import * as message_lists from "./message_lists";
import * as popover_menus from "./popover_menus";
import * as recent_topics_ui from "./recent_topics_ui";
import * as stream_list from "./stream_list";
import * as sub_store from "./sub_store";
import * as unread_ui from "./unread_ui";
import * as user_topics from "./user_topics";

export function handle_topic_updates(user_topic_event) {
    // Update the UI after changes in topic visibility policies.
    user_topics.set_user_topic(user_topic_event);
    popover_menus.get_topic_menu_popover()?.hide();

    stream_list.update_streams_sidebar();
    unread_ui.update_unread_counts();
    message_lists.current.update_muting_and_rerender();
    if (message_lists.current !== message_lists.home) {
        message_lists.home.update_muting_and_rerender();
    }
    recent_topics_ui.update_topic_visibility_policy(
        user_topic_event.stream_id,
        user_topic_event.topic_name,
    );
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

export function mute_or_unmute_topic($elt, visibility_policy) {
    const stream_id = Number.parseInt($elt.attr("data-stream-id"), 10);
    const topic = $elt.attr("data-topic-name");
    user_topics.set_user_topic_visibility_policy(stream_id, topic, visibility_policy);
}
