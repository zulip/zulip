/**
 * Widget for rendering ephemeral/private bot responses.
 *
 * These are temporary responses visible only to specific users,
 * shown as overlays attached to the parent message.
 */

import $ from "jquery";
import * as z from "zod/mini";

import render_ephemeral_response from "../templates/widgets/ephemeral_response.hbs";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import * as markdown from "./markdown.ts";
import type {Message} from "./message_store.ts";
import * as people from "./people.ts";

// Schema for ephemeral response content
const ephemeral_response_schema = z.object({
    type: z.enum(["ephemeral_response", "bot_response"]),
    interaction_id: z.optional(z.string()),
    content: z.string(),
    widget_content: z.optional(z.unknown()),
});

// Track dismissed ephemeral messages by submessage_id
const dismissed_ephemeral_ids = new Set<number>();

/**
 * Check if a submessage is an ephemeral response that should be rendered.
 */
export function is_ephemeral_submessage(submessage: {
    visible_to?: number[] | null | undefined;
    content: string;
}): boolean {
    // Must have visibility restriction
    if (!submessage.visible_to || submessage.visible_to.length === 0) {
        return false;
    }

    // Try to parse content to check type
    try {
        const parsed = JSON.parse(submessage.content);
        return (
            parsed.type === "ephemeral_response" ||
            parsed.type === "bot_response"
        );
    } catch {
        return false;
    }
}

/**
 * Render ephemeral responses attached to a message row.
 */
export function render_ephemeral_responses(
    $row: JQuery,
    message: Message,
): void {
    // Remove any existing ephemeral responses
    $row.find(".ephemeral-response-container").remove();

    // Find ephemeral submessages
    const ephemeral_submessages = message.submessages.filter(
        (sm) =>
            is_ephemeral_submessage(sm) &&
            !dismissed_ephemeral_ids.has(sm.id),
    );

    if (ephemeral_submessages.length === 0) {
        return;
    }

    // Create container for ephemeral responses
    const $container = $('<div class="ephemeral-response-container"></div>');

    for (const submessage of ephemeral_submessages) {
        try {
            const parsed = JSON.parse(submessage.content);
            const result = ephemeral_response_schema.safeParse(parsed);

            if (!result.success) {
                blueslip.warn("Invalid ephemeral response data", {
                    issues: result.error.issues,
                });
                continue;
            }

            const data = result.data;

            // Determine visibility text
            const visible_to = submessage["visible_to"] ?? [];
            let visibility_text: string;
            if (visible_to.length === 1) {
                visibility_text = "Only visible to you";
            } else {
                const visible_names = visible_to
                    .map((id: number) => {
                        const person = people.maybe_get_user_by_id(id);
                        return person?.full_name ?? `User ${id}`;
                    })
                    .join(", ");
                visibility_text = `Visible to: ${visible_names}`;
            }

            // Render markdown content
            const rendered_content = markdown.parse_non_message(data.content);

            // Render the ephemeral response
            const html = render_ephemeral_response({
                submessage_id: submessage.id,
                content: rendered_content,
                visibility_text,
                has_widget: !!data.widget_content,
            });

            const $response = $(html);

            // Bind dismiss handler
            $response.find(".ephemeral-dismiss").on("click", function (e) {
                e.preventDefault();
                e.stopPropagation();
                dismiss_ephemeral(submessage.id);
                $response.fadeOut(200, function () {
                    $(this).remove();
                    // Remove container if empty
                    if ($container.children().length === 0) {
                        $container.remove();
                    }
                });
            });

            $container.append($response);
        } catch (error) {
            blueslip.error("Error rendering ephemeral response", undefined, error);
        }
    }

    // Append to messagebox-content grid (after reactions/reminders)
    // We target .messagebox-content directly to ensure proper grid placement,
    // avoiding the .message_content inside .message_sender for status messages.
    $row.find(".messagebox-content").append($container);
}

/**
 * Dismiss an ephemeral message so it won't be shown again.
 * Also deletes from the server.
 */
export function dismiss_ephemeral(submessage_id: number): void {
    dismissed_ephemeral_ids.add(submessage_id);

    // Delete from server
    void channel.del({
        url: "/json/submessage",
        data: {submessage_id: JSON.stringify(submessage_id)},
        error(xhr) {
            blueslip.warn("Failed to delete ephemeral submessage", {
                submessage_id,
                status: xhr.status,
            });
        },
    });
}

/**
 * Check if an ephemeral message has been dismissed.
 */
export function is_dismissed(submessage_id: number): boolean {
    return dismissed_ephemeral_ids.has(submessage_id);
}

/**
 * Clear all dismissed ephemeral messages (for testing).
 */
export function clear_dismissed(): void {
    dismissed_ephemeral_ids.clear();
}
