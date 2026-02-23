import assert from "minimalistic-assert";

import * as narrow_state from "./narrow_state.ts";
import * as resolved_topic from "./resolved_topic.ts";
import * as stream_topic_history from "./stream_topic_history.ts";
import * as sub_store from "./sub_store.ts";
import * as typeahead from "./typeahead.ts";
import * as unread from "./unread.ts";
import * as user_topics from "./user_topics.ts";
import * as util from "./util.ts";

const MAX_TOPICS = 6;
const MAX_TOPICS_WITH_UNREAD = 10;

export type TopicInfo = {
    stream_id: number;
    topic_name: string;
    topic_resolved_prefix: string;
    topic_display_name: string;
    is_empty_string_topic: boolean;
    unread: number;
    is_zero: boolean;
    is_muted: boolean;
    is_followed: boolean;
    is_unmuted_or_followed: boolean;
    is_active_topic: boolean;
    url: string;
    contains_unread_mention: boolean;
};

type TopicChoiceState = {
    active_topic: string | undefined;
    topics_with_unread_mentions: Set<string>;
    more_topics_unmuted_unreads: number;
    more_topics_have_unread_mention_messages: boolean;
    more_topics_muted_unreads: number;
    more_topics_have_muted_unread_mention_messages: boolean;
    topics_selected: number;
    items: TopicInfo[];
};

function build_topic_info_item(
    stream_id: number,
    topic_name: string,
    num_unread: number,
    is_topic_muted: boolean,
    is_active_topic: boolean,
    contains_unread_mention: boolean,
): TopicInfo {
    const is_topic_followed = user_topics.is_topic_followed(stream_id, topic_name);
    const is_topic_unmuted_or_followed = user_topics.is_topic_unmuted_or_followed(
        stream_id,
        topic_name,
    );
    const [topic_resolved_prefix, topic_bare_name] = resolved_topic.display_parts(topic_name);
    const topic_info: TopicInfo = {
        stream_id,
        topic_name,
        topic_resolved_prefix,
        topic_display_name: util.get_final_topic_display_name(topic_bare_name),
        is_empty_string_topic: topic_bare_name === "",
        unread: num_unread,
        is_zero: num_unread === 0,
        is_muted: is_topic_muted,
        is_followed: is_topic_followed,
        is_unmuted_or_followed: is_topic_unmuted_or_followed,
        is_active_topic,
        url: stream_topic_history.channel_topic_permalink_hash(stream_id, topic_name),
        contains_unread_mention,
    };
    return topic_info;
}

function show_all_topics(
    stream_id: number,
    topic_names: string[],
    topic_choice_state: TopicChoiceState,
): void {
    for (const topic_name of topic_names) {
        const num_unread = unread.num_unread_for_topic(stream_id, topic_name);
        const is_active_topic = topic_choice_state.active_topic === topic_name.toLowerCase();
        const is_topic_muted = user_topics.is_topic_muted(stream_id, topic_name);
        // Important: Topics are lower-case in this set.
        const contains_unread_mention = topic_choice_state.topics_with_unread_mentions.has(
            topic_name.toLowerCase(),
        );
        const topic_info = build_topic_info_item(
            stream_id,
            topic_name,
            num_unread,
            is_topic_muted,
            is_active_topic,
            contains_unread_mention,
        );
        topic_choice_state.items.push(topic_info);
    }
}

type TopicBaseInfo = {
    contains_unread_mention: boolean;
    is_active_topic: boolean;
    is_followed: boolean;
    is_muted: boolean;
    num_unread: number;
    position: number;
    topic_name: string;
};

