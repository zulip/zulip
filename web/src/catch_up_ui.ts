import $ from "jquery";

import render_catch_up_view from "../templates/catch_up_view/catch_up_view.hbs";

import * as blueslip from "./blueslip.ts";
import * as catch_up_data from "./catch_up_data.ts";
import type {CatchUpTopic} from "./catch_up_data.ts";
import * as compose_closed_ui from "./compose_closed_ui.ts";
import * as hash_util from "./hash_util.ts";
import * as inbox_ui from "./inbox_ui.ts";
import * as left_sidebar_navigation_area from "./left_sidebar_navigation_area.ts";
import * as recent_view_ui from "./recent_view_ui.ts";
import * as stream_data from "./stream_data.ts";
import * as views_util from "./views_util.ts";

let is_catch_up_visible = false;

// Filter state
type FilterMode = "all" | "mentions" | "important";
let current_filter: FilterMode = "all";
let current_stream_filter: number | "all" = "all";

// Keyboard navigation state
let card_focus = -1;

// Importance score threshold for "Important" filter
const IMPORTANT_SCORE_THRESHOLD = 5.0;

export function is_visible(): boolean {
    return is_catch_up_visible;
}

export function is_in_focus(): boolean {
    if (!is_catch_up_visible) {
        return false;
    }
    // Consider catch-up in focus when the view is visible and focus is
    // inside the view or on a filter/card element.
    const active = document.activeElement;
    if (active === null) {
        return false;
    }
    return (
        $("#catch-up-view").has(active).length > 0 || $(active).is("#catch-up-view")
    );
}

function set_visible(value: boolean): void {
    is_catch_up_visible = value;
}

function format_period_display(hours: number): string {
    if (hours < 1) {
        const minutes = Math.round(hours * 60);
        return `${minutes} minutes away`;
    } else if (hours < 24) {
        const h = Math.round(hours);
        return `${h} hour${h !== 1 ? "s" : ""} away`;
    }
    const days = Math.round(hours / 24);
    return `${days} day${days !== 1 ? "s" : ""} away`;
}

function prepare_topic_for_render(topic: CatchUpTopic): Record<string, unknown> {
    const stream_color = stream_data.get_color(topic.stream_id);
    const topic_url = hash_util.by_stream_topic_url(topic.stream_id, topic.topic_name);
    const sender_list = topic.senders.join(", ");

    return {
        ...topic,
        stream_color,
        topic_url,
        sender_list,
        // String versions for data- attributes (Handlebars can't render booleans).
        data_has_mention: String(topic.has_mention),
        data_has_wildcard: String(topic.has_wildcard_mention),
        has_reactions: topic.reaction_count > 0,
        has_key_messages: (topic.key_messages ?? []).length > 0,
        has_sample_messages: topic.sample_messages.length > 0,
        has_keywords: (topic.keywords ?? []).length > 0,
    };
}

function get_unique_streams(
    topics: CatchUpTopic[],
): Array<{id: number; name: string}> {
    const seen = new Map<number, string>();
    for (const topic of topics) {
        if (!seen.has(topic.stream_id)) {
            seen.set(topic.stream_id, topic.stream_name);
        }
    }
    const streams: Array<{id: number; name: string}> = [];
    for (const [id, name] of seen) {
        streams.push({id, name});
    }
    streams.sort((a, b) => a.name.localeCompare(b.name));
    return streams;
}

function render_loading(): void {
    const html = render_catch_up_view({loading: true});
    $("#catch-up-pane").html(html);
}

function render_empty(): void {
    const html = render_catch_up_view({has_no_data: true});
    $("#catch-up-pane").html(html);
}

function render_data(data: catch_up_data.CatchUpData): void {
    const topics = data.topics.map((topic) => prepare_topic_for_render(topic));
    const streams = get_unique_streams(data.topics);

    const html = render_catch_up_view({
        loading: false,
        has_no_data: false,
        catch_up_period_display: format_period_display(data.catch_up_period_hours),
        total_messages: data.total_messages,
        total_topics: data.total_topics,
        topics,
        streams,
        has_streams: streams.length > 0,
    });

    $("#catch-up-pane").html(html);

    // Reset filter and focus state for fresh render.
    current_filter = "all";
    current_stream_filter = "all";
    card_focus = -1;

    setup_event_handlers();
}

