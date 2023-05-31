import {format, isSameDay} from "date-fns";
import $ from "jquery";

import render_message_edit_history from "../templates/message_edit_history.hbs";
import render_message_history_modal from "../templates/message_history_modal.hbs";

import * as channel from "./channel";
import * as dialog_widget from "./dialog_widget";
import {$t, $t_html} from "./i18n";
import * as message_lists from "./message_lists";
import {page_params} from "./page_params";
import * as people from "./people";
import * as popovers from "./popovers";
import * as rendered_markdown from "./rendered_markdown";
import * as rows from "./rows";
import * as spectators from "./spectators";
import * as sub_store from "./sub_store";
import * as timerender from "./timerender";
import * as ui_report from "./ui_report";

export function fetch_and_render_message_history(message) {
    channel.get({
        url: "/json/messages/" + message.id + "/history",
        data: {message_id: JSON.stringify(message.id)},
        success(data) {
            const content_edit_history = [];
            let prev_time = null;
            let prev_stream_item = null;

            for (const [index, msg] of data.message_history.entries()) {
                // Format times and dates nicely for display
                const time = new Date(msg.timestamp * 1000);
                const item = {
                    timestamp: timerender.stringify_time(time),
                    display_date: format(time, "MMMM d, yyyy"),
                    show_date_row: prev_time === null || !isSameDay(time, prev_time),
                };

                if (!msg.user_id) {
                    continue;
                }

                const person = people.get_by_user_id(msg.user_id);
                const full_name = person.full_name;

                if (index === 0) {
                    item.edited_by_notice = $t(
                        {defaultMessage: "Posted by {full_name}"},
                        {full_name},
                    );
                    item.body_to_render = msg.rendered_content;
                } else if (msg.prev_topic && msg.prev_content) {
                    item.edited_by_notice = $t(
                        {defaultMessage: "Edited by {full_name}"},
                        {full_name},
                    );
                    item.body_to_render = msg.content_html_diff;
                    item.topic_edited = true;
                    item.prev_topic = msg.prev_topic;
                    item.new_topic = msg.topic;
                } else if (msg.prev_topic && msg.prev_stream) {
                    const sub = sub_store.get(msg.prev_stream);
                    item.edited_by_notice = $t(
                        {defaultMessage: "Moved by {full_name}"},
                        {full_name},
                    );
                    item.topic_edited = true;
                    item.prev_topic = msg.prev_topic;
                    item.new_topic = msg.topic;
                    item.stream_changed = true;
                    if (!sub) {
                        item.prev_stream = $t({defaultMessage: "Unknown stream"});
                    } else {
                        item.prev_stream = sub_store.maybe_get_stream_name(msg.prev_stream);
                    }
                    if (prev_stream_item !== null) {
                        prev_stream_item.new_stream = sub_store.maybe_get_stream_name(
                            msg.prev_stream,
                        );
                    }
                    prev_stream_item = item;
                } else if (msg.prev_topic) {
                    item.edited_by_notice = $t(
                        {defaultMessage: "Moved by {full_name}"},
                        {full_name},
                    );
                    item.topic_edited = true;
                    item.prev_topic = msg.prev_topic;
                    item.new_topic = msg.topic;
                } else if (msg.prev_stream) {
                    const sub = sub_store.get(msg.prev_stream);
                    item.edited_by_notice = $t(
                        {defaultMessage: "Moved by {full_name}"},
                        {full_name},
                    );
                    item.stream_changed = true;
                    if (!sub) {
                        item.prev_stream = $t({defaultMessage: "Unknown stream"});
                    } else {
                        item.prev_stream = sub_store.maybe_get_stream_name(msg.prev_stream);
                    }
                    if (prev_stream_item !== null) {
                        prev_stream_item.new_stream = sub_store.maybe_get_stream_name(
                            msg.prev_stream,
                        );
                    }
                    prev_stream_item = item;
                } else {
                    // just a content edit
                    item.edited_by_notice = $t(
                        {defaultMessage: "Edited by {full_name}"},
                        {full_name},
                    );
                    item.body_to_render = msg.content_html_diff;
                }

                content_edit_history.push(item);
                prev_time = time;
            }
            if (prev_stream_item !== null) {
                prev_stream_item.new_stream = sub_store.maybe_get_stream_name(message.stream_id);
            }
            $("#message-history").attr("data-message-id", message.id);
            $("#message-history").html(
                render_message_edit_history({
                    edited_messages: content_edit_history,
                }),
            );
            // Pass the history through rendered_markdown.js
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

export function show_history(message) {
    const rendered_message_history = render_message_history_modal();

    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Message edit history"}),
        html_body: rendered_message_history,
        html_submit_button: $t_html({defaultMessage: "Close"}),
        id: "message-edit-history",
        on_click() {},
        close_on_submit: true,
        focus_submit_on_open: true,
        single_footer_button: true,
        post_render() {
            fetch_and_render_message_history(message);
        },
    });
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
        e.stopPropagation();
        e.preventDefault();
        popovers.hide_all();

        const message_id = rows.id($(e.currentTarget).closest(".message_row"));
        const $row = message_lists.current.get_row(message_id);
        const message = message_lists.current.get(rows.id($row));

        if (page_params.is_spectator) {
            spectators.login_to_access();
            return;
        }

        if (page_params.realm_allow_edit_history) {
            show_history(message);
            $("#message-history-cancel").trigger("focus");
        }
    });
}
