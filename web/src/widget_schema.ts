import * as z from "zod/mini";

import {poll_widget_extra_data_schema} from "./poll_data.ts";
import type {PollWidgetOutboundData} from "./poll_data.ts";
import {todo_widget_extra_data_schema} from "./todo_widget.ts";
import type {TodoWidgetOutboundData} from "./todo_widget.ts";
import {zform_widget_extra_data_schema} from "./zform_data.ts";

/*
    We can eventually unify this module with widget_data.ts,
    but until we can extract todo_data.ts (which is on hold
    until some functional todo-widget changes hit the main
    branch), we need tiny modules like this one in order
    to prevent circular dependencies.
*/

export type WidgetOutboundData = PollWidgetOutboundData | TodoWidgetOutboundData;

export const any_widget_data_schema = z.discriminatedUnion("widget_type", [
    z.object({widget_type: z.literal("poll"), extra_data: poll_widget_extra_data_schema}),
    z.object({
        widget_type: z.literal("zform"),
        extra_data: z.nullable(zform_widget_extra_data_schema),
    }),
    z.object({
        widget_type: z.literal("todo"),
        extra_data: z.nullable(todo_widget_extra_data_schema),
    }),
]);
export type AnyWidgetData = z.infer<typeof any_widget_data_schema>;
