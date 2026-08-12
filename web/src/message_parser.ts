// We only use jquery for parsing.
import {$} from "jquery";

import type {Message} from "./message_store.ts";

// We need to check if the message content contains the specified HTML
// elements.  We wrap the message.content in a <div>; this is
// important because $("Text <a>link</a>").find("a") returns nothing;
// one needs an outer element wrapping an object to use this
// construction.
function is_element_in_message_content(message_content: string, element_selector: string): boolean {
    return $(`<div>${message_content}</div>`).find(element_selector).length > 0;
}

export function message_has_link(message_content: string): boolean {
    return is_element_in_message_content(message_content, "a");
}

export function message_has_image(message_content: string): boolean {
    return is_element_in_message_content(message_content, ".message_inline_image, .inline-image");
}

export function message_has_attachment(message_content: string): boolean {
    return is_element_in_message_content(
        message_content,
        "a[href^='/user_uploads'], img[src^='/user_uploads'], audio[src^='/user_uploads']",
    );
}

export function message_has_link_preview(message_content: string): boolean {
    // Inline image and video previews are excluded because Markdown drops
    // the link when the message body is a bare URL, leaving the preview as
    // the only content; hiding it would blank the message. Video previews
    // always keep their link, so they are safe to hide. .vimeo-video is
    // legacy markup for Vimeo, still present in stored rendered content.
    return is_element_in_message_content(
        message_content,
        ".message_embed, .youtube-video, .embed-video, .vimeo-video",
    );
}

export function message_has_reaction(message: Message): boolean {
    return message.clean_reactions.size > 0;
}
