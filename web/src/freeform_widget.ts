import $ from "jquery";
import * as z from "zod/mini";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import type {Message} from "./message_store.ts";
import type {Event} from "./widget_data.ts";
import type {WidgetExtraData} from "./widgetize.ts";

export const freeform_extra_data_schema = z.object({
    html: z.string(),
    css: z.optional(z.string()),
    js: z.optional(z.string()),
});

type WidgetContext = {
    message_id: number;
    post_interaction: (data: Record<string, unknown>) => void;
    on: (event: string, selector: string, handler: (e: JQuery.Event) => void) => void;
    update_html: (html: string) => void;
};

function scope_css(css: string, message_id: number): string {
    // Scope CSS rules to this specific widget
    const scope = `.widget-freeform-${message_id}`;
    // Simple CSS scoping - prepend scope to each rule
    return css.replaceAll(/([^{}]+)\{/g, (_full_match, selector: string) => {
        const scoped_selectors = selector
            .split(",")
            .map((s: string) => `${scope} ${s.trim()}`)
            .join(", ");
        return `${scoped_selectors} {`;
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
    const parse_result = freeform_extra_data_schema.safeParse(extra_data);
    if (!parse_result.success) {
        blueslip.error("invalid freeform widget extra data", {issues: parse_result.error.issues});
        return (_events: Event[]): void => {
            /* noop */
        };
    }

    const data = parse_result.data;
    const widget_class = `widget-freeform-${message.id}`;

    function post_interaction(interaction_data: Record<string, unknown>): void {
        void channel.post({
            url: "/json/bot_interactions",
            data: {
                message_id: JSON.stringify(message.id),
                interaction_type: "freeform",
                custom_id: "freeform",
                data: JSON.stringify(interaction_data),
            },
        });
    }

    function render(): void {
        // Create container with scoped class
        const $container = $(`<div class="widget-freeform ${widget_class}"></div>`);

        // Add scoped CSS if provided
        if (data.css) {
            const scoped_css = scope_css(data.css, message.id);
            const $style = $(`<style>${scoped_css}</style>`);
            $container.append($style);
        }

        // Add HTML content - freeform widgets are from trusted bots
        // eslint-disable-next-line no-jquery/no-append-html
        $container.append(data.html);

        $elem.html("");
        $elem.append($container);

        // Execute JS if provided
        if (data.js) {
            const ctx: WidgetContext = {
                message_id: message.id,
                post_interaction,
                on(event: string, selector: string, handler: (e: JQuery.Event) => void): void {
                    $container.on(event, selector, handler);
                },
                update_html(html: string): void {
                    // Preserve style element when updating HTML
                    const $style = $container.find("style");
                    $container.html("");
                    if ($style.length > 0) {
                        $container.append($style);
                    }
                    // eslint-disable-next-line no-jquery/no-append-html -- Freeform widgets are trusted bot content
                    $container.append(html);
                },
            };

            try {
                // Execute the JS with the context
                // Freeform widgets allow trusted bots to execute arbitrary JavaScript
                // eslint-disable-next-line @typescript-eslint/no-implied-eval, no-new-func
                const fn = new Function("ctx", "container", data.js);
                // eslint-disable-next-line @typescript-eslint/no-unsafe-call
                fn(ctx, $container[0]);
            } catch (error) {
                blueslip.error("Error executing freeform widget JS", {error});
            }
        }
    }

    render();

    // Handle events - could be used for bot-initiated updates
    return (events: Event[]): void => {
        for (const event of events) {
            const event_data = event.data;
            if (
                event_data &&
                typeof event_data === "object" &&
                "type" in event_data &&
                typeof event_data.type === "string" &&
                event_data.type === "update"
            ) {
                // Update the widget content
                if ("html" in event_data && typeof event_data.html === "string") {
                    data.html = event_data.html;
                }
                if ("css" in event_data && typeof event_data.css === "string") {
                    data.css = event_data.css;
                }
                if ("js" in event_data && typeof event_data.js === "string") {
                    data.js = event_data.js;
                }
                render();
            }
        }
    };
}
