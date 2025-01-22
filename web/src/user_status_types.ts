import * as v from "valibot";

export const user_status_schema = v.intersect([
    v.object({
        status_text: v.optional(v.string()),
        away: v.optional(v.boolean()),
    }),
    v.variant("emoji_name", [
        v.object({
            emoji_name: v.string(),
            emoji_code: v.string(),
            reaction_type: v.picklist(["zulip_extra_emoji", "realm_emoji", "unicode_emoji"]),
        }),
        v.object({
            emoji_name: v.optional(v.never()),
        }),
    ]),
]);
