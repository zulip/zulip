// We only use jquery for parsing.
import $ from "jquery";

import type {Message} from "./message_store";

// We need to check if the message content contains the specified HTML
// elements.  We wrap the message.content in a <div>; this is
// important because $("Text <a>link</a>").find("a") returns nothing;
// one needs an outer element wrapping an object to use this
// construction.
const is_element_in_message_content = (message: Message, element_selector: string): boolean =>
    $(`<div>${message.content}</div>`).find(element_selector).length > 0;

export const message_has_link = (message: Message): boolean =>
    is_element_in_message_content(message, "a");

export const message_has_image = (message: Message): boolean =>
    is_element_in_message_content(message, ".message_inline_image");

export const message_has_attachment = (message: Message): boolean =>
    is_element_in_message_content(message, "a[href^='/user_uploads']");
