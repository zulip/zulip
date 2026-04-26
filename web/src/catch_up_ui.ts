import $ from "jquery";

import render_catch_up_overview_panel from "../templates/catch_up_view/catch_up_overview_panel.hbs";
import render_catch_up_overview_status from "../templates/catch_up_view/catch_up_overview_status.hbs";
import render_catch_up_view from "../templates/catch_up_view/catch_up_view.hbs";

import * as blueslip from "./blueslip.ts";
import * as catch_up_data from "./catch_up_data.ts";
import type {CatchUpOverviewResponse} from "./catch_up_data.ts";
import type {CatchUpTopic} from "./catch_up_data.ts";
import * as compose_closed_ui from "./compose_closed_ui.ts";
import * as hash_util from "./hash_util.ts";
import * as inbox_ui from "./inbox_ui.ts";
import * as left_sidebar_navigation_area from "./left_sidebar_navigation_area.ts";
import * as recent_view_ui from "./recent_view_ui.ts";
import * as rendered_markdown from "./rendered_markdown.ts";
import * as stream_data from "./stream_data.ts";
import * as views_util from "./views_util.ts";

let is_catch_up_visible = false;
let catch_up_visible_start_time_ms: number | undefined;

function start_catch_up_usage_timer(): void {
    if (catch_up_visible_start_time_ms !== undefined) {
        return;
    }
    catch_up_visible_start_time_ms = Date.now();
}

function stop_and_report_catch_up_usage_timer(): void {
    if (catch_up_visible_start_time_ms === undefined) {
        return;
    }

    const duration_ms = Date.now() - catch_up_visible_start_time_ms;
    catch_up_visible_start_time_ms = undefined;

    // Filter out accidental flashes and negative/invalid durations.
    if (!Number.isFinite(duration_ms) || duration_ms < 1000) {
        return;
    }

    const data = catch_up_data.get_current_data();
    const items: catch_up_data.CatchUpUsageItem[] = [];
    for (const topic of data?.topics ?? []) {
        if (topic.is_dm === true) {
            const dm_user_ids = topic.dm_user_ids ?? [];
            if (dm_user_ids.length === 1) {
                const dm_sender_id = topic.dm_sender_id ?? dm_user_ids[0];
                items.push({
                    item_type: "dm_personal",
                    dm_sender_id,
                    first_message_id: topic.first_message_id,
                    last_message_id: topic.latest_message_id,
                    message_count: topic.message_count,
                });
            } else if (topic.dm_recipient_id !== undefined) {
                items.push({
                    item_type: "dm_group",
                    dm_recipient_id: topic.dm_recipient_id,
                    first_message_id: topic.first_message_id,
                    last_message_id: topic.latest_message_id,
                    message_count: topic.message_count,
                });
            }
        } else {
            items.push({
                item_type: "stream_topic",
                stream_id: topic.stream_id,
                topic_name: topic.topic_name,
                first_message_id: topic.first_message_id,
                last_message_id: topic.latest_message_id,
                message_count: topic.message_count,
            });
        }
        if (items.length >= 50) {
            break;
        }
    }

    catch_up_data.report_catch_up_usage(duration_ms, items);
}

// Filter state
type FilterMode = "all" | "mentions" | "important" | "ai-summary";
let current_filter: FilterMode = "all";
let current_stream_filter: number | "all" = "all";

/** Draft text for catch-up overview prompt preferences (survives filter re-renders). */
let summary_preferences_draft = "";

