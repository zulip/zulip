import $ from "jquery";
import _ from "lodash";

import render_confirm_mute_user from "../templates/confirm_mute_user.hbs";
import render_topic_muted from "../templates/topic_muted.hbs";

import * as activity from "./activity";
import * as channel from "./channel";
import * as confirm_dialog from "./confirm_dialog";
import * as feedback_widget from "./feedback_widget";
import {$t} from "./i18n";
import * as message_lists from "./message_lists";
import * as muting from "./muting";
import * as overlays from "./overlays";
import * as people from "./people";
import * as pm_list from "./pm_list";
import * as popovers from "./popovers";
import * as recent_topics from "./recent_topics";
import * as settings_muted_topics from "./settings_muted_topics";
import * as settings_muted_users from "./settings_muted_users";
import * as stream_data from "./stream_data";
import * as stream_list from "./stream_list";
import * as stream_popover from "./stream_popover";
import * as unread_ui from "./unread_ui";

export function rerender_for_muted_topic(old_muted_topics) {
    stream_list.update_streams_sidebar();
    message_lists.current.update_muting_and_rerender();
    if (message_lists.current !== message_lists.home) {
        message_lists.home.update_muting_and_rerender();
    }
    if (overlays.settings_open() && settings_muted_topics.loaded) {
        settings_muted_topics.populate_list();
    }

    // We only update those topics which could have been affected, because
    // we want to avoid doing a complete rerender of the recent topics view,
    // because that can be expensive.
    const current_muted_topics = muting.get_muted_topics();
    const maybe_affected_topics = _.unionWith(old_muted_topics, current_muted_topics, _.isEqual);

    for (const topic_data of maybe_affected_topics) {
        recent_topics.update_topic_is_muted(topic_data.stream_id, topic_data.topic);
    }
}

export function handle_topic_updates(muted_topics) {
    const old_muted_topics = muting.get_muted_topics();
    muting.set_muted_topics(muted_topics);
    stream_popover.hide_topic_popover();
    unread_ui.update_unread_counts();
    rerender_for_muted_topic(old_muted_topics);
}

export function mute_topic(stream_id, topic, from_hotkey) {
    const stream_name = stream_data.maybe_get_stream_name(stream_id);
    const data = {
        stream_id,
        topic,
        op: "add",
    };

    channel.patch({
        url: "/json/users/me/subscriptions/muted_topics",
        idempotent: true,
        data,
        success() {
            if (!from_hotkey) {
                return;
            }

            // The following feedback_widget notice helps avoid
            // confusion when a user who is not familiar with Zulip's
            // keyboard UI hits "M" in the wrong context and has a
            // bunch of messages suddenly disappear.  This notice is
            // only useful when muting from the keyboard, since you
            // know what you did if you triggered muting with the
            // mouse.
            feedback_widget.show({
                populate(container) {
                    const rendered_html = render_topic_muted();
                    container.html(rendered_html);
                    container.find(".stream").text(stream_name);
                    container.find(".topic").text(topic);
                },
                on_undo() {
                    unmute_topic(stream_id, topic);
                },
                title_text: $t({defaultMessage: "Topic muted"}),
                undo_button_text: $t({defaultMessage: "Unmute"}),
            });
        },
    });
}

export function unmute_topic(stream_id, topic) {
    // Accidentally unmuting a topic isn't as much an issue as accidentally muting
    // a topic, so we don't show a popup after unmuting.
    const data = {
        stream_id,
        topic,
        op: "remove",
    };

    channel.patch({
        url: "/json/users/me/subscriptions/muted_topics",
        idempotent: true,
        data,
        success() {
            feedback_widget.dismiss();
        },
    });
}

export function toggle_topic_mute(message) {
    const stream_id = message.stream_id;
    const topic = message.topic;

    if (muting.is_topic_muted(stream_id, topic)) {
        unmute_topic(stream_id, topic);
    } else if (message.type === "stream") {
        mute_topic(stream_id, topic, true);
    }
}

export function mute_user(user_id) {
    channel.post({
        url: "/json/users/me/muted_users/" + user_id,
        idempotent: true,
    });
}

export function confirm_mute_user(user_id) {
    function on_click() {
        mute_user(user_id);
    }

    const modal_parent = $(".mute-user-modal-holder");
    const html_body = render_confirm_mute_user({
        user_name: people.get_full_name(user_id),
    });

    confirm_dialog.launch({
        parent: modal_parent,
        html_heading: $t({defaultMessage: "Mute user"}),
        help_link: "/help/mute-a-user",
        html_body,
        html_yes_button: $t({defaultMessage: "Confirm"}),
        on_click,
    });
}

export function unmute_user(user_id) {
    channel.del({
        url: "/json/users/me/muted_users/" + user_id,
        idempotent: true,
    });
}

export function rerender_for_muted_user() {
    message_lists.current.update_muting_and_rerender();
    if (message_lists.current !== message_lists.home) {
        message_lists.home.update_muting_and_rerender();
    }

    if (overlays.settings_open() && settings_muted_users.loaded) {
        settings_muted_users.populate_list();
    }

    activity.redraw();
    pm_list.update_private_messages();
}

export function handle_user_updates(muted_user_ids) {
    popovers.hide_all();
    muting.set_muted_users(muted_user_ids);
    rerender_for_muted_user();
}
