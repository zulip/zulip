import {format, isSameDay} from "date-fns";
import $ from "jquery";

import render_message_edit_history from "../templates/message_edit_history.hbs";
import render_message_history_modal from "../templates/message_history_modal.hbs";

import * as channel from "./channel";
import {$t_html} from "./i18n";
import * as message_lists from "./message_lists";
import * as overlays from "./overlays";
import {page_params} from "./page_params";
import * as people from "./people";
import * as popovers from "./popovers";
import * as rows from "./rows";
import * as timerender from "./timerender";
import * as ui_report from "./ui_report";

export function fetch_and_render_message_history(message) {
    channel.get({
        url: "/json/messages/" + message.id + "/history",
        data: {message_id: JSON.stringify(message.id)},
        success(data) {
            const content_edit_history = [];
            let prev_time = null;

            for (const [index, msg] of data.message_history.entries()) {
                // Format times and dates nicely for display
                const time = new Date(msg.timestamp * 1000);
                const item = {
                    timestamp: timerender.stringify_time(time),
                    display_date: format(time, "MMMM d, yyyy"),
                    show_date_row: prev_time === null || !isSameDay(time, prev_time),
                };

                if (msg.user_id) {
                    const person = people.get_by_user_id(msg.user_id);
                    item.edited_by = person.full_name;
                }

                if (index === 0) {
                    item.posted_or_edited = "Posted by";
                    item.body_to_render = msg.rendered_content;
                } else if (msg.prev_topic && msg.prev_content) {
                    item.posted_or_edited = "Edited by";
                    item.body_to_render = msg.content_html_diff;
                    item.topic_edited = true;
                    item.prev_topic = msg.prev_topic;
                    item.new_topic = msg.topic;
                } else if (msg.prev_topic) {
                    item.posted_or_edited = "Topic edited by";
                    item.topic_edited = true;
                    item.prev_topic = msg.prev_topic;
                    item.new_topic = msg.topic;
                } else {
                    // just a content edit
                    item.posted_or_edited = "Edited by";
                    item.body_to_render = msg.content_html_diff;
                }

                content_edit_history.push(item);

                prev_time = time;
            }
            $("#message-history").attr("data-message-id", message.id);
            $("#message-history").html(
                render_message_edit_history({
                    edited_messages: content_edit_history,
                }),
            );
        },
        error(xhr) {
            ui_report.error(
                $t_html({defaultMessage: "Error fetching message edit history"}),
                xhr,
                $("#message-history-error"),
            );
        },
    });
}

export function show_history(message) {
    const rendered_message_history = render_message_history_modal();
    $("#message_feed_container").append(rendered_message_history);

    fetch_and_render_message_history(message);
    overlays.open_modal("#message-edit-history", {autoremove: true});
}

export function initialize() {
    $("body").on("mouseenter", ".message_edit_notice", (e) => {
        if (page_params.realm_allow_edit_history) {
            $(e.currentTarget).addClass("message_edit_notice_hover");
        }
    });

    $("body").on("mouseleave", ".message_edit_notice", (e) => {
        if (page_params.realm_allow_edit_history) {
            $(e.currentTarget).removeClass("message_edit_notice_hover");
        }
    });

    $("body").on("click", ".message_edit_notice", (e) => {
        popovers.hide_all();
        const message_id = rows.id($(e.currentTarget).closest(".message_row"));
        const row = message_lists.current.get_row(message_id);
        const message = message_lists.current.get(rows.id(row));

        if (page_params.realm_allow_edit_history) {
            show_history(message);
            $("#message-history-cancel").trigger("focus");
        }
        e.stopPropagation();
        e.preventDefault();
    });
}
