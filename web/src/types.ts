import * as z from "zod/mini";

// TODO/typescript: Move this to server_events
export const topic_link_schema = z.object({
    text: z.string(),
    url: z.string(),
});

export type TopicLink = z.infer<typeof topic_link_schema>;

export type HTMLSelectOneElement = HTMLSelectElement & {type: "select-one"};

export const anonymous_group_schema = z.object({
    direct_subgroups: z.array(z.number()),
    direct_members: z.array(z.number()),
});

export const group_setting_value_schema = z.union([z.number(), anonymous_group_schema]);

export const COMPONENT_INTENT_VALUES = [
    "neutral",
    "brand",
    "info",
    "success",
    "warning",
    "danger",
] as const;

export type ComponentIntent = (typeof COMPONENT_INTENT_VALUES)[number];
