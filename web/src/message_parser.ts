// We only use jquery for parsing.
import $ from "jquery";

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
    return is_element_in_message_content(message_content, ".message_inline_image");
}

export function message_has_attachment(message_content: string): boolean {
    return is_element_in_message_content(message_content, "a[href^='/user_uploads']");
}

export function message_has_reaction(message: Message): boolean {
    return message.clean_reactions.size > 0;
}
