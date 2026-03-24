import * as resolved_topic from "./resolved_topic.ts";
import {realm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import type {StreamSubscription} from "./sub_store.ts";

export function can_toggle_topic_resolution(
    sub: StreamSubscription | undefined,
    topic_name: string,
): boolean {
    if (sub === undefined || sub.is_archived) {
        return false;
    }

    const can_resolve_by_permission = stream_data.can_resolve_topics(sub);
    if (resolved_topic.is_resolved(topic_name)) {
        return can_resolve_by_permission;
    }

    if (
        realm.realm_topic_resolution_message_requirement === "required" &&
        !stream_data.can_post_messages_in_stream(sub)
    ) {
        return false;
    }

    return can_resolve_by_permission;
}
