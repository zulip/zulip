import * as v from "valibot";

// TODO/typescript: Move this to server_events
export const topic_link_schema = v.object({
    text: v.string(),
    url: v.string(),
});

export type TopicLink = v.InferOutput<typeof topic_link_schema>;

export type HTMLSelectOneElement = HTMLSelectElement & {type: "select-one"};

export const anonymous_group_schema = v.object({
    direct_subgroups: v.array(v.number()),
    direct_members: v.array(v.number()),
});

export const group_setting_value_schema = v.union([v.number(), anonymous_group_schema]);
