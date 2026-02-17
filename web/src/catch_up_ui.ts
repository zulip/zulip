import $ from "jquery";

import render_catch_up_view from "../templates/catch_up_view/catch_up_view.hbs";
import render_catch_up_topic_card from "../templates/catch_up_view/catch_up_topic_card.hbs";

import * as blueslip from "./blueslip.ts";
import * as catch_up_data from "./catch_up_data.ts";
import type {CatchUpTopic} from "./catch_up_data.ts";
import * as compose_closed_ui from "./compose_closed_ui.ts";
import * as hash_util from "./hash_util.ts";
import * as inbox_ui from "./inbox_ui.ts";
import * as left_sidebar_navigation_area from "./left_sidebar_navigation_area.ts";
import * as loading from "./loading.ts";
import * as recent_view_ui from "./recent_view_ui.ts";
import * as stream_data from "./stream_data.ts";
import * as views_util from "./views_util.ts";

let is_catch_up_visible = false;

export function is_visible(): boolean {
    return is_catch_up_visible;
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
    };
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

    const html = render_catch_up_view({
        loading: false,
        has_no_data: false,
        catch_up_period_display: format_period_display(data.catch_up_period_hours),
        total_messages: data.total_messages,
        total_topics: data.total_topics,
        topics,
    });

    $("#catch-up-pane").html(html);
    setup_event_handlers();
}

function setup_event_handlers(): void {
    // "AI Summary" button click handler.
    $(".catch-up-summarize-btn").on("click", function (this: HTMLElement) {
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

    catch_up_data.clear_data();
}