function setup_event_handlers(): void {
    // "AI Summary" button click handler.
    $(".catch-up-summarize-btn").on("click", function (this: HTMLElement, e) {
        e.stopPropagation();
        const $btn = $(this);
        const stream_id = Number($btn.attr("data-stream-id"));
        const topic_name = $btn.attr("data-topic-name");

        if (!topic_name || Number.isNaN(stream_id)) {
            return;
        }

        const $card = $btn.closest(".catch-up-topic-card");
        const $summary_container = $card.find(".catch-up-summary-container");

        // Show loading state.
        $summary_container.html(
            '<div class="catch-up-summary-loading"><div class="loading_indicator_spinner"></div> Generating summary…</div>',
        );

        void catch_up_data
            .fetch_topic_summary(stream_id, topic_name)
            .then((summary) => {
                $summary_container.html(summary);
            })
            .catch(() => {
                $summary_container.html(
                    '<div class="catch-up-summary-error">Failed to generate summary. AI features may not be enabled on this server.</div>',
                );
            });
    });

    // Filter button click handlers.
    $(".catch-up-filter-btn").on("click", function (this: HTMLElement) {
        const filter = $(this).attr("data-filter") as FilterMode | undefined;
        if (!filter) {
            return;
        }
        current_filter = filter;
        $(".catch-up-filter-btn").removeClass("active");
        $(this).addClass("active");
        apply_filters();
    });

    // Stream filter dropdown.
    $("#catch-up-stream-filter").on("change", function (this: HTMLSelectElement) {
        const val = $(this).val() as string;
        current_stream_filter = val === "all" ? "all" : Number(val);
        apply_filters();
    });

    // Expand/collapse toggle on card header click.
    $(".catch-up-topic-card").on("click", ".catch-up-card-header", function (this: HTMLElement, e) {
        // Don't toggle if clicking a link or button inside the header.
        if ($(e.target).closest("a, button").length > 0) {
            return;
        }
        const $card = $(this).closest(".catch-up-topic-card");
        toggle_card_expansion($card);
    });

    // Expand button click.
    $(".catch-up-expand-btn").on("click", function (this: HTMLElement, e) {
        e.stopPropagation();
        const $card = $(this).closest(".catch-up-topic-card");
        toggle_card_expansion($card);
    });

    // "Open topic" link click — stop propagation so it doesn't toggle the card.
    $(".catch-up-open-topic").on("click", function (_this: HTMLElement, e) {
        e.stopPropagation();
    });
}

function toggle_card_expansion($card: JQuery): void {
    $card.toggleClass("expanded");
    const $icon = $card.find(".catch-up-expand-btn .zulip-icon");
    if ($card.hasClass("expanded")) {
        $icon.removeClass("zulip-icon-chevron-down").addClass("zulip-icon-chevron-up");
    } else {
        $icon.removeClass("zulip-icon-chevron-up").addClass("zulip-icon-chevron-down");
    }
}

function apply_filters(): void {
    const $cards = $(".catch-up-topic-card");
    let visible_count = 0;

    $cards.each(function (this: HTMLElement) {
        const $card = $(this);
        const stream_id = Number($card.attr("data-stream-id"));
        const has_mention = $card.attr("data-has-mention") === "true";
        const has_wildcard = $card.attr("data-has-wildcard") === "true";
        const score = Number($card.attr("data-score"));

        let visible = true;

        // Apply importance filter.
        if (current_filter === "mentions") {
            visible = has_mention || has_wildcard;
        } else if (current_filter === "important") {
            visible = score >= IMPORTANT_SCORE_THRESHOLD;
        }

        // Apply stream filter.
        if (visible && current_stream_filter !== "all") {
            visible = stream_id === current_stream_filter;
        }

        if (visible) {
            $card.show();
            visible_count += 1;
        } else {
            $card.hide();
        }
    });

    // Show/hide the "no results" message.
    if (visible_count === 0) {
        $("#catch-up-no-filter-results").show();
    } else {
        $("#catch-up-no-filter-results").hide();
    }

    // Reset focus to avoid pointing at a hidden card.
    card_focus = -1;
}

// --- Keyboard navigation ---

function get_visible_cards(): JQuery {
    return $(".catch-up-topic-card:visible");
}

function focus_card(index: number): void {
    const $cards = get_visible_cards();
    if ($cards.length === 0) {
        return;
    }

    // Clamp index.
    if (index < 0) {
        index = 0;
    } else if (index >= $cards.length) {
        index = $cards.length - 1;
    }

    card_focus = index;
    const card_el = $cards.eq(index).get(0);
    if (card_el) {
        card_el.focus();
        // Scroll into view if needed.
        card_el.scrollIntoView({block: "nearest", behavior: "smooth"});
    }
}

function focus_filters(): void {
    card_focus = -1;
    const $active_filter = $(".catch-up-filter-btn.active");
    if ($active_filter.length > 0) {
        $active_filter.trigger("focus");
    }
}

function open_focused_topic(): void {
    const $cards = get_visible_cards();
    if (card_focus < 0 || card_focus >= $cards.length) {
        return;
    }
    const $card = $cards.eq(card_focus);
    const $link = $card.find(".catch-up-open-topic");
    if ($link.length > 0) {
        window.location.href = $link.attr("href") ?? "";
    }
}

