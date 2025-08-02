import * as z from "zod/mini";

const display_recipient_users_schema = z.object({
    id: z.number(),
    email: z.string(),
    full_name: z.string(),
});

export const message_edit_history_schema = z.array(
    z.object({
        prev_content: z.optional(z.string()),
        prev_rendered_content: z.optional(z.string()),
        prev_stream: z.optional(z.number()),
        prev_topic: z.optional(z.string()),
        stream: z.optional(z.number()),
        timestamp: z.number(),
        topic: z.optional(z.string()),
        user_id: z.nullable(z.number()),
    }),
);

const message_reaction_schema = z.array(
    z.object({
        emoji_name: z.string(),
        emoji_code: z.string(),
        reaction_type: z.enum(["unicode_emoji", "realm_emoji", "zulip_extra_emoji"]),
        user_id: z.number(),
    }),
);

const submessage_schema = z.array(
    z.object({
        msg_type: z.string(),
        content: z.string(),
        message_id: z.number(),
        sender_id: z.number(),
        id: z.number(),
    }),
);

export const server_message_schema = z.intersection(
    z.object({
        avatar_url: z.nullish(z.string()),
        client: z.string(),
        content: z.string(),
        content_type: z.enum(["text/html", "text/x-markdown"]),
        display_recipient: z.union([z.string(), z.array(display_recipient_users_schema)]),
        edit_history: z.optional(message_edit_history_schema),
        id: z.number(),
        is_me_message: z.boolean(),
        last_edit_timestamp: z.optional(z.number()),
        last_moved_timestamp: z.optional(z.number()),
        reactions: message_reaction_schema,
        recipient_id: z.number(),
        sender_email: z.string(),
        sender_full_name: z.string(),
        sender_id: z.number(),
        sender_realm_str: z.string(),
        submessages: submessage_schema,
        timestamp: z.number(),
    }),
    z.discriminatedUnion("type", [
        z.object({
            type: z.literal("stream"),
            subject: z.string(),
            stream_id: z.number(),
            topic_links: z.array(
                z.object({
                    text: z.string(),
                    url: z.string(),
                }),
            ),
        }),
        z.object({
            type: z.literal("private"),
            subject: z.literal(""),
            topic_links: z.array(z.never()),
        }),
    ]),
);
