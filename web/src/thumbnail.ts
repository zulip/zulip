import type * as z from "zod/mini";

import {realm} from "./state_data.ts";
import type {thumbnail_format_schema} from "./state_data.ts";

type ThumbnailFormat = z.infer<typeof thumbnail_format_schema>;

export const thumbnail_formats: ThumbnailFormat[] = [];

export let preferred_format: ThumbnailFormat;
export let animated_format: ThumbnailFormat;

export function initialize(): void {
    // Go looking for the size closest to 840px wide.  We assume all browsers
    // support webp.
    const format_preferences = ["webp", "jpg", "gif"];
    const sorted_formats = realm.server_thumbnail_formats.sort((a, b) => {
        if (a.max_width !== b.max_width) {
            return Math.abs(a.max_width - 840) < Math.abs(b.max_width - 840) ? -1 : 1;
        } else if (a.format !== b.format) {
            let a_index = format_preferences.indexOf(a.format);
            if (a_index === -1) {
                a_index = format_preferences.length;
            }
            let b_index = format_preferences.indexOf(b.format);
            if (b_index === -1) {
                b_index = format_preferences.length;
            }
            return a_index - b_index;
        }

        return 0;
    });
    preferred_format = sorted_formats.find((format) => !format.animated)!;
    animated_format = sorted_formats.find((format) => format.animated)!;
}