function choose_topics(
    stream_id: number,
    topic_names: string[],
    topic_choice_state: TopicChoiceState,
): void {
    const selected_topics: TopicBaseInfo[] = [];
    const additional_followed_topics_with_unreads: TopicBaseInfo[] = [];
    const additional_topics_with_unreads: TopicBaseInfo[] = [];

    // Select most recent, unmuted MAX_TOPICS topics and the
    // active topic. Build sets for additional followed and
    // unmuted topics with unread messages. And update
    // TopicChoiceState for topics with unread messages that
    // are not selected for any of the above sets.
    for (const [idx, topic_name] of topic_names.entries()) {
        const num_unread = unread.num_unread_for_topic(stream_id, topic_name);
        const is_active_topic = topic_choice_state.active_topic === topic_name.toLowerCase();

        // If we've already found the most recent MAX_TOPICS,
        // then we only need to consider topics with unread
        // messages and the active topic.
        if (selected_topics.length >= MAX_TOPICS && !is_active_topic && num_unread === 0) {
            continue;
        }

        const is_muted = user_topics.is_topic_muted(stream_id, topic_name);
        // Important: Topics are lower-case in this set.
        const contains_unread_mention = topic_choice_state.topics_with_unread_mentions.has(
            topic_name.toLowerCase(),
        );

        // We don't show muted topics, unless it's the active topic,
        // so we just update the TopicChoiceState here.
        if (!is_active_topic && is_muted) {
            topic_choice_state.more_topics_muted_unreads += num_unread;
            if (contains_unread_mention) {
                topic_choice_state.more_topics_have_muted_unread_mention_messages = true;
            }
            continue;
        }

        const topic_base_info: TopicBaseInfo = {
            contains_unread_mention,
            is_active_topic,
            is_followed: user_topics.is_topic_followed(stream_id, topic_name),
            is_muted,
            num_unread,
            position: idx,
            topic_name,
        };

        if (selected_topics.length < MAX_TOPICS) {
            selected_topics.push(topic_base_info);
            continue;
        }

        if (topic_base_info.num_unread > 0) {
            if (
                topic_base_info.is_followed &&
                additional_followed_topics_with_unreads.length < MAX_TOPICS_WITH_UNREAD
            ) {
                additional_followed_topics_with_unreads.push(topic_base_info);
                continue;
            }

            if (additional_topics_with_unreads.length < MAX_TOPICS_WITH_UNREAD) {
                additional_topics_with_unreads.push(topic_base_info);
                continue;
            }

            if (!topic_base_info.is_active_topic) {
                topic_choice_state.more_topics_unmuted_unreads += topic_base_info.num_unread;
                if (topic_base_info.contains_unread_mention) {
                    topic_choice_state.more_topics_have_unread_mention_messages = true;
                }
                continue;
            }
        }

        // We always show the active topic, even if it's older and
        // has no unread messages.
        if (topic_base_info.is_active_topic) {
            selected_topics.push(topic_base_info);
        }
    }

    // Select followed topics with unread messages up to MAX_TOPICS_WITH_UNREAD.
    // Update TopicChoiceState for topics that are not selected.
    for (const topic_base_info of additional_followed_topics_with_unreads) {
        if (selected_topics.length < MAX_TOPICS_WITH_UNREAD) {
            selected_topics.push(topic_base_info);
        } else {
            topic_choice_state.more_topics_unmuted_unreads += topic_base_info.num_unread;
            if (topic_base_info.contains_unread_mention) {
                topic_choice_state.more_topics_have_unread_mention_messages = true;
            }
        }
    }

    // Select additional topics with unread messages up to MAX_TOPICS_WITH_UNREAD.
    // Update TopicChoiceState for topics that are not selected.
    for (const topic_base_info of additional_topics_with_unreads) {
        if (selected_topics.length < MAX_TOPICS_WITH_UNREAD) {
            selected_topics.push(topic_base_info);
        } else {
            topic_choice_state.more_topics_unmuted_unreads += topic_base_info.num_unread;
            if (topic_base_info.contains_unread_mention) {
                topic_choice_state.more_topics_have_unread_mention_messages = true;
            }
        }
    }

    // Sort selected topics by original position in topic_names list
    // and build TopicInfo items for topic list data.
    for (const selected_topic of selected_topics.toSorted(
        (a: TopicBaseInfo, b: TopicBaseInfo) => a.position - b.position,
    )) {
        topic_choice_state.topics_selected += 1;

        const topic_info = build_topic_info_item(
            stream_id,
            selected_topic.topic_name,
            selected_topic.num_unread,
            selected_topic.is_muted,
            selected_topic.is_active_topic,
            selected_topic.contains_unread_mention,
        );
        topic_choice_state.items.push(topic_info);
    }
}

function contains_topic(topic_names: string[], narrowed_topic: string): boolean {
    const lower_cased_topics = topic_names.map((name) => name.toLowerCase());
    return lower_cased_topics.includes(narrowed_topic.toLowerCase());
}

type TopicListInfo = {
    items: TopicInfo[];
    num_possible_topics: number;
    more_topics_unreads: number;
    more_topics_have_unread_mention_messages: boolean;
    more_topics_unread_count_muted: boolean;
};