/** Whether the AI Summary tab instructions textarea is visible (hidden by default). */
let ai_summary_instructions_expanded = false;

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
    /*
    if (value && !is_catch_up_visible) {
        start_catch_up_usage_timer();
    } else if (!value && is_catch_up_visible) {
        stop_and_report_catch_up_usage_timer();
    }
    is_catch_up_visible = value;*/

    if (value === is_catch_up_visible) {
        return;
    }

    if (value) {
        start_catch_up_usage_timer();
    } else {
        stop_and_report_catch_up_usage_timer();
    }

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
    const is_dm = topic.is_dm === true;
    let stream_color: string;
    let topic_url: string;

    if (is_dm && topic.dm_user_ids && topic.dm_user_ids.length > 0) {
        stream_color = "#607D8B";
        const user_ids_string = topic.dm_user_ids.join(",");
        topic_url = hash_util.pm_with_url(user_ids_string);
    } else {
        stream_color = stream_data.get_color(topic.stream_id);
        topic_url = hash_util.by_stream_topic_url(topic.stream_id, topic.topic_name);
    }

    const sender_list = topic.senders.join(", ");

    return {
        ...topic,
        stream_color,
        topic_url,
        sender_list,
        is_dm,
        data_is_dm: String(is_dm),
        // String versions for data- attributes (Handlebars can't render booleans).
        data_has_mention: String(topic.has_mention),
        data_has_wildcard: String(topic.has_wildcard_mention),
        has_reactions: topic.reaction_count > 0,
        has_key_messages: (topic.key_messages ?? []).length > 0,
        has_sample_messages: topic.sample_messages.length > 0,
        has_keywords: (topic.keywords ?? []).length > 0,
    };
}

/** Illustrative “time saved” metrics for the catch-up tab (dummy visualization). */
function prepare_time_saved_context(
    data: catch_up_data.CatchUpData,
): Record<string, unknown> {
    const messages = data.total_messages;
    const topics = data.total_topics;
    const minutes_saved = Math.min(120, Math.max(10, Math.round(messages * 0.4 + topics * 2.5)));
    const minutes_linear = Math.min(480, Math.max(35, Math.round(messages * 1.35 + topics * 6)));

    const seg_summaries_pct = 42;
    const seg_priority_pct = 33;
    const seg_skipped_pct = 25;

    const d1 = Math.round((360 * seg_summaries_pct) / 100);
    const d2 = d1 + Math.round((360 * seg_priority_pct) / 100);

    const catchup_bar_pct = Math.max(
        18,
        Math.min(100, Math.round((minutes_saved / minutes_linear) * 100)),
    );

    return {
        minutes_saved,
        minutes_linear,
        seg_summaries_pct,
        seg_priority_pct,
        seg_skipped_pct,
        seg_summaries_end_deg: d1,
        seg_priority_end_deg: d2,
        linear_bar_pct: 100,
        catchup_bar_pct,
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
    const $prefs_field = $("#catch-up-summary-preferences");
    if ($prefs_field.length > 0) {
        summary_preferences_draft = String($prefs_field.val() ?? "");
    }

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
        is_all_filter: current_filter === "all",
        is_mentions_filter: current_filter === "mentions",
        is_important_filter: current_filter === "important",
        is_ai_summary_filter: current_filter === "ai-summary",
        catch_up_summary_preferences_value: summary_preferences_draft,
        time_saved: prepare_time_saved_context(data),
    });

    $("#catch-up-pane").html(html);

    $("#catch-up-pane")
        .find(".rendered_markdown")
        .each(function () {
            rendered_markdown.update_elements($(this));
        });

    // Reset filter and focus state for fresh render.
    card_focus = -1;

    setup_event_handlers();
    if (current_filter === "ai-summary") {
        sync_ai_summary_instructions_visibility();
        load_ai_summary_overview(false);
    } else {
        apply_filters();
    }
}

function sync_ai_summary_instructions_visibility(): void {
    const $block = $("#catch-up-preferences-collapsible");
    const $toggle = $("#catch-up-summary-prefs-toggle");
    if ($block.length === 0 || $toggle.length === 0) {
        return;
    }
    if (ai_summary_instructions_expanded) {
        $block.show();
        $toggle.attr("aria-expanded", "true");
    } else {
        $block.hide();
        $toggle.attr("aria-expanded", "false");
    }
}

