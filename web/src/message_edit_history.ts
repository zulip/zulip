import $ from "jquery";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import render_message_edit_history from "../templates/message_edit_history.hbs";
import render_message_history_overlay from "../templates/message_history_overlay.hbs";

import {exit_overlay} from "./browser_history.ts";
import * as channel from "./channel.ts";
import {by_stream_topic_url} from "./hash_util.ts";
import {$t, $t_html} from "./i18n.ts";
import * as loading from "./loading.ts";
import * as message_lists from "./message_lists.ts";
import type {Message} from "./message_store.ts";
import * as messages_overlay_ui from "./messages_overlay_ui.ts";
import * as overlays from "./overlays.ts";
import {page_params} from "./page_params.ts";
import * as people from "./people.ts";
import * as rendered_markdown from "./rendered_markdown.ts";
import {is_resolved, unresolve_name} from "./resolved_topic.ts";
import * as rows from "./rows.ts";
import {message_edit_history_visibility_policy_values} from "./settings_config.ts";
import * as spectators from "./spectators.ts";
import {realm} from "./state_data.ts";
import {get_recipient_bar_color} from "./stream_color.ts";
import {get_color} from "./stream_data.ts";
import * as sub_store from "./sub_store.ts";
import * as submessage from "./submessage.ts";
import * as timerender from "./timerender.ts";
import * as ui_report from "./ui_report.ts";
import * as util from "./util.ts";

type EditHistoryEntry = {
    initial_entry_for_move_history: boolean;
    edited_at_time: string;
    edited_by_notice: string;
    timestamp: number; // require to set data-message-id for overlay message row
    is_stream: boolean;
    recipient_bar_color: string | undefined;
    body_to_render: string | undefined;
    topic_edited: boolean | undefined;
    prev_topic_display_name: string | undefined;
    new_topic_display_name: string | undefined;
    is_empty_string_prev_topic: boolean | undefined;
    is_empty_string_new_topic: boolean | undefined;
    stream_changed: boolean | undefined;
    prev_stream: string | undefined;
    prev_stream_id: number | undefined;
    prev_stream_sub: sub_store.StreamSubscription | undefined;
    new_stream: string | undefined;
    new_stream_sub: sub_store.StreamSubscription | undefined;
    prev_stream_topic_url: string | undefined;
    new_stream_topic_url: string | undefined;
    topic_resolved_or_unresolved: "resolved" | "unresolved" | "none";
};

const server_message_history_schema = z.object({
    message_history: z.array(
        z.object({
            content: z.string(),
            rendered_content: z.string(),
            timestamp: z.number(),
            topic: z.string(),
            user_id: z.nullable(z.number()),
            prev_topic: z.optional(z.string()),
            stream: z.optional(z.number()),
            prev_stream: z.optional(z.number()),
            prev_content: z.optional(z.string()),
            prev_rendered_content: z.optional(z.string()),
            content_html_diff: z.optional(z.string()),
        }),
    ),
});

type ServerMessageHistoryData = z.infer<typeof server_message_history_schema>;
type ServerMessageHistoryEntry = ServerMessageHistoryData["message_history"][number];

