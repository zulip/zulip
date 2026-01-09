/**
 * Widget for displaying bot command invocations in messages.
 *
 * This shows a structured display of a slash command invocation,
 * similar to how Discord displays slash command usage.
 */

import * as z from "zod/mini";

import render_command_invocation_widget from "../templates/widgets/command_invocation_widget.hbs";

import * as blueslip from "./blueslip.ts";
import type {Message} from "./message_store.ts";
import type {Event} from "./widget_data.ts";
import type {WidgetExtraData} from "./widgetize.ts";

const command_argument_schema = z.record(z.string(), z.string());

export const command_invocation_extra_data_schema = z.object({
    command_name: z.string(),
    arguments: command_argument_schema,
    bot_id: z.number(),
    bot_name: z.string(),
    interaction_id: z.optional(z.string()),
    status: z.optional(z.enum(["pending", "responding", "complete", "error"])),
});

export function activate({
    $elem,
    extra_data,
}: {
    $elem: JQuery;
    callback: (data: Record<string, unknown>) => void;
    extra_data: WidgetExtraData;
    message: Message;
}): (events: Event[]) => void {
    const parse_result = command_invocation_extra_data_schema.safeParse(extra_data);
    if (!parse_result.success) {
        blueslip.error("invalid command_invocation widget extra data", {
            issues: parse_result.error.issues,
        });
        return (_events: Event[]): void => {
            /* noop */
        };
    }

    const data = parse_result.data;

    // Track status for the command - starts as pending
    let status = data.status ?? "pending";

    // Track error message if any
    let error_message = "";

    function render(): void {
        // Get bot avatar - use simple path since we just have the bot_id
        const bot_avatar = `/avatar/${data.bot_id}`;

        // Format arguments for display
        const formatted_args = Object.entries(data.arguments).map(([name, value]) => ({
            name,
            value,
        }));

        const template_data = {
            command_name: data.command_name,
            bot_name: data.bot_name,
            bot_avatar,
            arguments: formatted_args,
            has_arguments: formatted_args.length > 0,
            is_pending: status === "pending",
            is_responding: status === "responding",
            is_error: status === "error",
            error_message,
        };

        const html = render_command_invocation_widget(template_data);
        $elem.html(html);
    }

    render();

    // Handle events - for status updates from bot
    return (events: Event[]): void => {
        for (const event of events) {
            const event_data = event.data;
            if (event_data && typeof event_data === "object") {
                // Check for status update
                if ("status" in event_data && typeof event_data.status === "string") {
                    status = event_data.status as "pending" | "responding" | "complete" | "error";
                    // Capture error message if present
                    if ("error" in event_data && typeof event_data.error === "string") {
                        error_message = event_data.error;
                    }
                    render();
                }
            }
        }
    };
}
