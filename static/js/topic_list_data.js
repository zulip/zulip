"use strict";

const max_topics = 5;
const max_topics_with_unread = 8;

exports.get_list_info = function (stream_id, zoomed) {
    let topics_selected = 0;
    let more_topics_unreads = 0;

    let active_topic = narrow_state.topic();

    if (active_topic) {
        active_topic = active_topic.toLowerCase();
    }

    const topic_names = stream_topic_history.get_recent_topic_names(stream_id);

    const items = [];

    for (const [idx, topic_name] of topic_names.entries()) {
        const num_unread = unread.num_unread_for_topic(stream_id, topic_name);
        const is_active_topic = active_topic === topic_name.toLowerCase();
        const is_topic_muted = muting.is_topic_muted(stream_id, topic_name);

        if (!zoomed) {
            function should_show_topic(topics_selected) {
                // This function exists just for readability, to
                // avoid long chained conditionals to determine
                // which topics to include.

                // We always show the active topic.  Ideally, this
                // logic would first check whether the active
                // topic is in the set of those with unreads to
                // avoid ending up with max_topics_with_unread + 1
                // total topics if the active topic comes after
                // the first several topics with unread messages.
                if (is_active_topic) {
                    return true;
                }

                // We unconditionally skip showing muted topics
                // when not zoomed, even if they have unread
                // messages.
                if (is_topic_muted) {
                    return false;
                }

                // We include the most recent max_topics topics,
                // even if there are no unread messages.
                if (idx < max_topics) {
                    return true;
                }

                // We include older topics with unread messages up
                // until max_topics_with_unread total topics have
                // been included.
                if (num_unread > 0 && topics_selected < max_topics_with_unread) {
                    return true;
                }

                // Otherwise, we don't show the topic in the
                // unzoomed view.  We might display its unread
                // count in in "more topics" if it is not muted.
                return false;
            }

            const show_topic = should_show_topic(topics_selected);
            if (!show_topic) {
                if (!is_topic_muted) {
                    // The "more topics" unread count, like
                    // stream-level counts, only counts messages
                    // on unmuted topics.
                    more_topics_unreads += num_unread;
                }
                continue;
            }
            topics_selected += 1;
            // We fall through to rendering the topic, using the
            // same code we do when zoomed.
        }

        const topic_info = {
            topic_name,
            unread: num_unread,
            is_zero: num_unread === 0,
            is_muted: is_topic_muted,
            is_active_topic,
            url: hash_util.by_stream_topic_uri(stream_id, topic_name),
        };

        items.push(topic_info);
    }

    return {
        items,
        num_possible_topics: topic_names.length,
        more_topics_unreads,
    };
};
