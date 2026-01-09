import $ from "jquery";
import * as z from "zod/mini";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import type {Message} from "./message_store.ts";
import {current_user} from "./state_data.ts";
import type {Event} from "./widget_data.ts";
import type {WidgetExtraData} from "./widgetize.ts";

const dependency_schema = z.object({
    url: z.string(),
    type: z.enum(["script", "style"]),
});

export const freeform_extra_data_schema = z.object({
    html: z.string(),
    css: z.optional(z.string()),
    js: z.optional(z.string()),
    // External dependencies loaded once and shared across all freeform widgets
    dependencies: z.optional(z.array(dependency_schema)),
});

// Track loaded dependencies globally to avoid duplicate loading
const loaded_dependencies = new Set<string>();
const loading_dependencies = new Map<string, Promise<void>>();

async function load_dependency(dep: {url: string; type: "script" | "style"}): Promise<void> {
    // Already loaded
    if (loaded_dependencies.has(dep.url)) {
        return;
    }

    // Currently loading - wait for it
    const existing = loading_dependencies.get(dep.url);
    if (existing) {
        return existing;
    }

    // Start loading
    const promise = new Promise<void>((resolve, reject) => {
        if (dep.type === "script") {
            const script = document.createElement("script");
            script.src = dep.url;
            script.onload = (): void => {
                loaded_dependencies.add(dep.url);
                loading_dependencies.delete(dep.url);
                resolve();
            };
            script.onerror = (): void => {
                loading_dependencies.delete(dep.url);
                reject(new Error(`Failed to load script: ${dep.url}`));
            };
            document.head.append(script);
        } else {
            const link = document.createElement("link");
            link.rel = "stylesheet";
            link.href = dep.url;
            link.onload = (): void => {
                loaded_dependencies.add(dep.url);
                loading_dependencies.delete(dep.url);
                resolve();
            };
            link.onerror = (): void => {
                loading_dependencies.delete(dep.url);
                reject(new Error(`Failed to load stylesheet: ${dep.url}`));
            };
            document.head.append(link);
        }
    });

    loading_dependencies.set(dep.url, promise);
    return promise;
}

async function load_all_dependencies(
    deps: Array<{url: string; type: "script" | "style"}>,
): Promise<void> {
    await Promise.all(deps.map((dep) => load_dependency(dep)));
}

type SubmessageData = {
    submessage_id: number;
    sender_id: number;
    msg_type: string;
    content: unknown;
};

type WidgetContext = {
    message_id: number;
    post_interaction: (data: Record<string, unknown>) => void;
    post_submessage: (data: Record<string, unknown>) => Promise<void>;
    on_submessage: (callback: (data: SubmessageData) => void) => void;
    on: (event: string, selector: string, handler: (e: JQuery.Event) => void) => void;
    update_html: (html: string) => void;
    current_user: {
        user_id: number;
        full_name: string;
        avatar_url?: string;
    };
    // Initial submessages that existed when widget was rendered
    initial_submessages: SubmessageData[];
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

    async function post_submessage(submessage_data: Record<string, unknown>): Promise<void> {
        await channel.post({
            url: "/json/submessage",
            data: {
                message_id: JSON.stringify(message.id),
                msg_type: "widget",
                content: JSON.stringify(submessage_data),
            },
        });
    }

    // Callbacks registered by widgets to receive submessage events
    const submessage_callbacks: Array<(data: SubmessageData) => void> = [];

    function on_submessage(callback: (data: SubmessageData) => void): void {
        submessage_callbacks.push(callback);
    }

    // Extract initial submessages from message (if available)
    const initial_submessages: SubmessageData[] = (message.submessages ?? [])
        .filter((sm) => sm.msg_type === "widget")
        .map((sm) => ({
            submessage_id: sm.id,
            sender_id: sm.sender_id,
            msg_type: sm.msg_type,
            content: JSON.parse(sm.content) as unknown,
        }));

    async function render(): Promise<void> {
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

        // Load external dependencies before executing JS
        if (data.dependencies && data.dependencies.length > 0) {
            try {
                await load_all_dependencies(data.dependencies);
            } catch (error) {
                blueslip.error("Error loading freeform widget dependencies", {error});
                return;
            }
        }

        // Execute JS if provided
        if (data.js) {
            const ctx: WidgetContext = {
                message_id: message.id,
                post_interaction,
                post_submessage,
                on_submessage,
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
                current_user: {
                    user_id: current_user.user_id,
                    full_name: current_user.full_name,
                    ...(current_user.avatar_url && {avatar_url: current_user.avatar_url}),
                },
                initial_submessages,
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

    void render();

    // Handle events - could be used for bot-initiated updates or submessages
    return (events: Event[]): void => {
        for (const event of events) {
            // Route all events to submessage callbacks for live updates
            for (const callback of submessage_callbacks) {
                callback({
                    submessage_id: 0, // Not available in live events, use initial_submessages for historical IDs
                    sender_id: event.sender_id,
                    msg_type: "widget",
                    content: event.data,
                });
            }

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
                // Update dependencies if provided
                if (
                    "dependencies" in event_data &&
                    Array.isArray(event_data.dependencies)
                ) {
                    data.dependencies = event_data.dependencies as Array<{
                        url: string;
                        type: "script" | "style";
                    }>;
                }
                void render();
            }
        }
    };
}
