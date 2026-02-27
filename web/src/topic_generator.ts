import _ from "lodash";

import * as narrow_state from "./narrow_state.ts";
import * as pm_conversations from "./pm_conversations.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_list_sort from "./stream_list_sort.ts";
import * as stream_topic_history from "./stream_topic_history.ts";
import * as unread from "./unread.ts";
import * as user_topics from "./user_topics.ts";

// If there are any unreads in the current topic,
// user likely wants to avoid reading them right now.
// So, we add them to `topics_kept_unread_by_user`
// which we will navigate to later.
//
// Why first unread message ID?
// User wants to start reading from that message later,
// and can follow `moved` breadcrumbs to read further if
// the later messages in the topic were moved.
//
// Contains the first unread message in the topic.
let topics_kept_unread_by_user = new Set<number>();

export function reset_topics_kept_unread_by_user(): void {
    topics_kept_unread_by_user.clear();
}

export function next_topic(
    sorted_channels_info: {
        channel_id: number;
        is_collapsed: boolean;
    }[],
    get_topics: (stream_id: number) => string[],
    has_unread_messages: (stream_id: number, topic: string) => boolean,
    curr_stream_id: number | undefined,
    curr_topic: string | undefined,
): {stream_id: number; topic: string} | undefined {
    const curr_stream_index = curr_stream_id
        ? sorted_channels_info.findIndex(({channel_id}) => channel_id === curr_stream_id)
        : -1;

    if (curr_stream_index >= 0) {
        const {channel_id} = sorted_channels_info[curr_stream_index]!;
        const topics = get_topics(channel_id);
        const curr_topic_index = curr_topic !== undefined ? topics.indexOf(curr_topic) : -1; // -1 if not found

        // 1. Find any unreads in the current channel after the current topic.
        for (let i = curr_topic_index + 1; i < topics.length; i += 1) {
            const topic = topics[i]!;
            if (has_unread_messages(channel_id, topic)) {
                return {stream_id: channel_id, topic};
            }
        }

        // 2. Find any unreads in the current channel before the current topic.
        for (let i = 0; i < curr_topic_index; i += 1) {
            const topic = topics[i]!;
            if (has_unread_messages(channel_id, topic)) {
                return {stream_id: channel_id, topic};
            }
        }
    }

    // 3. Find any unreads after the current channel in uncollapsed folders.
    for (let i = curr_stream_index + 1; i < sorted_channels_info.length; i += 1) {
        const channel_info = sorted_channels_info[i]!;
        if (channel_info.is_collapsed) {
            continue;
        }
        for (const topic of get_topics(channel_info.channel_id)) {
            if (has_unread_messages(channel_info.channel_id, topic)) {
                return {stream_id: channel_info.channel_id, topic};
            }
        }
    }

    // `sorted_channels_info`: First has uncollapsed channels,
    //                         then collapsed ones.
    // 4. Find any unreads before the current channel:topic.
    // 5. Find any unreads in collapsed channels.
    let reached_current_narrow_state = false;
    for (const channel_info of sorted_channels_info) {
        if (reached_current_narrow_state && !channel_info.is_collapsed) {
            // We have already processed uncollapsed channels
            // after the current channel in step 2.
            continue;
        }

        for (const topic of get_topics(channel_info.channel_id)) {
            // Skip over to the next channel after reaching the current topic.
            if (
                !reached_current_narrow_state &&
                curr_stream_id !== undefined &&
                channel_info.channel_id === curr_stream_id
            ) {
                reached_current_narrow_state = curr_topic === undefined || curr_topic === topic;

                if (reached_current_narrow_state) {
                    // We already processed topic in the current channel above.
                    break;
                }
            }

            if (has_unread_messages(channel_info.channel_id, topic)) {
                return {stream_id: channel_info.channel_id, topic};
            }
        }
    }

    // 6. No unread topic found.
    return undefined;
}

