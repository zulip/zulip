import * as v from "valibot";

import {group_setting_value_schema, topic_link_schema} from "./types.ts";

export const user_group_update_event_schema = v.object({
    id: v.number(),
    type: v.literal("user_group"),
    op: v.literal("update"),
    group_id: v.number(),
    data: v.object({
        name: v.optional(v.string()),
        description: v.optional(v.string()),
        can_add_members_group: v.optional(group_setting_value_schema),
        can_join_group: v.optional(group_setting_value_schema),
        can_leave_group: v.optional(group_setting_value_schema),
        can_manage_group: v.optional(group_setting_value_schema),
        can_mention_group: v.optional(group_setting_value_schema),
        can_remove_members_group: v.optional(group_setting_value_schema),
        deactivated: v.optional(v.boolean()),
    }),
});
export type UserGroupUpdateEvent = v.InferOutput<typeof user_group_update_event_schema>;

export const update_message_event_schema = v.object({
    id: v.number(),
    type: v.literal("update_message"),
    user_id: v.nullable(v.number()),
    rendering_only: v.boolean(),
    message_id: v.number(),
    message_ids: v.array(v.number()),
    flags: v.array(v.string()),
    edit_timestamp: v.number(),
    stream_name: v.optional(v.string()),
    stream_id: v.optional(v.number()),
    new_stream_id: v.optional(v.number()),
    propagate_mode: v.optional(v.string()),
    orig_subject: v.optional(v.string()),
    subject: v.optional(v.string()),
    topic_links: v.optional(v.array(topic_link_schema)),
    orig_content: v.optional(v.string()),
    orig_rendered_content: v.optional(v.string()),
    content: v.optional(v.string()),
    rendered_content: v.optional(v.string()),
    is_me_message: v.optional(v.boolean()),
    // The server is still using subject.
    // This will not be set until it gets fixed.
    topic: v.optional(v.string()),
});
export type UpdateMessageEvent = v.InferOutput<typeof update_message_event_schema>;

export const message_details_schema = v.record(
    v.pipe(v.string(), v.transform(Number), v.number()),
    v.intersect([
        v.object({mentioned: v.optional(v.boolean())}),
        v.variant("type", [
            v.object({type: v.literal("private"), user_ids: v.array(v.number())}),
            v.object({
                type: v.literal("stream"),
                stream_id: v.number(),
                topic: v.string(),
                unmuted_stream_msg: v.boolean(),
            }),
        ]),
    ]),
);
export type MessageDetails = v.InferOutput<typeof message_details_schema>;
