// We only use jquery for parsing.
import $ from "jquery";

// TODO: Move this to message_store when it is
// converted to TypeScript.
type Message = {
    content: string;
};

// We need to check if the message content contains the specified HTML
// elements.  We wrap the message.content in a <div>; this is
// important because $("Text <a>link</a>").find("a") returns nothing;
// one needs an outer element wrapping an object to use this
// construction.
function is_element_in_message_content(message: Message, element_selector: string): boolean {
    return $(`<div>${message.content}</div>`).find(`${element_selector}`).length > 0;
}

export function message_has_link(message: Message): boolean {
    return is_element_in_message_content(message, "a");
}

export function message_has_image(message: Message): boolean {
    return is_element_in_message_content(message, ".message_inline_image");
}

export function message_has_attachment(message: Message): boolean {
    return is_element_in_message_content(message, "a[href^='/user_uploads']");
}