export function change_focused_element(input_key: string): boolean {
    if (!is_catch_up_visible) {
        return false;
    }

    const $cards = get_visible_cards();

    // If focus is on a filter button.
    const active = document.activeElement;
    const is_on_filter =
        active !== null && $(active).hasClass("catch-up-filter-btn");
    const is_on_stream_select =
        active !== null && $(active).is("#catch-up-stream-filter");

    if (is_on_filter || is_on_stream_select) {
        switch (input_key) {
            case "down_arrow":
            case "vim_down":
                if ($cards.length > 0) {
                    focus_card(0);
                }
                return true;
            case "right_arrow":
            case "vim_right":
                if (is_on_filter) {
                    const $next = $(active!).next(".catch-up-filter-btn");
                    if ($next.length > 0) {
                        $next.trigger("focus");
                    } else {
                        // Move to stream filter dropdown if it exists.
                        const $select = $("#catch-up-stream-filter");
                        if ($select.length > 0) {
                            $select.trigger("focus");
                        }
                    }
                }
                return true;
            case "left_arrow":
            case "vim_left":
                if (is_on_filter) {
                    const $prev = $(active!).prev(".catch-up-filter-btn");
                    if ($prev.length > 0) {
                        $prev.trigger("focus");
                    }
                } else if (is_on_stream_select) {
                    const $last_btn = $(".catch-up-filter-btn").last();
                    if ($last_btn.length > 0) {
                        $last_btn.trigger("focus");
                    }
                }
                return true;
        }
        return false;
    }

    // Focus is on a topic card.
    switch (input_key) {
        case "down_arrow":
        case "vim_down":
            if (card_focus < $cards.length - 1) {
                focus_card(card_focus + 1);
            }
            return true;
        case "up_arrow":
        case "vim_up":
            if (card_focus <= 0) {
                focus_filters();
                return true;
            }
            focus_card(card_focus - 1);
            return true;
        case "page_down": {
            const new_focus = Math.min(card_focus + 5, $cards.length - 1);
            focus_card(new_focus);
            return true;
        }
        case "page_up": {
            const new_focus = Math.max(card_focus - 5, 0);
            focus_card(new_focus);
            return true;
        }
        case "vim_right":
        case "right_arrow":
            // Expand the card if collapsed.
            if (card_focus >= 0 && card_focus < $cards.length) {
                const $card = $cards.eq(card_focus);
                if (!$card.hasClass("expanded")) {
                    toggle_card_expansion($card);
                }
            }
            return true;
        case "vim_left":
        case "left_arrow":
            // Collapse the card if expanded.
            if (card_focus >= 0 && card_focus < $cards.length) {
                const $card = $cards.eq(card_focus);
                if ($card.hasClass("expanded")) {
                    toggle_card_expansion($card);
                }
            }
            return true;
    }

    return false;
}

export function handle_enter_key(): boolean {
    if (!is_catch_up_visible) {
        return false;
    }

    const active = document.activeElement;

    // If on a filter button, activate it.
    if (active !== null && $(active).hasClass("catch-up-filter-btn")) {
        $(active).trigger("click");
        return true;
    }

    // If on a topic card, open the topic.
    if (card_focus >= 0) {
        open_focused_topic();
        return true;
    }

    return false;
}

export function complete_rerender(): void {
    if (!is_catch_up_visible) {
        return;
    }

    render_loading();

    void catch_up_data
        .fetch_catch_up_data(true)
        .then((data) => {
            if (!is_catch_up_visible) {
                return;
            }
            if (data.total_messages === 0) {
                render_empty();
            } else {
                render_data(data);
            }
        })
        .catch((error: unknown) => {
            if (!is_catch_up_visible) {
                return;
            }
            blueslip.error("Failed to load catch-up data", {error: String(error)});
            render_empty();
        });
}

export function show(): void {
    // Hide other non-message-feed views before showing catch-up.
    inbox_ui.hide();
    recent_view_ui.hide();

    views_util.show({
        highlight_view_in_left_sidebar() {
            views_util.handle_message_view_deactivated(
                left_sidebar_navigation_area.highlight_catch_up_view,
            );
        },
        $view: $("#catch-up-view"),
        update_compose: compose_closed_ui.update_buttons,
        is_visible,
        set_visible,
        complete_rerender,
    });
}

export function hide(): void {
    if (!is_catch_up_visible) {
        return;
    }

    views_util.hide({
        $view: $("#catch-up-view"),
        set_visible,
    });

    // Reset state.
    card_focus = -1;
    current_filter = "all";
    current_stream_filter = "all";
    catch_up_data.clear_data();
}
