import * as blueslip from "./blueslip";
import {page_params} from "./page_params";
import * as topic_list from "./topic_list";

let pinned_topics = [];

export function add({stream_id, topic_name}) {
    pinned_topics.push({stream_id, topic_name});
    topic_list.update();
    blueslip.info("add pinned topic", pinned_topics);
}

export function remove({stream_id, topic_name}) {
    pinned_topics = pinned_topics.filter(
        (item) => !(item.stream_id === stream_id && item.topic_name === topic_name),
    );
    topic_list.update();
    blueslip.info("add pinned topic", pinned_topics);
}

export function is_topic_pinned({stream_id, topic_name}) {
    for (const row of pinned_topics) {
        if (row.stream_id === stream_id && row.topic_name === topic_name) {
            return true;
        }
    }

    return false;
}

export function initialize() {
    pinned_topics = [...page_params.pinned_topics];
    blueslip.info("initialize pinned_topics", pinned_topics);
}