function setup_event_handlers(): void {
    // Filter button click handlers.
    $(".catch-up-filter-btn").on("click", function (this: HTMLElement) {
        const filter = $(this).attr("data-filter") as FilterMode | undefined;
        if (!filter) {
            return;
        }
        if (current_filter === "ai-summary" && filter !== "ai-summary") {
            ai_summary_instructions_expanded = false;
        }
        current_filter = filter;
        const data = catch_up_data.get_current_data();
        if (data !== undefined) {
            render_data(data);
        }
    });

    $("#catch-up-summary-preferences").on("input", function (this: HTMLTextAreaElement) {
        summary_preferences_draft = this.value;
    });

    $("#catch-up-summary-prefs-toggle").on("click", () => {
        ai_summary_instructions_expanded = !ai_summary_instructions_expanded;
        sync_ai_summary_instructions_visibility();
    });

    $("#catch-up-regenerate-overview").on("click", () => {
        const $ta = $("#catch-up-summary-preferences");
        if ($ta.length > 0) {
            summary_preferences_draft = String($ta.val() ?? "");
        }
        load_ai_summary_overview(true);
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
    cached_overview = null;
    cached_overview_preferences_key = "";
    summary_preferences_draft = "";
    ai_summary_instructions_expanded = false;
    catch_up_data.clear_data();
}

// ── AI Summary tab: POST /json/catch-up/overview (US-08) ──────────────────────

type OverviewResponse = CatchUpOverviewResponse;

let cached_overview: OverviewResponse | null = null;
/** Preferences string used for `cached_overview`; regenerated when preferences differ. */
let cached_overview_preferences_key = "";

function wrap_overview_html(inner: string): string {
    return `<div class="catch-up-overview-panel">${inner}</div>`;
}

function load_ai_summary_overview(force: boolean): void {
    const $body = $("#catch-up-ai-summary-body");
    if ($body.length === 0) {
        return;
    }

    const prefs = String($("#catch-up-summary-preferences").val() ?? summary_preferences_draft);

    if (
        !force &&
        cached_overview !== null &&
        cached_overview_preferences_key === prefs
    ) {
        $body.html(
            wrap_overview_html(
                render_catch_up_overview_panel(prepare_overview_context(cached_overview)),
            ),
        );
        return;
    }

    $body.html(
        wrap_overview_html(
            render_catch_up_overview_status({is_loading: true, error_msg: ""}),
        ),
    );

    void catch_up_data
        .fetch_catch_up_overview(prefs)
        .then((data: OverviewResponse) => {
            cached_overview = data;
            cached_overview_preferences_key = prefs;
            if (!$("#catch-up-ai-summary-body").length) {
                return;
            }
            $("#catch-up-ai-summary-body").html(
                wrap_overview_html(
                    render_catch_up_overview_panel(prepare_overview_context(data)),
                ),
            );
        })
        .catch((error: unknown) => {
            const error_msg =
                error instanceof Error ? error.message : "Failed to generate summary.";
            if (!$("#catch-up-ai-summary-body").length) {
                return;
            }
            $("#catch-up-ai-summary-body").html(
                wrap_overview_html(
                    render_catch_up_overview_status({is_loading: false, error_msg}),
                ),
            );
        });
}

function resolve_topic_url(stream: string, topic: string): string {
    const sub = stream_data.get_sub_by_name(stream);
    if (sub === undefined) {
        return "";
    }
    return hash_util.by_stream_topic_url(sub.stream_id, topic);
}

function prepare_overview_context(data: OverviewResponse): object {
    const action_items = data.action_items.map((item) => ({
        ...item,
        has_assignee: item.assignee !== null && item.assignee !== "",
        resolved_url: item.narrow_url ? resolve_topic_url(
            item.narrow_url.split("/topic/")[0]?.split("-").slice(1).join("-") ?? "",
            item.narrow_url.split("/topic/")[1] ?? "",
        ) : "",
        has_resolved_url: false as boolean,
    })).map((item) => ({...item, has_resolved_url: item.resolved_url !== ""}));

    const topics = data.topics.map((t) => {
        const topic_url = resolve_topic_url(t.stream, t.topic);
        return {
            ...t,
            topic_url,
            has_topic_url: topic_url !== "",
            key_messages: t.key_messages.map((km) => {
                const jump_url = resolve_topic_url(t.stream, t.topic);
                return {...km, jump_url, has_jump_url: jump_url !== ""};
            }),
        };
    });

    return {
        ...data,
        has_keywords: data.keywords.length > 0,
        has_action_items: data.action_items.length > 0,
        has_topics: data.topics.length > 0,
        action_items,
        topics,
    };
}
