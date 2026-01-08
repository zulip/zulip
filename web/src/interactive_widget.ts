import $ from "jquery";
import * as z from "zod/mini";

import render_interactive_widget from "../templates/widgets/interactive_widget.hbs";

import * as blueslip from "./blueslip.ts";
import * as bot_modal from "./bot_modal.ts";
import * as channel from "./channel.ts";
import type {Message} from "./message_store.ts";
import type {Event} from "./widget_data.ts";
import type {WidgetExtraData} from "./widgetize.ts";

// Modal schema for buttons that open modals
const button_modal_schema = z.object({
    custom_id: z.string(),
    title: z.string(),
    components: z.array(
        z.object({
            type: z.literal("action_row"),
            components: z.array(
                z.object({
                    type: z.literal("text_input"),
                    custom_id: z.string(),
                    label: z.string(),
                    style: z.optional(z.enum(["short", "paragraph"])),
                    placeholder: z.optional(z.string()),
                    value: z.optional(z.string()),
                    min_length: z.optional(z.number()),
                    max_length: z.optional(z.number()),
                    required: z.optional(z.boolean()),
                }),
            ),
        }),
    ),
});

const button_schema = z.object({
    type: z.literal("button"),
    label: z.string(),
    style: z.optional(z.enum(["primary", "secondary", "success", "danger", "link"])),
    custom_id: z.optional(z.string()),
    url: z.optional(z.string()),
    disabled: z.optional(z.boolean()),
    modal: z.optional(button_modal_schema),
});

const select_option_schema = z.object({
    label: z.string(),
    value: z.string(),
    description: z.optional(z.string()),
    default: z.optional(z.boolean()),
});

const select_menu_schema = z.object({
    type: z.literal("select_menu"),
    custom_id: z.string(),
    options: z.array(select_option_schema),
    placeholder: z.optional(z.string()),
    min_values: z.optional(z.number()),
    max_values: z.optional(z.number()),
    disabled: z.optional(z.boolean()),
});

const component_schema = z.discriminatedUnion("type", [button_schema, select_menu_schema]);

const action_row_schema = z.object({
    type: z.literal("action_row"),
    components: z.array(component_schema),
});

export const interactive_extra_data_schema = z.object({
    content: z.optional(z.string()),
    components: z.array(action_row_schema),
});

// Types inferred from schemas - exported for external use if needed
export type InteractiveExtraDataType = z.infer<typeof interactive_extra_data_schema>;

function post_interaction(
    message_id: number,
    interaction_type: string,
    custom_id: string,
    data: Record<string, unknown> = {},
): void {
    void channel.post({
        url: "/json/bot_interactions",
        data: {
            message_id: JSON.stringify(message_id),
            interaction_type,
            custom_id,
            data: JSON.stringify(data),
        },
    });
}

export function activate({
    $elem,
    extra_data,
    message,
}: {
    $elem: JQuery;
    callback: (data: Record<string, unknown>) => void;
    extra_data: WidgetExtraData;
    message: Message;
}): (events: Event[]) => void {
    const parse_result = interactive_extra_data_schema.safeParse(extra_data);
    if (!parse_result.success) {
        blueslip.error("invalid interactive widget extra data", {
            issues: parse_result.error.issues,
        });
        return (_events: Event[]): void => {
            /* noop */
        };
    }

    const data = parse_result.data;

    // Store button modal data by custom_id for lookup on click
    const button_modals = new Map<string, z.infer<typeof button_modal_schema>>();

    function render(): void {
        button_modals.clear();

        // Transform data for template
        const template_data = {
            content: data.content,
            action_rows: data.components.map((row) => ({
                components: row.components.map((comp) => {
                    if (comp.type === "button") {
                        // Store modal data if present
                        if (comp.modal && comp.custom_id) {
                            button_modals.set(comp.custom_id, comp.modal);
                        }
                        return {
                            is_button: true,
                            ...comp,
                            style: comp.style ?? "secondary",
                            has_modal: Boolean(comp.modal),
                        };
                    }
                    return {
                        is_select: true,
                        ...comp,
                    };
                }),
            })),
        };

        const html = render_interactive_widget(template_data);
        $elem.html(html);

        // Bind button click handlers
        $elem.find(".widget-button").on("click", function (e) {
            e.stopPropagation();
            const $button = $(this);
            const custom_id = $button.attr("data-custom-id");
            const url = $button.attr("data-url");

            if (url) {
                // Link button - open URL
                window.open(url, "_blank", "noopener,noreferrer");
            } else if (custom_id) {
                // Check if button has modal data
                const modal_data = button_modals.get(custom_id);
                if (modal_data) {
                    // Show modal instead of posting interaction directly
                    bot_modal.show_bot_modal(message.id, modal_data);
                } else {
                    // Custom button - post interaction
                    $button.prop("disabled", true);
                    post_interaction(message.id, "button_click", custom_id);
                }
            }
        });

        // Bind select change handlers
        $elem.find(".widget-select").on("change", function (e) {
            e.stopPropagation();
            const $select = $(this);
            const custom_id = $select.attr("data-custom-id");
            const values = $select.val();

            if (custom_id && values) {
                post_interaction(message.id, "select_menu", custom_id, {
                    values: Array.isArray(values) ? values : [values],
                });
            }
        });
    }

    render();

    // Handle update events from bot
    return (events: Event[]): void => {
        for (const event of events) {
            const event_data = event.data;
            if (
                event_data &&
                typeof event_data === "object" &&
                "type" in event_data &&
                typeof event_data.type === "string"
            ) {
                if (event_data.type === "update") {
                    // Re-render with new data if the bot sends an update
                    // For now, we just re-render the existing data
                    render();
                } else if (
                    event_data.type === "show_modal" &&
                    "modal" in event_data &&
                    event_data.modal
                ) {
                    // Bot wants to show a modal dynamically
                    bot_modal.handle_modal_event(message.id, event_data.modal);
                }
            }
        }
    };
}
