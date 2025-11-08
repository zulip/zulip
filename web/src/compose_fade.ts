import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";

import * as compose_fade_helper from "./compose_fade_helper.ts";
import * as compose_state from "./compose_state.ts";
import type {MessageGroup} from "./message_list_view.ts";
import * as message_lists from "./message_lists.ts";
import * as message_viewport from "./message_viewport.ts";
import * as people from "./people.ts";
import * as rows from "./rows.ts";
import * as util from "./util.ts";

let normal_display = false;

export function set_focused_recipient(msg_type?: "private" | "stream"): void {
    if (msg_type === undefined) {
        compose_fade_helper.clear_focused_recipient();
    }

    // Construct focused_recipient as a mocked up element which has all the
    // fields of a message used by util.same_recipient()
    let focused_recipient;
    if (msg_type === "stream") {
        const stream_id = compose_state.stream_id();
        const topic = compose_state.topic();
        if (stream_id) {
            focused_recipient = {
                type: msg_type,
                stream_id,
                topic,
            };
        }
    } else if (msg_type === "private") {
        // Normalize the recipient list so it matches the one used when
        // adding the message (see message_helper.process_new_message()).
        const reply_to = util.normalize_recipients(
            compose_state.private_message_recipient_emails(),
        );
        const to_user_ids = people.reply_to_to_user_ids_string(reply_to);
        focused_recipient = {
            type: msg_type,
            reply_to,
            to_user_ids,
        };
    }

    compose_fade_helper.set_focused_recipient(focused_recipient);
}

function display_messages_normally(): void {
    message_lists.current?.view.$list.find(".recipient_row").removeClass("message-fade");

    normal_display = true;
}

function change_fade_state($elt: JQuery, should_fade_group: boolean): void {
    if (should_fade_group) {
        $elt.addClass("message-fade");
    } else {
        $elt.removeClass("message-fade");
    }
}

function fade_messages(): void {
    if (message_lists.current === undefined) {
        return;
    }

    normal_display = false;

    // Update the visible messages first, before the compose box opens
    for (const group_elt of message_viewport.visible_groups(false)) {
        const $first_row = rows.first_message_in_group($(group_elt));
        const first_message = message_lists.current.get(rows.id($first_row));
        assert(first_message !== undefined);
        const should_fade_group = compose_fade_helper.should_fade_message(first_message);

        change_fade_state($(group_elt), should_fade_group);
    }

    // Defer updating all message groups so that the compose box can open sooner
    setTimeout(
        (expected_msg_list, expected_recipient) => {
            if (
                message_lists.current !== expected_msg_list ||
                !compose_state.composing() ||
                compose_state.private_message_recipient_emails() !== expected_recipient
            ) {
                return;
            }

            const $all_groups = message_lists.current.view.$list.find(".recipient_row");
            // Note: The below algorithm relies on the fact that all_elts is
            // sorted as it would be displayed in the message view
            for (const group_elt of $all_groups) {
                const $group_elt = $(group_elt);
                const should_fade_group = compose_fade_helper.should_fade_message(
                    rows.recipient_from_group($group_elt)!,
                );
                change_fade_state($group_elt, should_fade_group);
            }
        },
        0,
        message_lists.current,
        compose_state.private_message_recipient_emails(),
    );
}

export function do_update_all(): void {
    if (compose_fade_helper.want_normal_display()) {
        if (!normal_display) {
            display_messages_normally();
        }
    } else {
        fade_messages();
    }
}

// This gets called on keyup events, hence the throttling.
export const update_all = _.debounce(do_update_all, 50);

export function start_compose(msg_type?: "private" | "stream"): void {
    set_focused_recipient(msg_type);
    do_update_all();
}

export function clear_compose(): void {
    compose_fade_helper.clear_focused_recipient();
    display_messages_normally();
}

export function update_message_list(): void {
    if (compose_fade_helper.want_normal_display()) {
        display_messages_normally();
    } else {
        fade_messages();
    }
}

export function update_rendered_message_groups(
    message_groups: MessageGroup[],
    get_element: (message_group: MessageGroup) => JQuery,
): void {
    if (compose_fade_helper.want_normal_display()) {
        return;
    }

    // This loop is superficially similar to some code in fade_messages, but an
    // important difference here is that we look at each message individually, whereas
    // the other code takes advantage of blocks beneath recipient bars.
    for (const message_group of message_groups) {
        const $elt = get_element(message_group);
        const first_message = message_group.message_containers[0]!.msg;
        const should_fade = compose_fade_helper.should_fade_message(first_message);
        change_fade_state($elt, should_fade);
    }
}
