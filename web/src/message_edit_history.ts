import $ from "jquery";
import assert from "minimalistic-assert";
import {z} from "zod";

import render_message_edit_history from "../templates/message_edit_history.hbs";
import render_message_history_overlay from "../templates/message_history_overlay.hbs";

import {exit_overlay} from "./browser_history";
import * as channel from "./channel";
import {$t, $t_html} from "./i18n";
import * as loading from "./loading";
import * as message_lists from "./message_lists";
import type {Message} from "./message_store";
import * as messages_overlay_ui from "./messages_overlay_ui";
import * as overlays from "./overlays";
import {page_params} from "./page_params";
import * as people from "./people";
import * as rendered_markdown from "./rendered_markdown";
import * as rows from "./rows";
import * as spectators from "./spectators";
import {realm} from "./state_data";
import {get_recipient_bar_color} from "./stream_color";
import {get_color} from "./stream_data";
import * as sub_store from "./sub_store";
import * as timerender from "./timerender";
import * as ui_report from "./ui_report";

type EditHistoryEntry = {
    edited_at_time: string;
    edited_by_notice: string;
    timestamp: number; // require to set data-message-id for overlay message row
    is_stream: boolean;
    recipient_bar_color?: string;
    body_to_render?: string;
    topic_edited?: boolean;
    prev_topic?: string;
    new_topic?: string;
    stream_changed?: boolean;
    prev_stream?: string;
    prev_stream_id?: number;
    new_stream?: string;
};

const server_message_history_schema = z.object({
    message_history: z.array(
        z.object({
            content: z.string(),
            rendered_content: z.string(),
            timestamp: z.number(),
            topic: z.string(),
            user_id: z.number().or(z.null()),
            prev_topic: z.string().optional(),
            stream: z.number().optional(),
            prev_stream: z.number().optional(),
            prev_content: z.string().optional(),
            prev_rendered_content: z.string().optional(),
            content_html_diff: z.string().optional(),
        }),
    ),
});

// This will be used to handle up and down keyws
const keyboard_handling_context: messages_overlay_ui.Context = {
    items_container_selector: "message-edit-history-container",
    items_list_selector: "message-edit-history-list",
    row_item_selector: "overlay-message-row",
    box_item_selector: "overlay-message-info-box",
    id_attribute_name: "data-message-edit-history-id",
    get_items_ids(): number[] {
        const edited_messages_ids: number[] = [];
        const $message_history_list: JQuery = $(
            "#message-history-overlay .message-edit-history-list",
        );
        for (const message of $message_history_list.children()) {
            const data_message_edit_history_id = $(message).attr("data-message-edit-history-id");
            assert(data_message_edit_history_id !== undefined);
            edited_messages_ids.push(Number(data_message_edit_history_id));
        }
        return edited_messages_ids;
    },
    on_enter() {
        return;
    },
    on_delete() {
        return;
    },
};

function get_display_stream_name(stream_id: number): string {
    const stream_name = sub_store.maybe_get_stream_name(stream_id);
    if (stream_name === undefined) {
        return $t({defaultMessage: "Unknown channel"});
    }
    return stream_name;
}

function show_loading_indicator(): void {
    loading.make_indicator($(".message-edit-history-container .loading_indicator"));
    $(".message-edit-history-container .loading_indicator").addClass(
        "overlay_loading_indicator_style",
    );
}

function hide_loading_indicator(): void {
    loading.destroy_indicator($(".message-edit-history-container .loading_indicator"));
    $(".message-edit-history-container .loading_indicator").removeClass(
        "overlay_loading_indicator_style",
    );
}

