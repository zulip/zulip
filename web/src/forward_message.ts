import $ from "jquery";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import render_forward_message from "../templates/forward_message.hbs";

import * as channel from "./channel.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as feedback_widget from "./feedback_widget.ts";
import * as fenced_code from "./fenced_code.ts";
import * as hash_util from "./hash_util.ts";
import {$t, $t_html} from "./i18n.ts";
import * as message_lists from "./message_lists.ts";
import type {Message} from "./message_store.ts";
import * as people from "./people.ts";
import * as pm_conversations from "./pm_conversations.ts";
import * as sent_messages from "./sent_messages.ts";
import * as server_events_state from "./server_events_state.ts";
import {current_user} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import type {StreamSubscription} from "./sub_store.ts";
import * as transmit from "./transmit.ts";
import * as ui_report from "./ui_report.ts";
import * as util from "./util.ts";

// A WhatsApp/Telegram-style "Forward to…" experience for the message
// actions menu. Unlike the upstream forward flow (which re-uses the
// compose box and defaults to the same conversation), this opens a
// dedicated modal where the user picks one or more destinations —
// channels (with a topic), task channels, and direct messages — and
// the message is forwarded to each via the standard send pipeline.

const MODAL_ID = "forward_message_modal";
// Cap how many people we render at once; search reveals the rest.
const PEOPLE_RENDER_CAP = 50;

export type StreamDestination = {
    kind: "stream";
    key: string;
    stream_id: number;
    name: string;
    topic: string;
};

export type DmDestination = {
    kind: "private";
    key: string;
    user_ids: number[];
    label: string;
};

export type Destination = StreamDestination | DmDestination;

// Mirrors the (non-exported) SendMessageData shape consumed by
// transmit.send_message; structurally assignable to it.
type SendRequest =
    | {
          type: "stream";
          local_id: string;
          sender_id: number;
          queue_id: string | null;
          to: string;
          content: string;
          topic: string;
      }
    | {
          type: "private";
          local_id: string;
          sender_id: number;
          queue_id: string | null;
          to: string;
          content: string;
      };

let selected_destinations = new Map<string, Destination>();
let source_message: Message | undefined;
let default_forward_topic = "";

function stream_key(stream_id: number): string {
    return `stream:${stream_id}`;
}

function dm_key(user_ids: number[]): string {
    return `dm:${[...user_ids].sort((a, b) => a - b).join(",")}`;
}

function get_val($el: JQuery): string {
    const value = $el.val();
    return typeof value === "string" ? value : "";
}

function dm_label(user_ids: number[]): string {
    const names = user_ids.map((user_id) => {
        const full_name = people.get_by_user_id(user_id).full_name;
        if (people.is_my_user_id(user_id)) {
            return $t({defaultMessage: "{name} (you)"}, {name: full_name});
        }
        return full_name;
    });
    return names.join(", ");
}

export function build_forward_content(
    message: {sender_full_name: string; sender_id: number},
    link_to_message: string,
    raw_content: string,
    comment: string,
): string {
    // Final message looks like:
    //     <optional comment>
    //
    //     *Forwarded from* @_**Iago|5** ([original](link)):
    //     ```quote
    //     message content
    //     ```
    // The mention is "silent" (@_), so the original sender is not notified.
    const fence = fenced_code.get_unused_fence(raw_content);
    const attribution = $t(
        {defaultMessage: "*Forwarded from* {sender} ([original]({link_to_message})):"},
        {
            sender: `@_**${message.sender_full_name}|${message.sender_id}**`,
            link_to_message,
        },
    );

    let content = "";
    const trimmed_comment = comment.trim();
    if (trimmed_comment !== "") {
        content += `${trimmed_comment}\n\n`;
    }
    content += `${attribution}\n`;
    content += `${fence}quote\n${raw_content}\n${fence}`;
    return content;
}

export function build_send_request(
    dest: Destination,
    content: string,
    local_id: string,
    sender_id: number,
    queue_id: string | null,
): SendRequest {
    const base = {local_id, sender_id, queue_id, content};
    if (dest.kind === "stream") {
        return {
            type: "stream",
            ...base,
            to: JSON.stringify([dest.stream_id]),
            topic: dest.topic,
        };
    }
    return {
        type: "private",
        ...base,
        to: JSON.stringify(dest.user_ids),
    };
}

function send_to_destination(dest: Destination, content: string): Promise<void> {
    return new Promise((resolve, reject) => {
        const request = build_send_request(
            dest,
            content,
            sent_messages.get_new_local_id(),
            current_user.user_id,
            server_events_state.queue_id,
        );
        transmit.send_message(
            request,
            () => {
                resolve();
            },
            (response: string) => {
                reject(new Error(response));
            },
        );
    });
}

