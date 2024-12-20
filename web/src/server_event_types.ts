import {z} from "zod";

import {group_setting_value_schema} from "./types.ts";

export const user_group_update_event_schema = z.object({
    id: z.number(),
    type: z.literal("user_group"),
    op: z.literal("update"),
    group_id: z.number(),
    data: z.object({
        name: z.optional(z.string()),
        description: z.optional(z.string()),
        can_add_members_group: z.optional(group_setting_value_schema),
        can_join_group: z.optional(group_setting_value_schema),
        can_leave_group: z.optional(group_setting_value_schema),
        can_manage_group: z.optional(group_setting_value_schema),
        can_mention_group: z.optional(group_setting_value_schema),
        can_remove_members_group: z.optional(group_setting_value_schema),
        deactivated: z.optional(z.boolean()),
    }),
});
export type UserGroupUpdateEvent = z.output<typeof user_group_update_event_schema>;