export function filter_topics_by_search_term(
    stream_id: number,
    topic_names: string[],
    search_term: string,
    topics_state = "",
): string[] {
    if (search_term === "" && topics_state === "") {
        return topic_names;
    }

    const empty_string_topic_display_name = util.get_final_topic_display_name("");
    const normalize = (s: string): string => s.replaceAll(/[:/_-]+/g, " ");
    const normalized_query = normalize(search_term);

    topic_names = topic_names.filter((topic) => {
        const topic_string = topic === "" ? empty_string_topic_display_name : topic;
        const normalized_topic = normalize(topic_string);

        return typeahead.query_matches_string_in_any_order(normalized_query, normalized_topic, " ");
    });

    switch (topics_state) {
        case "is:resolved":
            topic_names = topic_names.filter((name) => resolved_topic.is_resolved(name));
            break;
        case "-is:resolved":
            topic_names = topic_names.filter((name) => !resolved_topic.is_resolved(name));
            break;
        case "is:followed":
            topic_names = topic_names.filter((name) =>
                user_topics.is_topic_followed(stream_id, name),
            );
            break;
        case "-is:followed":
            topic_names = topic_names.filter(
                (name) => !user_topics.is_topic_followed(stream_id, name),
            );
            break;
    }

    return topic_names;
}

export function get_filtered_topic_names(
    stream_id: number,
    filter_topics: (topic_names: string[]) => string[],
): string[] {
    const topic_names = stream_topic_history.get_recent_topic_names(stream_id);
    const narrowed_topic = narrow_state.topic();

    // If the user is viewing a topic with no messages, include
    // the topic name to the beginning of the list of topics.
    if (
        stream_id === narrow_state.stream_id() &&
        narrowed_topic !== undefined &&
        !contains_topic(topic_names, narrowed_topic)
    ) {
        topic_names.unshift(narrowed_topic);
    }

    return filter_topics(topic_names);
}

export function get_list_info(
    stream_id: number,
    zoomed: boolean,
    filter_topics: (topic_names: string[]) => string[],
): TopicListInfo {
    const topic_choice_state: TopicChoiceState = {
        items: [],
        topics_selected: 0,
        more_topics_muted_unreads: 0,
        more_topics_unmuted_unreads: 0,
        more_topics_have_unread_mention_messages: false,
        more_topics_have_muted_unread_mention_messages: false,
        active_topic: narrow_state.topic()?.toLowerCase(),
        topics_with_unread_mentions: unread.get_topics_with_unread_mentions(stream_id),
    };

    const sub = sub_store.get(stream_id);
    assert(sub !== undefined);
    const stream_muted = sub.is_muted;

    const topic_names = get_filtered_topic_names(stream_id, filter_topics);

    if (zoomed) {
        show_all_topics(stream_id, topic_names, topic_choice_state);
    } else if (stream_muted) {
        const unmuted_or_followed_topics = topic_names.filter((topic) =>
            user_topics.is_topic_unmuted_or_followed(stream_id, topic),
        );
        const other_topics = topic_names.filter(
            (topic) => !user_topics.is_topic_unmuted_or_followed(stream_id, topic),
        );
        const reordered_topics = [...unmuted_or_followed_topics, ...other_topics];
        choose_topics(stream_id, reordered_topics, topic_choice_state);
    } else {
        choose_topics(stream_id, topic_names, topic_choice_state);
    }

    if (
        topic_choice_state.more_topics_unmuted_unreads === 0 &&
        topic_choice_state.more_topics_muted_unreads > 0 &&
        stream_muted
    ) {
        // For muted streams, if the only unreads are in muted topics,
        // we have a muted styling "all topics" row.
        return {
            items: topic_choice_state.items,
            num_possible_topics: topic_names.length,
            more_topics_unreads: topic_choice_state.more_topics_muted_unreads,
            more_topics_have_unread_mention_messages:
                topic_choice_state.more_topics_have_muted_unread_mention_messages,
            more_topics_unread_count_muted: true,
        };
    }
    return {
        items: topic_choice_state.items,
        num_possible_topics: topic_names.length,
        more_topics_unreads: topic_choice_state.more_topics_unmuted_unreads,
        more_topics_have_unread_mention_messages:
            // Because mentions are important, and get displayed in the
            // overall summary, we display the mention indicator even if
            // they are in muted streams.
            topic_choice_state.more_topics_have_unread_mention_messages ||
            topic_choice_state.more_topics_have_muted_unread_mention_messages,
        more_topics_unread_count_muted: false,
    };
}
