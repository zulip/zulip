import * as z from "zod/mini";

import * as channel from "./channel.ts";
import type {Message} from "./message_store.ts";
import * as people from "./people.ts";
import * as settings_data from "./settings_data.ts";
import {realm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";

export function is_message_sent_by_my_bot(message: Message): boolean {
    const user = people.get_by_user_id(message.sender_id);
    if (!user.is_bot || user.bot_owner_id === null) {
        // The message was not sent by a bot or the message was sent
        // by a cross-realm bot which does not have an owner.
        return false;
    }

    return people.is_my_user_id(user.bot_owner_id);
}

export function get_deletability(message: Message): boolean {
    if (message.type === "stream" && stream_data.is_stream_archived_by_id(message.stream_id)) {
        return false;
    }
    if (settings_data.user_can_delete_any_message()) {
        return true;
    }

    if (message.type === "stream") {
        const stream = stream_data.get_sub_by_id(message.stream_id);
        // The channel may not be available locally (e.g. not yet loaded).
        // Skip the channel-level permission check rather than crashing the
        // message-list render, which now consults this for every message.
        if (stream !== undefined) {
            const can_delete_any_message_in_channel =
                settings_data.user_has_permission_for_group_setting(
                    stream.can_delete_any_message_group,
                    "can_delete_any_message_group",
                    "stream",
                );
            if (can_delete_any_message_in_channel) {
                return true;
            }
        }
    }

    if (!message.sent_by_me && !is_message_sent_by_my_bot(message)) {
        return false;
    }
    if (message.locally_echoed) {
        return false;
    }
    if (!settings_data.user_can_delete_own_message()) {
        if (message.type !== "stream") {
            return false;
        }

        const stream = stream_data.get_sub_by_id(message.stream_id);
        if (stream === undefined) {
            // Channel not available locally; treat as non-deletable.
            return false;
        }

        const can_delete_own_message_in_channel =
            settings_data.user_has_permission_for_group_setting(
                stream.can_delete_own_message_group,
                "can_delete_own_message_group",
                "stream",
            );
        if (!can_delete_own_message_in_channel) {
            return false;
        }
    }

    if (realm.realm_message_content_delete_limit_seconds === null) {
        // This means no time limit for message deletion.
        return true;
    }

    if (
        realm.realm_message_content_delete_limit_seconds + (message.timestamp - Date.now() / 1000) >
        0
    ) {
        return true;
    }
    return false;
}

export function delete_topic(stream_id: number, topic_name: string, failures = 0): void {
    void channel.post({
        url: "/json/streams/" + stream_id + "/delete_topic",
        data: {
            topic_name,
        },
        success(data) {
            const {complete} = z.object({complete: z.boolean()}).parse(data);
            if (!complete) {
                if (failures >= 9) {
                    // Don't keep retrying indefinitely to avoid DoSing the server.
                    return;
                }

                failures += 1;
                /* When trying to delete a very large topic, it's
                   possible for the request to the server to
                   time out after making some progress. Retry the
                   request, so that the user can just do nothing and
                   watch the topic slowly be deleted.

                   TODO: Show a nice loading indicator experience.
                */
                delete_topic(stream_id, topic_name, failures);
            }
        },
    });
}