function with_raw_content(
    message: Message,
    on_success: (raw_content: string) => void,
    on_error: () => void,
): void {
    if (message.raw_content !== undefined) {
        on_success(message.raw_content);
        return;
    }
    void channel.get({
        url: "/json/messages/" + message.id,
        data: {allow_empty_topic_name: true},
        success(raw_data) {
            const data = z.object({raw_content: z.string()}).parse(raw_data);
            on_success(data.raw_content);
        },
        error() {
            on_error();
        },
    });
}

function show_success_feedback(count: number): void {
    feedback_widget.show({
        populate($container) {
            $container.text(
                $t(
                    {
                        defaultMessage:
                            "Forwarded to {count, plural, one {# conversation} other {# conversations}}.",
                    },
                    {count},
                ),
            );
        },
        title_text: $t({defaultMessage: "Message forwarded"}),
        hide_delay: 4000,
    });
}

function show_forward_error(failed: number, total: number): void {
    ui_report.client_error(
        $t_html(
            {
                defaultMessage:
                    "Failed to forward the message to {failed} of {total} conversations.",
            },
            {failed, total},
        ),
        $(`#${MODAL_ID} #dialog_error`),
    );
}

function can_submit(): boolean {
    if (selected_destinations.size === 0) {
        return false;
    }
    for (const dest of selected_destinations.values()) {
        if (dest.kind === "stream") {
            const topic_ok =
                dest.topic.trim() !== "" || stream_data.can_use_empty_topic(dest.stream_id);
            if (!topic_ok) {
                return false;
            }
        }
    }
    return true;
}

function update_submit_disabled(): void {
    $(`#${MODAL_ID} .dialog_submit_button`).prop("disabled", !can_submit());
}

function make_section_header(text: string): JQuery {
    return $("<div>").addClass("forward-section-header").text(text);
}

function make_stream_row(sub: StreamSubscription): JQuery {
    const $row = $("<div>")
        .addClass("forward-row")
        .attr({"data-kind": "stream", "data-stream-id": String(sub.stream_id)});
    if (selected_destinations.has(stream_key(sub.stream_id))) {
        $row.addClass("selected");
    }
    $row.append($("<span>").addClass("forward-row-icon").text("#"));
    $row.append($("<span>").addClass("forward-row-label").text(sub.name));
    return $row;
}

function make_dm_row(user_ids: number[], label: string): JQuery {
    const $row = $("<div>")
        .addClass("forward-row")
        .attr({"data-kind": "private", "data-user-ids": user_ids.join(",")});
    if (selected_destinations.has(dm_key(user_ids))) {
        $row.addClass("selected");
    }
    $row.append($("<span>").addClass("forward-row-icon").text("@"));
    $row.append($("<span>").addClass("forward-row-label").text(label));
    return $row;
}

function render_destinations(query: string): void {
    const q = query.trim().toLowerCase();
    const $list = $("#forward-destinations").empty();

    // Recent direct messages (1:1 and group), most recent first.
    const recent_rows: JQuery[] = [];
    for (const conversation of pm_conversations.recent.get()) {
        const user_ids = people.user_ids_string_to_ids_array(conversation.user_ids_string);
        if (user_ids.length === 0) {
            continue;
        }
        const label = dm_label(user_ids);
        if (q !== "" && !label.toLowerCase().includes(q)) {
            continue;
        }
        recent_rows.push(make_dm_row(user_ids, label));
    }
    if (recent_rows.length > 0) {
        $list.append(make_section_header($t({defaultMessage: "Recent direct messages"})));
        for (const $row of recent_rows) {
            $list.append($row);
        }
    }

    // Channels the user can post to.
    const channels = stream_data
        .subscribed_subs()
        .filter((sub) => !sub.is_archived && stream_data.can_post_messages_in_stream(sub))
        .filter((sub) => q === "" || sub.name.toLowerCase().includes(q))
        .toSorted((a, b) => util.strcmp(a.name.toLowerCase(), b.name.toLowerCase()));
    if (channels.length > 0) {
        $list.append(make_section_header($t({defaultMessage: "Channels"})));
        for (const sub of channels) {
            $list.append(make_stream_row(sub));
        }
    }

    // People (for new direct messages).
    const humans = people
        .get_realm_active_human_users()
        .filter((user) => q === "" || user.full_name.toLowerCase().includes(q))
        .toSorted((a, b) => util.strcmp(a.full_name.toLowerCase(), b.full_name.toLowerCase()))
        .slice(0, PEOPLE_RENDER_CAP);
    if (humans.length > 0) {
        $list.append(make_section_header($t({defaultMessage: "People"})));
        for (const user of humans) {
            $list.append(make_dm_row([user.user_id], user.full_name));
        }
    }

    if ($list.children().length === 0) {
        $list.append(
            $("<div>")
                .addClass("forward-empty")
                .text($t({defaultMessage: "No matching conversations."})),
        );
    }
}

