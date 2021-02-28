import * as activity from "./activity";
import * as notifications from "./notifications";
import * as pm_list from "./pm_list";
import * as top_left_corner from "./top_left_corner";
import * as topic_list from "./topic_list";
import * as unread from "./unread";

let last_mention_count = 0;

function do_new_messages_animation(li) {
    li.addClass("new_messages");
    function mid_animation() {
        li.removeClass("new_messages");
        li.addClass("new_messages_fadeout");
    }
    function end_animation() {
        li.removeClass("new_messages_fadeout");
    }
    setTimeout(mid_animation, 3000);
    setTimeout(end_animation, 6000);
}

export function animate_mention_changes(li, new_mention_count) {
    if (new_mention_count > last_mention_count) {
        do_new_messages_animation(li);
    }
    last_mention_count = new_mention_count;
}

export function set_count_toggle_button(elem, count) {
    if (count === 0) {
        if (elem.is(":animated")) {
            return elem.stop(true, true).hide();
        }
        return elem.hide(500);
    } else if (count > 0 && count < 1000) {
        elem.show(500);
        return elem.text(count);
    }
    elem.show(500);
    return elem.text("1k+");
}

export function update_unread_counts() {
    // Pure computation:
    const res = unread.get_counts();

    // Side effects from here down:
    // This updates some DOM elements directly, so try to
    // avoid excessive calls to this.
    activity.update_dom_with_unread_counts(res);
    top_left_corner.update_dom_with_unread_counts(res);
    stream_list.update_dom_with_unread_counts(res);
    pm_list.update_dom_with_unread_counts(res);
    topic_list.update();
    const notifiable_unread_count = unread.calculate_notifiable_count(res);
    notifications.update_unread_counts(notifiable_unread_count, res.private_message_count);

    set_count_toggle_button($("#streamlist-toggle-unreadcount"), res.home_unread_messages);
}

export function should_display_bankruptcy_banner() {
    // Until we've handled possibly declaring bankruptcy, don't show
    // unread counts since they only consider messages that are loaded
    // client side and may be different from the numbers reported by
    // the server.

    if (!page_params.furthest_read_time) {
        // We've never read a message.
        return false;
    }

    const now = Date.now() / 1000;
    if (
        page_params.unread_msgs.count > 500 &&
        now - page_params.furthest_read_time > 60 * 60 * 24 * 2
    ) {
        // 2 days.
        return true;
    }

    return false;
}

export function initialize() {
    update_unread_counts();
}
