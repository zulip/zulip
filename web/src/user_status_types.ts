import {z} from "zod";

export const user_status_schema = z.intersection(
    z.object({
        status_text: z.string().optional(),
        scheduled_end_time: z.number().optional(),
        away: z.boolean().optional(),
    }),
    z.union([
        z.object({
            emoji_name: z.string(),
            emoji_code: z.string(),
            reaction_type: z.enum(["zulip_extra_emoji", "realm_emoji", "unicode_emoji"]),
        }),
        z.object({
            emoji_name: z.undefined(),
        }),
    ]),
);
