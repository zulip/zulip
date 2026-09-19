import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_emoji_tooltip from "../templates/emoji_tooltip.hbs";

import {parse_html} from "./ui_util.ts";

// Reads the canonical `:name:` an emoji carries in the DOM, so we
// never rebuild it from the human-friendly `title` (which has spaces,
// not underscores): custom emoji (<img>) use `alt`, Unicode emoji
// (<span>) use their text content, status emoji use `data-tippy-content`.
export function get_canonical_emoji_name(emoji_element: Element): string | undefined {
    const raw =
        emoji_element.getAttribute("alt") ??
        emoji_element.getAttribute("data-tippy-content") ??
        emoji_element.textContent ??
        "";
    if (raw.startsWith(":") && raw.endsWith(":") && raw.length > 2) {
        return raw.slice(1, -1);
    }
    // Our caller needs to handle this possibility.
    return undefined;
}

// Builds the tooltip body: an enlarged copy of the emoji above its `:name:`.
export function build_emoji_tooltip_content(
    emoji_element: Element,
    emoji_name: string,
): DocumentFragment {
    const enlarged_emoji = emoji_element.cloneNode(true);
    assert(enlarged_emoji instanceof HTMLElement);
    // The clone is decorative (the `:name:` line carries the name), and
    // Unicode emoji have role="img", so hide it from assistive tech to
    // avoid announcing an unnamed image.
    enlarged_emoji.setAttribute("aria-hidden", "true");
    // Drop the native title and the name it duplicates, so the copy
    // can't show a tooltip of its own inside this one.
    enlarged_emoji.removeAttribute("title");
    enlarged_emoji.removeAttribute("aria-label");
    // Status emoji keep their tooltip in data-tippy-content, and layout
    // classes for sitting beside a name; neither suits the copy.
    enlarged_emoji.removeAttribute("data-tippy-content");
    enlarged_emoji.classList.remove("status-emoji", "status-emoji-name");
    enlarged_emoji.classList.add("emoji-tooltip-enlarged");

    const fragment = parse_html(render_emoji_tooltip({emoji_name}));
    const emoji_container = fragment.querySelector(".emoji-tooltip-emoji");
    assert(emoji_container !== null);
    emoji_container.append(enlarged_emoji);
    return fragment;
}

// Shared `onShow` for the emoji tooltip delegates: render the enlarged
// preview, or decline to show when the element carries no emoji name.
export function show_emoji_tooltip(instance: tippy.Instance): false | undefined {
    const emoji_name = get_canonical_emoji_name(instance.reference);
    if (emoji_name === undefined) {
        return false;
    }
    instance.setContent(build_emoji_tooltip_content(instance.reference, emoji_name));
    return undefined;
}
