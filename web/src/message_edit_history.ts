import $ from "jquery";
import assert from "minimalistic-assert";
import {z} from "zod";

import render_message_edit_history from "../templates/message_edit_history.hbs";
import render_message_history_modal from "../templates/message_history_modal.hbs";

import * as channel from "./channel";
import * as dialog_widget from "./dialog_widget";
import {$t, $t_html} from "./i18n";
import * as message_lists from "./message_lists";
import type {Message} from "./message_store";
import {page_params} from "./page_params";
import * as people from "./people";
import * as rendered_markdown from "./rendered_markdown";
import * as rows from "./rows";
import * as spectators from "./spectators";
import {realm} from "./state_data";
import * as sub_store from "./sub_store";
import {is_same_day} from "./time_zone_util";
import * as timerender from "./timerender";
import * as ui_report from "./ui_report";
import {user_settings} from "./user_settings";

type EditHistoryEntry = {
    timestamp: string;
    display_date: string;
    show_date_row: boolean;
    edited_by_notice: string;
    body_to_render?: string;
    topic_edited?: boolean;
    prev_topic?: string;
    new_topic?: string;
    stream_changed?: boolean;
    prev_stream?: string;
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

export function fetch_and_render_message_history(message: Message): void {
    void channel.get({
        url: "/json/messages/" + message.id + "/history",
        data: {message_id: JSON.stringify(message.id)},
        success(data) {
            const clean_data = server_message_history_schema.parse(data);

            const content_edit_history: EditHistoryEntry[] = [];
            let prev_time = null;
            let prev_stream_item: EditHistoryEntry | null = null;

            const date_time_format = new Intl.DateTimeFormat(user_settings.default_language, {
                year: "numeric",
                month: "long",
                day: "numeric",
            });
            for (const [index, msg] of clean_data.message_history.entries()) {
                // Format times and dates nicely for display
                const time = new Date(msg.timestamp * 1000);
                const timestamp = timerender.stringify_time(time);
                const display_date = date_time_format.format(time);
                const show_date_row =
                    prev_time === null ||
                    !is_same_day(time, prev_time, timerender.display_time_zone);

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
                    const sub = sub_store.get(msg.prev_stream);
                    edited_by_notice = $t({defaultMessage: "Moved by {full_name}"}, {full_name});
                    topic_edited = true;
                    prev_topic = msg.prev_topic;
                    new_topic = msg.topic;
                    stream_changed = true;
                    if (!sub) {
                        prev_stream = $t({defaultMessage: "Unknown stream"});
                    } else {
                        prev_stream = sub_store.maybe_get_stream_name(msg.prev_stream);
                    }
                    if (prev_stream_item !== null) {
                        prev_stream_item.new_stream = sub_store.maybe_get_stream_name(
                            msg.prev_stream,
                        );
                    }
                } else if (msg.prev_topic) {
                    edited_by_notice = $t({defaultMessage: "Moved by {full_name}"}, {full_name});
                    topic_edited = true;
                    prev_topic = msg.prev_topic;
                    new_topic = msg.topic;
                } else if (msg.prev_stream) {
                    const sub = sub_store.get(msg.prev_stream);
                    edited_by_notice = $t({defaultMessage: "Moved by {full_name}"}, {full_name});
                    stream_changed = true;
                    if (!sub) {
                        prev_stream = $t({defaultMessage: "Unknown stream"});
                    } else {
                        prev_stream = sub_store.maybe_get_stream_name(msg.prev_stream);
                    }
                    if (prev_stream_item !== null) {
                        prev_stream_item.new_stream = sub_store.maybe_get_stream_name(
                            msg.prev_stream,
                        );
                    }
                } else {
                    // just a content edit
                    edited_by_notice = $t({defaultMessage: "Edited by {full_name}"}, {full_name});
                    body_to_render = msg.content_html_diff;
                }

                const item: EditHistoryEntry = {
                    timestamp,
                    display_date,
                    show_date_row,
                    edited_by_notice,
                    body_to_render,
                    topic_edited,
                    prev_topic,
                    new_topic,
                    stream_changed,
                    prev_stream,
                    new_stream: undefined,
                };

                if (msg.prev_stream) {
                    prev_stream_item = item;
                }

                content_edit_history.push(item);
                prev_time = time;
            }
            if (prev_stream_item !== null) {
                assert(message.type === "stream");
                prev_stream_item.new_stream = sub_store.maybe_get_stream_name(message.stream_id);
            }
            show_history();
            $("#message-history").attr("data-message-id", message.id);
            $("#message-history").html(
                render_message_edit_history({
                    edited_messages: content_edit_history,
                }),
            );
            // Pass the history through rendered_markdown.ts
            // to update dynamic_elements in the content.
            $("#message-history")
                .find(".rendered_markdown")
                .each(function () {
                    rendered_markdown.update_elements($(this));
                });
        },
        error(xhr) {
            ui_report.error(
                $t_html({defaultMessage: "Error fetching message edit history"}),
                xhr,
                $("#dialog_error"),
            );
        },
    });
}

export function show_history(): void {
    if (!$("#message-history").length) {
        const rendered_message_history = render_message_history_modal();

        dialog_widget.launch({
            html_heading: $t_html({defaultMessage: "Message edit history"}),
            html_body: rendered_message_history,
            html_submit_button: $t_html({defaultMessage: "Close"}),
            id: "message-edit-history",
            on_click() {
                /* do nothing */
            },
            close_on_submit: true,
            focus_submit_on_open: true,
            single_footer_button: true,
        });
    }
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

    $("body").on("click", ".message_edit_notice", (e) => {
        e.stopPropagation();
        e.preventDefault();

        const message_id = rows.id($(e.currentTarget).closest(".message_row"));
        assert(message_id !== undefined);
        assert(message_lists.current !== undefined);
        const $row = message_lists.current.get_row(message_id);
        const row_id = rows.id($row);
        assert(row_id !== undefined);
        const message = message_lists.current.get(row_id);
        assert(message !== undefined);

        if (page_params.is_spectator) {
            spectators.login_to_access();
            return;
        }

        if (realm.realm_allow_edit_history) {
            fetch_and_render_message_history(message);
            $("#message-history-cancel").trigger("focus");
        }
    });
}
