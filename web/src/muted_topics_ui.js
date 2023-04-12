import _ from "lodash";

import * as message_lists from "./message_lists";
import * as overlays from "./overlays";
import * as popover_menus from "./popover_menus";
import * as recent_topics_ui from "./recent_topics_ui";
import * as settings_muted_topics from "./settings_muted_topics";
import * as stream_list from "./stream_list";
import * as sub_store from "./sub_store";
import * as unread_ui from "./unread_ui";
import * as user_topics from "./user_topics";

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
    const current_muted_topics = user_topics.get_user_topics_for_visibility_policy(
        user_topics.all_visibility_policies.MUTED,
    );
    const maybe_affected_topics = _.unionWith(old_muted_topics, current_muted_topics, _.isEqual);

    for (const topic_data of maybe_affected_topics) {
        recent_topics_ui.update_topic_is_muted(topic_data.stream_id, topic_data.topic);
    }
}

export function handle_topic_updates(user_topic) {
    const old_muted_topics = user_topics.get_user_topics_for_visibility_policy(
        user_topics.all_visibility_policies.MUTED,
    );
    user_topics.set_user_topic(user_topic);
    popover_menus.get_topic_menu_popover()?.hide();
    unread_ui.update_unread_counts();
    rerender_for_muted_topic(old_muted_topics);
}

export function toggle_topic_visibility_policy(message) {
    const stream_id = message.stream_id;
    const topic = message.topic;

    if (
        user_topics.is_topic_muted(stream_id, topic) ||
        user_topics.is_topic_unmuted(stream_id, topic)
    ) {
        user_topics.set_user_topic_visibility_policy(
            stream_id,
            topic,
            user_topics.all_visibility_policies.INHERIT,
        );
    } else if (message.type === "stream") {
        if (sub_store.get(stream_id).is_muted) {
            user_topics.set_user_topic_visibility_policy(
                stream_id,
                topic,
                user_topics.all_visibility_policies.UNMUTED,
                true,
            );
        } else {
            user_topics.set_user_topic_visibility_policy(
                stream_id,
                topic,
                user_topics.all_visibility_policies.MUTED,
                true,
            );
        }
    }
}

export function mute_or_unmute_topic($elt, mute) {
    const stream_id = Number.parseInt($elt.attr("data-stream-id"), 10);
    const topic = $elt.attr("data-topic-name");
    if (mute) {
        user_topics.set_user_topic_visibility_policy(
            stream_id,
            topic,
            user_topics.all_visibility_policies.MUTED,
        );
    } else {
        user_topics.set_user_topic_visibility_policy(
            stream_id,
            topic,
            user_topics.all_visibility_policies.INHERIT,
        );
    }
}