export function fetch_and_render_message_history(message: Message): void {
    $("#message-edit-history-overlay-container").html(render_message_history_overlay());
    open_overlay();
    show_loading_indicator();
    void channel.get({
        url: "/json/messages/" + message.id + "/history",
        data: {message_id: JSON.stringify(message.id)},
        success(data) {
            const clean_data = server_message_history_schema.parse(data);

            const content_edit_history: EditHistoryEntry[] = [];
            let prev_stream_item: EditHistoryEntry | null = null;
            for (const [index, msg] of clean_data.message_history.entries()) {
                // Format times and dates nicely for display
                const time = new Date(msg.timestamp * 1000);
                const edited_at_time = timerender.get_full_datetime(time, "time");

                if (!msg.user_id) {
                    continue;
                }

                const person = people.get_user_by_id_assert_valid(msg.user_id);
                const full_name = person.full_name;

                let edited_by_notice;
                let body_to_render;
                let topic_edited;
                let prev_topic;
                let new_topic;
                let stream_changed;
                let prev_stream;
                let prev_stream_id;

                if (index === 0) {
                    edited_by_notice = $t({defaultMessage: "Posted by {full_name}"}, {full_name});
                    body_to_render = msg.rendered_content;
                } else if (msg.prev_topic && msg.prev_content) {
                    edited_by_notice = $t({defaultMessage: "Edited by {full_name}"}, {full_name});
                    body_to_render = msg.content_html_diff;
                    topic_edited = true;
                    prev_topic = msg.prev_topic;
                    new_topic = msg.topic;
                } else if (msg.prev_topic && msg.prev_stream) {
                    edited_by_notice = $t({defaultMessage: "Moved by {full_name}"}, {full_name});
                    topic_edited = true;
                    prev_topic = msg.prev_topic;
                    new_topic = msg.topic;
                    stream_changed = true;
                    prev_stream_id = msg.prev_stream;
                    prev_stream = get_display_stream_name(msg.prev_stream);
                    if (prev_stream_item !== null) {
                        prev_stream_item.new_stream = get_display_stream_name(msg.prev_stream);
                    }
                } else if (msg.prev_topic) {
                    edited_by_notice = $t({defaultMessage: "Moved by {full_name}"}, {full_name});
                    topic_edited = true;
                    prev_topic = msg.prev_topic;
                    new_topic = msg.topic;
                } else if (msg.prev_stream) {
                    edited_by_notice = $t({defaultMessage: "Moved by {full_name}"}, {full_name});
                    stream_changed = true;
                    prev_stream_id = msg.prev_stream;
                    prev_stream = get_display_stream_name(msg.prev_stream);
                    if (prev_stream_item !== null) {
                        prev_stream_item.new_stream = get_display_stream_name(msg.prev_stream);
                    }
                } else {
                    // just a content edit
                    edited_by_notice = $t({defaultMessage: "Edited by {full_name}"}, {full_name});
                    body_to_render = msg.content_html_diff;
                }
                const item: EditHistoryEntry = {
                    edited_at_time,
                    edited_by_notice,
                    timestamp: msg.timestamp,
                    is_stream: message.is_stream,
                    recipient_bar_color: undefined,
                    body_to_render,
                    topic_edited,
                    prev_topic,
                    new_topic,
                    stream_changed,
                    prev_stream,
                    prev_stream_id,
                    new_stream: undefined,
                };

                if (msg.prev_stream) {
                    prev_stream_item = item;
                }

                content_edit_history.push(item);
            }
            if (prev_stream_item !== null) {
                assert(message.type === "stream");
                prev_stream_item.new_stream = get_display_stream_name(message.stream_id);
            }

            // In order to correctly compute the recipient_bar_color
            // values, it is convenient to iterate through the array of edit history
            // entries in reverse chronological order.
            if (message.is_stream) {
                // Start with the message's current location.
                let stream_color: string = get_color(message.stream_id);
                let recipient_bar_color: string = get_recipient_bar_color(stream_color);
                for (const edit_history_entry of content_edit_history.toReversed()) {
                    // The stream following this move is the one whose color we already have.
                    edit_history_entry.recipient_bar_color = recipient_bar_color;
                    if (edit_history_entry.stream_changed) {
                        // If this event moved the message, then immediately
                        // prior to this event, the message must have been in
                        // edit_history_event.prev_stream_id; fetch its color.
                        assert(edit_history_entry.prev_stream_id !== undefined);
                        stream_color = get_color(edit_history_entry.prev_stream_id);
                        recipient_bar_color = get_recipient_bar_color(stream_color);
                    }
                }
            }
            const rendered_list_html = render_message_edit_history({
                edited_messages: content_edit_history,
            });
            $("#message-history-overlay").attr("data-message-id", message.id);
            hide_loading_indicator();
            $("#message-history-overlay .overlay-messages-list").append($(rendered_list_html));

            // Pass the history through rendered_markdown.ts
            // to update dynamic_elements in the content.
            $("#message-history-overlay")
                .find(".rendered_markdown")
                .each(function () {
                    rendered_markdown.update_elements($(this));
                });
            const first_element_id = content_edit_history[0].timestamp;
            messages_overlay_ui.set_initial_element(
                String(first_element_id),
                keyboard_handling_context,
            );
        },
        error(xhr) {
            ui_report.error(
                $t_html({defaultMessage: "Error fetching message edit history."}),
                xhr,
                $("#message-history-overlay #message-history-error"),
            );
            hide_loading_indicator();
            $("#message-history-error").show();
        },
    });
}

export function open_overlay(): void {
    if (overlays.any_active()) {
        return;
    }
    overlays.open_overlay({
        name: "message_edit_history",
        $overlay: $("#message-history-overlay"),
        on_close() {
            exit_overlay();
            $("#message-edit-history-overlay-container").empty();
        },
    });
}

export function handle_keyboard_events(event_key: string): void {
    messages_overlay_ui.modals_handle_events(event_key, keyboard_handling_context);
}

export function initialize(): void {
    $("body").on("mouseenter", ".message_edit_notice", (e) => {
        if (realm.realm_allow_edit_history) {
            $(e.currentTarget).addClass("message_edit_notice_hover");
        }
    });

    $("body").on("mouseleave", ".message_edit_notice", (e) => {
        if (realm.realm_allow_edit_history) {
            $(e.currentTarget).removeClass("message_edit_notice_hover");
        }
    });

    $("body").on("click", ".message_edit_notice", function (this: HTMLElement, e) {
        e.stopPropagation();
        e.preventDefault();

        const message_id = rows.id($(this).closest(".message_row"));
        assert(message_lists.current !== undefined);
        const $row = message_lists.current.get_row(message_id);
        const row_id = rows.id($row);
        const message = message_lists.current.get(row_id);
        assert(message !== undefined);

        if (page_params.is_spectator) {
            spectators.login_to_access();
            return;
        }

        if (realm.realm_allow_edit_history) {
            fetch_and_render_message_history(message);
            $("#message-history-overlay .exit-sign").trigger("focus");
        }
    });

    $("body").on(
        "focus",
        "#message-history-overlay .overlay-message-info-box",
        function (this: HTMLElement) {
            messages_overlay_ui.activate_element(this, keyboard_handling_context);
        },
    );
}
