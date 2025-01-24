import * as v from "valibot";

const display_recipient_users_schema = v.object({
    id: v.number(),
    email: v.string(),
    full_name: v.string(),
});

export const message_edit_history_schema = v.array(
    v.object({
        prev_content: v.optional(v.string()),
        prev_rendered_content: v.optional(v.string()),
        prev_stream: v.optional(v.number()),
        prev_topic: v.optional(v.string()),
        stream: v.optional(v.number()),
        timestamp: v.number(),
        topic: v.optional(v.string()),
        user_id: v.nullable(v.number()),
    }),
);

const message_reaction_schema = v.array(
    v.object({
        emoji_name: v.string(),
        emoji_code: v.string(),
        reaction_type: v.picklist(["unicode_emoji", "realm_emoji", "zulip_extra_emoji"]),
        user_id: v.number(),
    }),
);

const submessage_schema = v.array(
    v.object({
        msg_type: v.string(),
        content: v.string(),
        message_id: v.number(),
        sender_id: v.number(),
        id: v.number(),
    }),
);

export const server_message_schema = v.intersect([
    v.object({
        avatar_url: v.nullish(v.string()),
        client: v.string(),
        content: v.string(),
        content_type: v.picklist(["text/html", "text/x-markdown"]),
        display_recipient: v.union([v.string(), v.array(display_recipient_users_schema)]),
        edit_history: v.optional(message_edit_history_schema),
        id: v.number(),
        is_me_message: v.boolean(),
        last_edit_timestamp: v.optional(v.number()),
        reactions: message_reaction_schema,
        recipient_id: v.number(),
        sender_email: v.string(),
        sender_full_name: v.string(),
        sender_id: v.number(),
        sender_realm_str: v.string(),
        submessages: submessage_schema,
        timestamp: v.number(),
    }),
    v.variant("type", [
        v.object({
            type: v.literal("stream"),
            subject: v.string(),
            stream_id: v.number(),
            topic_links: v.array(
                v.object({
                    text: v.string(),
                    url: v.string(),
                }),
            ),
        }),
        v.object({
            type: v.literal("private"),
            subject: v.literal(""),
            topic_links: v.array(v.never()),
        }),
    ]),
]);
