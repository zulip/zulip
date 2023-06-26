import $ from "jquery";
import _ from "lodash";

import {buddy_list} from "./buddy_list";
import * as compose_fade_helper from "./compose_fade_helper";
import * as compose_fade_users from "./compose_fade_users";
import * as compose_state from "./compose_state";
import * as message_lists from "./message_lists";
import * as message_viewport from "./message_viewport";
import * as people from "./people";
import * as rows from "./rows";
import * as util from "./util";

let normal_display = false;

export function set_focused_recipient(msg_type) {
    if (msg_type === undefined) {
        compose_fade_helper.clear_focused_recipient();
    }

    // Construct focused_recipient as a mocked up element which has all the
    // fields of a message used by util.same_recipient()
    const focused_recipient = {
        type: msg_type,
    };

    if (focused_recipient.type === "stream") {
        const stream_id = compose_state.stream_id();
        focused_recipient.topic = compose_state.topic();
        if (stream_id) {
            focused_recipient.stream_id = stream_id;
        }
    } else {
        // Normalize the recipient list so it matches the one used when
        // adding the message (see message_helper.process_new_message()).
        const reply_to = util.normalize_recipients(compose_state.private_message_recipient());
        focused_recipient.reply_to = reply_to;
        focused_recipient.to_user_ids = people.reply_to_to_user_ids_string(reply_to);
    }

    compose_fade_helper.set_focused_recipient(focused_recipient);
}

function display_messages_normally() {
    const $table = rows.get_table(message_lists.current.table_name);
    $table.find(".recipient_row").removeClass("message-fade");

    normal_display = true;
}

function change_fade_state($elt, should_fade_group) {
    if (should_fade_group) {
        $elt.addClass("message-fade");
    } else {
        $elt.removeClass("message-fade");
    }
}

function fade_messages() {
    let i;
    let first_message;
    let $first_row;
    let should_fade_group = false;
    const visible_groups = message_viewport.visible_groups(false);

    normal_display = false;

    // Update the visible messages first, before the compose box opens
    for (i = 0; i < visible_groups.length; i += 1) {
        $first_row = rows.first_message_in_group(visible_groups[i]);
        first_message = message_lists.current.get(rows.id($first_row));
        should_fade_group = compose_fade_helper.should_fade_message(first_message);

        change_fade_state($(visible_groups[i]), should_fade_group);
    }

    // Defer updating all message groups so that the compose box can open sooner
    setTimeout(
        (expected_msg_list, expected_recipient) => {
            const all_groups = rows
                .get_table(message_lists.current.table_name)
                .find(".recipient_row");

            if (
                message_lists.current !== expected_msg_list ||
                !compose_state.composing() ||
                compose_state.private_message_recipient() !== expected_recipient
            ) {
                return;
            }

            should_fade_group = false;

            // Note: The below algorithm relies on the fact that all_elts is
            // sorted as it would be displayed in the message view
            for (i = 0; i < all_groups.length; i += 1) {
                const $group_elt = $(all_groups[i]);
                should_fade_group = compose_fade_helper.should_fade_message(
                    rows.recipient_from_group($group_elt),
                );
                change_fade_state($group_elt, should_fade_group);
            }
        },
        0,
        message_lists.current,
        compose_state.private_message_recipient(),
    );
}

const user_fade_config = {
    get_user_id($li) {
        return buddy_list.get_key_from_li({$li});
    },
    fade($li) {
        return $li.addClass("user-fade");
    },
    unfade($li) {
        return $li.removeClass("user-fade");
    },
};

function do_update_all() {
    const user_items = buddy_list.get_items();

    if (compose_fade_helper.want_normal_display()) {
        if (!normal_display) {
            display_messages_normally();
            compose_fade_users.display_users_normally(user_items, user_fade_config);
        }
    } else {
        fade_messages();
        compose_fade_users.fade_users(user_items, user_fade_config);
    }
}

// This one only updates the users, not both, like update_faded_messages.
// This is for when new presence information comes in, redrawing the presence
// list.
export function update_faded_users() {
    const user_items = buddy_list.get_items();

    compose_fade_users.update_user_info(user_items, user_fade_config);
}

// This gets called on keyup events, hence the throttling.
export const update_all = _.debounce(do_update_all, 50);

export function start_compose(msg_type) {
    set_focused_recipient(msg_type);
    do_update_all();
}

export function clear_compose() {
    compose_fade_helper.clear_focused_recipient();
    display_messages_normally();
    update_faded_users();
}

export function update_message_list() {
    if (compose_fade_helper.want_normal_display()) {
        display_messages_normally();
    } else {
        fade_messages();
    }
}

export function update_rendered_message_groups(message_groups, get_element) {
    if (compose_fade_helper.want_normal_display()) {
        return;
    }

    // This loop is superficially similar to some code in fade_messages, but an
    // important difference here is that we look at each message individually, whereas
    // the other code takes advantage of blocks beneath recipient bars.
    for (const message_group of message_groups) {
        const $elt = get_element(message_group);
        const first_message = message_group.message_containers[0].msg;
        const should_fade = compose_fade_helper.should_fade_message(first_message);
        change_fade_state($elt, should_fade);
    }
}
