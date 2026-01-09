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

// Bot widget outbound data - interactions sent back to bots
export type BotWidgetOutboundData = Record<string, unknown>;

export type WidgetOutboundData =
    | PollWidgetOutboundData
    | TodoWidgetOutboundData
    | BotWidgetOutboundData;

// Schemas for bot widget extra data - permissive to allow bot-defined structures
const rich_embed_extra_data_schema = z.record(z.string(), z.unknown());
const interactive_extra_data_schema = z.record(z.string(), z.unknown());
const freeform_extra_data_schema = z.record(z.string(), z.unknown());
const command_invocation_extra_data_schema = z.record(z.string(), z.unknown());

export const widget_data_schema = z.discriminatedUnion("widget_type", [
    z.object({widget_type: z.literal("poll"), extra_data: poll_widget_extra_data_schema}),
    z.object({
        widget_type: z.literal("zform"),
        extra_data: z.nullable(zform_widget_extra_data_schema),
    }),
    z.object({
        widget_type: z.literal("todo"),
        extra_data: z.nullable(todo_widget_extra_data_schema),
    }),
    // Bot widget types
    z.object({
        widget_type: z.literal("rich_embed"),
        extra_data: z.nullable(rich_embed_extra_data_schema),
    }),
    z.object({
        widget_type: z.literal("interactive"),
        extra_data: z.nullable(interactive_extra_data_schema),
    }),
    z.object({
        widget_type: z.literal("freeform"),
        extra_data: z.nullable(freeform_extra_data_schema),
    }),
    z.object({
        widget_type: z.literal("command_invocation"),
        extra_data: z.nullable(command_invocation_extra_data_schema),
    }),
]);