export function get_next_topic(
    curr_stream_id: number | undefined,
    curr_topic: string | undefined,
    only_followed_topics: boolean,
    sorted_channels_info: {
        channel_id: number;
        is_collapsed: boolean;
    }[],
): {stream_id: number; topic: string} | undefined {
    sorted_channels_info = sorted_channels_info.filter(({channel_id}) => {
        if (!stream_data.is_muted(channel_id)) {
            return true;
        }
        if (only_followed_topics) {
            // We can use Shift + N to go to unread followed topic in muted stream.
            const topics = stream_topic_history.get_recent_topic_names(channel_id);
            return topics.some((topic) => user_topics.is_topic_followed(channel_id, topic));
        }
        if (channel_id === curr_stream_id) {
            // We can use n within a muted stream if we are
            // currently narrowed to it.
            return true;
        }
        // We can use N to go to next unread unmuted/followed topic in a muted stream .
        const topics = stream_topic_history.get_recent_topic_names(channel_id);
        return topics.some((topic) => user_topics.is_topic_unmuted_or_followed(channel_id, topic));
    });

    function get_unmuted_topics(stream_id: number): string[] {
        const narrowed_steam_id = narrow_state.stream_id();
        const topics = stream_topic_history.get_recent_topic_names(stream_id);
        const narrowed_topic = narrow_state.topic();
        if (
            narrowed_steam_id !== undefined &&
            narrowed_topic !== undefined &&
            narrowed_steam_id === stream_id &&
            _.isEqual(narrow_state.filter()?.sorted_term_types(), ["stream", "topic"]) &&
            !user_topics.is_topic_unmuted_or_followed(stream_id, narrowed_topic)
        ) {
            // Here we're using N within a muted stream starting from
            // a muted topic; advance to the next not-explicitly-muted
            // unread topic in the stream, to allow using N within
            // muted streams. We'll jump back into the normal mode if
            // we land in a followed/unmuted topic, but that's OK.

            /* istanbul ignore next */
            return topics.filter((topic) => !user_topics.is_topic_muted(stream_id, topic));
        } else if (stream_data.is_muted(stream_id)) {
            return topics.filter((topic) =>
                user_topics.is_topic_unmuted_or_followed(stream_id, topic),
            );
        }
        return topics.filter((topic) => !user_topics.is_topic_muted(stream_id, topic));
    }

    function get_followed_topics(stream_id: number): string[] {
        let topics = stream_topic_history.get_recent_topic_names(stream_id);
        topics = topics.filter((topic) => user_topics.is_topic_followed(stream_id, topic));
        return topics;
    }

    // Remember that user chose to keep some messages unread in the current topic.
    if (
        narrow_state.narrowed_by_topic_reply() &&
        curr_stream_id !== undefined &&
        curr_topic !== undefined
    ) {
        const topic_unread_msg_ids = unread.get_msg_ids_for_topic(curr_stream_id, curr_topic);
        if (topic_unread_msg_ids.length > 0) {
            topics_kept_unread_by_user.add(topic_unread_msg_ids[0]!);
        }
    }

    function has_unread_messages(channel_id: number, topic: string): boolean {
        const topic_unread_msg_ids = unread.get_msg_ids_for_topic(channel_id, topic);
        if (topic_unread_msg_ids.length > 0) {
            // If user chose to keep some messages unread in this topic,
            // skip it for now and come back to it later.
            if (topic_unread_msg_ids.some((msg_id) => topics_kept_unread_by_user.has(msg_id))) {
                // Remove these msg_ids from the set so that
                // we don't skip this topic next time.
                topics_kept_unread_by_user = topics_kept_unread_by_user.difference(
                    new Set(topic_unread_msg_ids),
                );
                return false;
            }
            return true;
        }
        return false;
    }

    if (only_followed_topics) {
        return next_topic(
            sorted_channels_info,
            get_followed_topics,
            has_unread_messages,
            curr_stream_id,
            curr_topic,
        );
    }

    return next_topic(
        sorted_channels_info,
        get_unmuted_topics,
        has_unread_messages,
        curr_stream_id,
        curr_topic,
    );
}

export function get_next_unread_pm_string(curr_pm: string | undefined): string | undefined {
    const my_pm_strings = pm_conversations.recent.get_strings();
    // undefined translates to "not found".
    let curr_pm_index = -1;
    if (curr_pm !== undefined) {
        curr_pm_index = my_pm_strings.indexOf(curr_pm);
    }

    for (let i = curr_pm_index + 1; i < my_pm_strings.length; i += 1) {
        if (unread.num_unread_for_user_ids_string(my_pm_strings[i]!) > 0) {
            return my_pm_strings[i];
        }
    }

    for (let i = 0; i < curr_pm_index; i += 1) {
        if (unread.num_unread_for_user_ids_string(my_pm_strings[i]!) > 0) {
            return my_pm_strings[i];
        }
    }

    return undefined;
}

export function get_next_stream(curr_stream_id: number): number | undefined {
    const my_streams = stream_list_sort.get_stream_ids();
    const curr_stream_index = my_streams.indexOf(curr_stream_id);
    return my_streams[
        curr_stream_index === -1 || curr_stream_index === my_streams.length - 1
            ? 0
            : curr_stream_index + 1
    ];
}

export function get_prev_stream(curr_stream_id: number): number | undefined {
    const my_streams = stream_list_sort.get_stream_ids();
    const curr_stream_index = my_streams.indexOf(curr_stream_id);
    return my_streams[curr_stream_index <= 0 ? my_streams.length - 1 : curr_stream_index - 1];
}
