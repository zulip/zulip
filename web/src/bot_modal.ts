import $ from "jquery";
import * as z from "zod/mini";

import render_bot_modal from "../templates/bot_modal.hbs";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import * as dialog_widget from "./dialog_widget.ts";

// Schema for text input component
const text_input_schema = z.object({
    type: z.literal("text_input"),
    custom_id: z.string(),
    label: z.string(),
    style: z.optional(z.enum(["short", "paragraph"])),
    placeholder: z.optional(z.string()),
    value: z.optional(z.string()),
    min_length: z.optional(z.number()),
    max_length: z.optional(z.number()),
    required: z.optional(z.boolean()),
});

// Component is just text_input for now, can be extended
const modal_component_schema = text_input_schema;

// Action row containing components
const modal_action_row_schema = z.object({
    type: z.literal("action_row"),
    components: z.array(modal_component_schema),
});

// Full modal data schema
export const bot_modal_schema = z.object({
    custom_id: z.string(),
    title: z.string(),
    components: z.array(modal_action_row_schema),
});

export type BotModalData = z.infer<typeof bot_modal_schema>;

function post_modal_submit(
    message_id: number,
    custom_id: string,
    fields: Record<string, string>,
): void {
    void channel.post({
        url: "/json/bot_interactions",
        data: {
            message_id: JSON.stringify(message_id),
            interaction_type: "modal_submit",
            custom_id,
            data: JSON.stringify({fields}),
        },
    });
}

export function show_bot_modal(message_id: number, modal_data: BotModalData): void {
    const parse_result = bot_modal_schema.safeParse(modal_data);
    if (!parse_result.success) {
        blueslip.error("invalid bot modal data", {issues: parse_result.error.issues});
        return;
    }

    const data = parse_result.data;

    // Transform components for template
    const template_data = {
        components: data.components.map((row) => ({
            components: row.components.map((comp) => ({
                is_text_input: true,
                is_paragraph: comp.style === "paragraph",
                ...comp,
            })),
        })),
    };

    const html_body = render_bot_modal(template_data);

    dialog_widget.launch({
        text_heading: data.title,
        html_body,
        html_submit_button: "Submit",
        form_id: "bot-modal-form",
        loading_spinner: true,
        on_click() {
            // Collect all input values
            const fields: Record<string, string> = {};
            const $form = $("#bot-modal-form");

            $form.find(".bot-modal-input").each(function () {
                const $input = $(this);
                const name = $input.attr("name");
                if (name) {
                    fields[name] = String($input.val() ?? "");
                }
            });

            // Submit to bot
            post_modal_submit(message_id, data.custom_id, fields);

            // Close the modal
            dialog_widget.close();
        },
        validate_input() {
            const $form = $("#bot-modal-form");
            const form = $form[0];
            if (form instanceof HTMLFormElement && !form.checkValidity()) {
                form.reportValidity();
                return false;
            }
            return true;
        },
    });
}

// Handle modal trigger from widget events
export function handle_modal_event(message_id: number, modal_data: unknown): void {
    const parse_result = bot_modal_schema.safeParse(modal_data);
    if (!parse_result.success) {
        blueslip.warn("received invalid modal event data", {issues: parse_result.error.issues});
        return;
    }

    show_bot_modal(message_id, parse_result.data);
}
