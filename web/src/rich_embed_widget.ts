import {z} from "zod";

import render_rich_embed_widget from "../templates/widgets/rich_embed_widget.hbs";

import * as blueslip from "./blueslip.ts";
import type {Message} from "./message_store.ts";
import type {Event} from "./widget_data.ts";
import type {WidgetExtraData} from "./widgetize.ts";

const rich_embed_field_schema = z.object({
    name: z.string(),
    value: z.string(),
    inline: z.boolean().optional(),
});

const rich_embed_footer_schema = z.object({
    text: z.string(),
    icon_url: z.string().optional(),
});

const rich_embed_media_schema = z.object({
    url: z.string(),
});

const rich_embed_author_schema = z.object({
    name: z.string(),
    url: z.string().optional(),
    icon_url: z.string().optional(),
});

export const rich_embed_extra_data_schema = z.object({
    title: z.string().optional(),
    description: z.string().optional(),
    url: z.string().optional(),
    color: z.number().optional(),
    timestamp: z.string().optional(),
    footer: rich_embed_footer_schema.optional(),
    thumbnail: rich_embed_media_schema.optional(),
    image: rich_embed_media_schema.optional(),
    author: rich_embed_author_schema.optional(),
    fields: z.array(rich_embed_field_schema).optional(),
});

type RichEmbedExtraData = z.infer<typeof rich_embed_extra_data_schema>;

function int_to_hex_color(color: number): string {
    // Convert integer color to CSS hex color
    return "#" + color.toString(16).padStart(6, "0");
}

function format_timestamp(timestamp: string): string {
    try {
        const date = new Date(timestamp);
        return date.toLocaleString();
    } catch {
        return timestamp;
    }
}

export function activate({
    $elem,
    extra_data,
}: {
    $elem: JQuery;
    callback: (data: Record<string, unknown>) => void;
    extra_data: WidgetExtraData;
    message: Message;
}): (events: Event[]) => void {
    const parse_result = rich_embed_extra_data_schema.safeParse(extra_data);
    if (!parse_result.success) {
        blueslip.error("invalid rich_embed widget extra data", {issues: parse_result.error.issues});
        return (_events: Event[]): void => {
            /* noop */
        };
    }

    const data = parse_result.data;

    function render(): void {
        const template_data: RichEmbedExtraData & {
            color_css?: string;
            formatted_timestamp?: string;
            has_fields?: boolean;
        } = {...data};

        if (data.color !== undefined) {
            template_data.color_css = int_to_hex_color(data.color);
        }

        if (data.timestamp !== undefined) {
            template_data.formatted_timestamp = format_timestamp(data.timestamp);
        }

        if (data.fields && data.fields.length > 0) {
            template_data.has_fields = true;
        }

        const html = render_rich_embed_widget(template_data);
        $elem.html(html);
    }

    render();

    // Rich embeds are static - no event handling needed
    return (_events: Event[]): void => {
        /* noop */
    };
}