// This will be used to handle up and down keyws
const keyboard_handling_context: messages_overlay_ui.Context = {
    items_container_selector: "message-edit-history-container",
    items_list_selector: "message-edit-history-list",
    row_item_selector: "message-edit-message-row",
    box_item_selector: "message-edit-message-info-box",
    id_attribute_name: "data-message-edit-history-id",
    get_items_ids() {
        const edited_messages_ids: string[] = [];
        const $message_history_list: JQuery = $(
            "#message-history-overlay .message-edit-history-list",
        );
        for (const message of $message_history_list.children()) {
            const data_message_edit_history_id = $(message).attr("data-message-edit-history-id");
            assert(data_message_edit_history_id !== undefined);
            edited_messages_ids.push(data_message_edit_history_id);
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

function get_topic_change_fields(
    server_entry: ServerMessageHistoryEntry,
): Pick<
    EditHistoryEntry,
    | "topic_edited"
    | "prev_topic_display_name"
    | "new_topic_display_name"
    | "is_empty_string_prev_topic"
    | "is_empty_string_new_topic"
    | "new_stream"
    | "new_stream_sub"
    | "prev_stream"
    | "prev_stream_sub"
    | "prev_stream_topic_url"
    | "new_stream_topic_url"
    | "stream_changed"
    | "prev_stream_id"
> {
    assert(server_entry.prev_topic !== undefined);

    const base_params = {
        topic_edited: true,
        prev_topic_display_name: util.get_final_topic_display_name(server_entry.prev_topic),
        new_topic_display_name: util.get_final_topic_display_name(server_entry.topic),
        is_empty_string_prev_topic: server_entry.prev_topic === "",
        is_empty_string_new_topic: server_entry.topic === "",
    };

    if (server_entry.prev_stream) {
        const prev_stream_id = server_entry.prev_stream;
        const new_stream_id = server_entry.stream;
        assert(new_stream_id !== undefined);
        return {
            ...base_params,
            stream_changed: true,
            prev_stream_id,
            prev_stream: get_display_stream_name(server_entry.prev_stream),
            prev_stream_sub: sub_store.get(prev_stream_id),
            prev_stream_topic_url: by_stream_topic_url(prev_stream_id, server_entry.prev_topic),
            new_stream: get_display_stream_name(new_stream_id),
            new_stream_sub: sub_store.get(new_stream_id),
            new_stream_topic_url: by_stream_topic_url(new_stream_id, server_entry.topic),
        };
    }

    // For topic-only moves and content+topic edits: stream and URL info is
    // computed in the reverse-chronological pass once we know the stream
    // context for each historical event.
    return {
        ...base_params,
        stream_changed: undefined,
        prev_stream_id: undefined,
        prev_stream: undefined,
        prev_stream_sub: undefined,
        new_stream: undefined,
        new_stream_sub: undefined,
        prev_stream_topic_url: undefined,
        new_stream_topic_url: undefined,
    };
}

function build_initial_entry(
    server_entry: ServerMessageHistoryEntry,
    full_name: string,
    move_history_only: boolean,
): Partial<EditHistoryEntry> {
    if (move_history_only) {
        return {
            edited_by_notice: $t({defaultMessage: "Posted by {full_name}"}, {full_name}),
            initial_entry_for_move_history: true,
            new_topic_display_name: util.get_final_topic_display_name(server_entry.topic),
        };
    }

    return {
        edited_by_notice: $t({defaultMessage: "Posted by {full_name}"}, {full_name}),
        body_to_render: server_entry.rendered_content,
    };
}

function build_topic_and_content_edit_entry(
    server_entry: ServerMessageHistoryEntry,
    full_name: string,
): Partial<EditHistoryEntry> {
    return {
        edited_by_notice: $t({defaultMessage: "Edited by {full_name}"}, {full_name}),
        body_to_render: server_entry.content_html_diff,
        ...get_topic_change_fields(server_entry),
    };
}

function build_topic_and_stream_move_entry(
    server_entry: ServerMessageHistoryEntry,
    full_name: string,
): Partial<EditHistoryEntry> {
    assert(server_entry.prev_stream !== undefined);

    return {
        edited_by_notice: $t({defaultMessage: "Moved by {full_name}"}, {full_name}),
        ...get_topic_change_fields(server_entry),
    };
}

function build_topic_move_entry(
    server_entry: ServerMessageHistoryEntry,
    full_name: string,
): Partial<EditHistoryEntry> {
    let edited_by_notice = $t({defaultMessage: "Moved by {full_name}"}, {full_name});
    assert(server_entry.prev_topic !== undefined);
    let topic_resolved_or_unresolved: "resolved" | "unresolved" | "none" = "none";
    const prev_topic_resolved = is_resolved(server_entry.prev_topic);
    const current_topic_resolved = is_resolved(server_entry.topic);
    // Only treat this as a resolve/unresolve toggle when the base topic name
    // (stripped of the resolved prefix) is unchanged; otherwise it's a rename
    // that also happened to add/remove the prefix.
    if (
        prev_topic_resolved !== current_topic_resolved &&
        unresolve_name(server_entry.prev_topic) === unresolve_name(server_entry.topic)
    ) {
        if (current_topic_resolved) {
            topic_resolved_or_unresolved = "resolved";
            edited_by_notice = $t({defaultMessage: "Topic resolved by {full_name}"}, {full_name});
        } else {
            topic_resolved_or_unresolved = "unresolved";
            edited_by_notice = $t({defaultMessage: "Topic unresolved by {full_name}"}, {full_name});
        }
    }
    return {
        edited_by_notice,
        topic_resolved_or_unresolved,
        ...get_topic_change_fields(server_entry),
    };
}

function build_stream_move_entry(
    server_entry: ServerMessageHistoryEntry,
    full_name: string,
): Partial<EditHistoryEntry> {
    assert(server_entry.prev_stream !== undefined);
    const new_stream_id = server_entry.stream;
    assert(new_stream_id !== undefined);

    return {
        edited_by_notice: $t({defaultMessage: "Moved by {full_name}"}, {full_name}),
        stream_changed: true,
        prev_stream_id: server_entry.prev_stream,
        prev_stream: get_display_stream_name(server_entry.prev_stream),
        prev_stream_sub: sub_store.get(server_entry.prev_stream),
        new_stream: get_display_stream_name(new_stream_id),
        new_stream_sub: sub_store.get(new_stream_id),
    };
}

function build_content_edit_entry(
    server_entry: ServerMessageHistoryEntry,
    full_name: string,
): Partial<EditHistoryEntry> {
    return {
        edited_by_notice: $t({defaultMessage: "Edited by {full_name}"}, {full_name}),
        body_to_render: server_entry.content_html_diff,
    };
}

function make_edit_history_entry(
    server_entry: ServerMessageHistoryEntry,
    edited_at_time: string,
    is_stream: boolean,
    entry_data: Partial<EditHistoryEntry>,
): EditHistoryEntry {
    return {
        initial_entry_for_move_history: false,
        edited_at_time,
        edited_by_notice: "",
        timestamp: server_entry.timestamp,
        is_stream,
        recipient_bar_color: undefined,
        body_to_render: undefined,
        topic_edited: undefined,
        prev_topic_display_name: undefined,
        new_topic_display_name: undefined,
        is_empty_string_prev_topic: undefined,
        is_empty_string_new_topic: undefined,
        stream_changed: undefined,
        prev_stream: undefined,
        prev_stream_id: undefined,
        prev_stream_sub: undefined,
        new_stream: undefined,
        new_stream_sub: undefined,
        prev_stream_topic_url: undefined,
        new_stream_topic_url: undefined,
        topic_resolved_or_unresolved: "none",
        ...entry_data,
    };
}

export function fetch_and_render_message_history(message: Message): void {
    assert(message_lists.current !== undefined);
    const message_container = message_lists.current.view.message_containers.get(message.id);
    assert(message_container !== undefined);
    const move_history_only =
        realm.realm_message_edit_history_visibility_policy ===
        message_edit_history_visibility_policy_values.moves_only.code;
    $("#message-edit-history-overlay-container").html(
        render_message_history_overlay({
            moved: message_container.moved,
            edited: message_container.edited,
            move_history_only,
        }),
    );
    $("#message-edit-history-overlay-container").attr("data-message-id", message.id);
    open_overlay();
    show_loading_indicator();
    void channel.get({
        url: "/json/messages/" + message.id + "/history",
        data: {
            message_id: JSON.stringify(message.id),
            allow_empty_topic_name: true,
        },
        success(raw_data) {
            if (
                !overlays.message_edit_history_open() ||
                $("#message-edit-history-overlay-container").attr("data-message-id") !==
                    String(message.id)
            ) {
                return;
            }
            const data = server_message_history_schema.parse(raw_data);

            const content_edit_history: EditHistoryEntry[] = [];

            for (const [index, server_entry] of data.message_history.entries()) {
                // Format times and dates nicely for display
                const time = new Date(server_entry.timestamp * 1000);
                const edited_at_time = timerender.get_full_datetime(time, "time");

                if (!server_entry.user_id) {
                    continue;
                }

                const person = people.get_user_by_id_assert_valid(server_entry.user_id);
                const full_name = person.full_name;

                let entry_data: Partial<EditHistoryEntry>;
                if (index === 0) {
                    entry_data = build_initial_entry(server_entry, full_name, move_history_only);
                } else if (server_entry.prev_topic !== undefined && server_entry.prev_content) {
                    entry_data = build_topic_and_content_edit_entry(server_entry, full_name);
                } else if (server_entry.prev_topic !== undefined && server_entry.prev_stream) {
                    entry_data = build_topic_and_stream_move_entry(server_entry, full_name);
                } else if (server_entry.prev_topic !== undefined) {
                    entry_data = build_topic_move_entry(server_entry, full_name);
                } else if (server_entry.prev_stream) {
                    entry_data = build_stream_move_entry(server_entry, full_name);
                } else {
                    entry_data = build_content_edit_entry(server_entry, full_name);
                }
                const item = make_edit_history_entry(
                    server_entry,
                    edited_at_time,
                    message.is_stream,
                    entry_data,
                );

                content_edit_history.push(item);
            }

            // In order to correctly compute the recipient_bar_color values and entries for topic
            // only moves, it is convenient to iterate through the array of edit history
            // entries in reverse chronological order.
            if (message.is_stream) {
                // Start with the message's current location.
                let current_stream_id = message.stream_id;
                // Track the topic in effect at the time of each historical event.
                // Going backwards, we step current_topic back whenever a topic
                // rename is encountered, just as we step current_stream_id back
                // for stream moves.
                let current_topic = message.topic;
                let stream_display_name: string = get_display_stream_name(message.stream_id);
                let stream_color: string = get_color(message.stream_id);
                let recipient_bar_color: string = get_recipient_bar_color(stream_color);
                // Iterate in reverse chronological order so we can track which
                // stream and topic the message was in at the time of each event.
                for (const edit_history_entry of content_edit_history.toReversed()) {
                    // The stream following this move is the one whose color we already have.
                    edit_history_entry.recipient_bar_color = recipient_bar_color;
                    if (edit_history_entry.stream_changed) {
                        // Immediately prior to this event the message was in
                        // prev_stream_id; capture the post-move stream before updating.
                        const new_stream_id = current_stream_id;
                        assert(edit_history_entry.prev_stream_id !== undefined);
                        stream_display_name = get_display_stream_name(
                            edit_history_entry.prev_stream_id,
                        );
                        stream_color = get_color(edit_history_entry.prev_stream_id);
                        recipient_bar_color = get_recipient_bar_color(stream_color);
                        current_stream_id = edit_history_entry.prev_stream_id;
                        if (!edit_history_entry.topic_edited) {
                            // Stream-only move: the topic did not change in this event,
                            // so the topic on both sides is current_topic (the topic in
                            // effect at this point in history, already stepped back past
                            // any later topic renames).
                            const topic = current_topic;
                            edit_history_entry.new_topic_display_name =
                                util.get_final_topic_display_name(topic);
                            edit_history_entry.prev_topic_display_name =
                                util.get_final_topic_display_name(topic);
                            edit_history_entry.is_empty_string_new_topic = topic === "";
                            edit_history_entry.is_empty_string_prev_topic = topic === "";
                            edit_history_entry.prev_stream_sub = sub_store.get(current_stream_id);
                            edit_history_entry.prev_stream_topic_url = by_stream_topic_url(
                                current_stream_id,
                                topic,
                            );
                            edit_history_entry.new_stream_sub = sub_store.get(new_stream_id);
                            edit_history_entry.new_stream_topic_url = by_stream_topic_url(
                                new_stream_id,
                                topic,
                            );
                        }
                    }
                    // After processing a topic-editing event, step current_topic back
                    // to what it was immediately before this event.
                    if (edit_history_entry.topic_edited) {
                        assert(edit_history_entry.prev_topic_display_name !== undefined);
                        current_topic =
                            edit_history_entry.is_empty_string_prev_topic === true
                                ? ""
                                : edit_history_entry.prev_topic_display_name;
                    }
                    if (edit_history_entry.topic_edited && !edit_history_entry.stream_changed) {
                        // Topic-only and content+topic edits: now that we know the
                        // stream context, fill in stream names and generate URLs.
                        // Use is_empty_string_* to recover the raw topic since
                        // display names differ from raw topics for empty-string topics.
                        const stream_sub = sub_store.get(current_stream_id);
                        edit_history_entry.prev_stream = stream_display_name;
                        edit_history_entry.prev_stream_sub = stream_sub;
                        edit_history_entry.new_stream = stream_display_name;
                        edit_history_entry.new_stream_sub = stream_sub;
                        assert(edit_history_entry.prev_topic_display_name !== undefined);
                        assert(edit_history_entry.new_topic_display_name !== undefined);
                        const prev_topic_raw =
                            edit_history_entry.is_empty_string_prev_topic === true
                                ? ""
                                : edit_history_entry.prev_topic_display_name;
                        const new_topic_raw =
                            edit_history_entry.is_empty_string_new_topic === true
                                ? ""
                                : edit_history_entry.new_topic_display_name;
                        edit_history_entry.prev_stream_topic_url = by_stream_topic_url(
                            current_stream_id,
                            prev_topic_raw,
                        );
                        edit_history_entry.new_stream_topic_url = by_stream_topic_url(
                            current_stream_id,
                            new_topic_raw,
                        );
                    }
                }
                if (move_history_only) {
                    // If message history is limited to moves only, then we
                    // display the original topic and channel for the message.
                    content_edit_history[0]!.new_stream = stream_display_name;
                    content_edit_history[0]!.new_stream_sub = sub_store.get(current_stream_id);
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

            // When an image is deleted before thumbnailing is completed, we can
            // end up with the loading spinner HTML syntax stuck in message edit
            // history indefinitely. Mask this by replacing thumbnailing loading
            // spinners in edit history with the deleted image placeholder.
            $("#message-history-overlay")
                .find("img.image-loading-placeholder")
                .each(function () {
                    const $img = $(this);
                    $img.attr("src", "/static/images/errors/image-not-exist.png");
                    $img.attr(
                        "alt",
                        $t({defaultMessage: "This file does not exist or has been deleted."}),
                    );
                    $img.removeClass("image-loading-placeholder");
                });

            const first_element_id = content_edit_history[0]!.timestamp;
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
    $("body").on(
        "mouseenter",
        ".message_edit_notice, .edit-notifications.has-edit-history",
        (e) => {
            if (
                realm.realm_message_edit_history_visibility_policy !==
                message_edit_history_visibility_policy_values.never.code
            ) {
                $(e.currentTarget).addClass("message_edit_notice_hover");
            }
        },
    );

    $("body").on(
        "mouseleave",
        ".message_edit_notice, .edit-notifications.has-edit-history",
        (e) => {
            if (
                realm.realm_message_edit_history_visibility_policy !==
                message_edit_history_visibility_policy_values.never.code
            ) {
                $(e.currentTarget).removeClass("message_edit_notice_hover");
            }
        },
    );

    $("body").on(
        "click",
        ".message_edit_notice, .edit-notifications.has-edit-history",
        function (this: HTMLElement, e) {
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

            // Poll messages can show an EDITED marker for widget edits
            // (question changes, new options) that have no server-side
            // edit history. Skip the overlay when the message has no
            // text edits or moves to display.
            if (
                submessage.is_poll_message(message) &&
                message.last_edit_timestamp === undefined &&
                message.last_moved_timestamp === undefined
            ) {
                return;
            }

            if (
                realm.realm_message_edit_history_visibility_policy ===
                    message_edit_history_visibility_policy_values.always.code ||
                (realm.realm_message_edit_history_visibility_policy ===
                    message_edit_history_visibility_policy_values.moves_only.code &&
                    message.last_moved_timestamp !== undefined)
            ) {
                fetch_and_render_message_history(message);
                $("#message-history-overlay .exit-sign").trigger("focus");
            }
        },
    );

    $("body").on(
        "focus",
        "#message-history-overlay .overlay-message-info-box",
        function (this: HTMLElement) {
            messages_overlay_ui.activate_element(this, keyboard_handling_context);
        },
    );

    $("body").on("click", "#message-history-overlay .message_edit_history_content", (e) => {
        messages_overlay_ui.handle_overlay_media_click(e, "message_edit_history");
    });
}