function render_selected(): void {
    const $selected = $("#forward-selected").empty();
    if (selected_destinations.size === 0) {
        $selected.hide();
        return;
    }
    $selected.show();
    for (const dest of selected_destinations.values()) {
        const $item = $("<div>").addClass("forward-selected-item");
        if (dest.kind === "stream") {
            $item.append($("<span>").addClass("forward-selected-name").text("#" + dest.name));
            $item.append(
                $("<input>")
                    .attr({
                        type: "text",
                        "data-key": dest.key,
                        placeholder: $t({defaultMessage: "topic"}),
                    })
                    .addClass("forward-topic-input modal_text_input")
                    .val(dest.topic),
            );
        } else {
            $item.append($("<span>").addClass("forward-selected-name").text(dest.label));
        }
        $item.append(
            $("<button>")
                .attr({
                    type: "button",
                    "data-key": dest.key,
                    "aria-label": $t({defaultMessage: "Remove"}),
                })
                .addClass("forward-remove")
                .text("×"),
        );
        $selected.append($item);
    }
}

function refresh(): void {
    render_destinations(get_val($("#forward-search")));
    render_selected();
    update_submit_disabled();
}

function toggle_destination($row: JQuery): void {
    const kind = $row.attr("data-kind");
    if (kind === "stream") {
        const stream_id = Number($row.attr("data-stream-id"));
        const key = stream_key(stream_id);
        if (selected_destinations.has(key)) {
            selected_destinations.delete(key);
        } else {
            const sub = stream_data.get_sub_by_id(stream_id);
            if (sub === undefined) {
                return;
            }
            selected_destinations.set(key, {
                kind: "stream",
                key,
                stream_id,
                name: sub.name,
                topic: default_forward_topic,
            });
        }
    } else {
        const user_ids = ($row.attr("data-user-ids") ?? "")
            .split(",")
            .map((id) => Number(id))
            .filter((id) => !Number.isNaN(id));
        if (user_ids.length === 0) {
            return;
        }
        const key = dm_key(user_ids);
        if (selected_destinations.has(key)) {
            selected_destinations.delete(key);
        } else {
            selected_destinations.set(key, {
                kind: "private",
                key,
                user_ids,
                label: dm_label(user_ids),
            });
        }
    }
    refresh();
}

function do_forward(): void {
    assert(source_message !== undefined);
    const message = source_message;
    const comment = get_val($("#forward-comment"));
    const destinations = [...selected_destinations.values()];

    with_raw_content(
        message,
        (raw_content) => {
            const content = build_forward_content(
                message,
                hash_util.by_conversation_and_time_url(message),
                raw_content,
                comment,
            );
            void Promise.allSettled(
                destinations.map((dest) => send_to_destination(dest, content)),
            ).then((results) => {
                const failed = results.filter((result) => result.status === "rejected").length;
                if (failed === 0) {
                    dialog_widget.close();
                    show_success_feedback(destinations.length);
                } else {
                    dialog_widget.hide_dialog_spinner();
                    show_forward_error(failed, destinations.length);
                }
            });
        },
        () => {
            dialog_widget.hide_dialog_spinner();
            show_forward_error(destinations.length, destinations.length);
        },
    );
}

export function show(opts: {message_id: number}): void {
    if (message_lists.current === undefined) {
        return;
    }
    const message = message_lists.current.get(opts.message_id);
    if (message === undefined) {
        return;
    }

    source_message = message;
    selected_destinations = new Map();
    default_forward_topic = message.is_stream ? message.topic : "";

    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Forward message"}),
        html_body: render_forward_message(),
        html_submit_button: $t_html({defaultMessage: "Forward"}),
        id: MODAL_ID,
        loading_spinner: true,
        close_on_submit: false,
        validate_input: () => can_submit(),
        on_click() {
            do_forward();
        },
        post_render() {
            render_destinations("");
            render_selected();
            update_submit_disabled();

            $("#forward-search").on("input", function () {
                render_destinations(get_val($(this)));
            });
            $("#forward-destinations").on("click", ".forward-row", function () {
                toggle_destination($(this));
            });
            $("#forward-selected").on("click", ".forward-remove", function () {
                const key = $(this).attr("data-key");
                if (key !== undefined) {
                    selected_destinations.delete(key);
                    refresh();
                }
            });
            $("#forward-selected").on("input", ".forward-topic-input", function () {
                const key = $(this).attr("data-key");
                const dest = key === undefined ? undefined : selected_destinations.get(key);
                if (dest?.kind === "stream") {
                    dest.topic = get_val($(this));
                    update_submit_disabled();
                }
            });
        },
        on_hidden() {
            selected_destinations = new Map();
            source_message = undefined;
        },
    });
}
