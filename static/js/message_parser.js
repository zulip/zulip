// We only use jquery for parsing.
import $ from "jquery";

// We need to check if the message content contains the specified HTML
// elements.  We wrap the message.content in a <div>; this is
// important because $("Text <a>link</a>").find("a") returns nothing;
// one needs an outer element wrapping an object to use this
// construction.
function is_element_in_message_content(message, element_selector) {
    return $(`<div>${message.content}</div>`).find(`${element_selector}`).length > 0;
}

export function message_has_link(message) {
    return is_element_in_message_content(message, "a");
}

export function message_has_image(message) {
    return is_element_in_message_content(message, ".message_inline_image");
}

export function message_has_attachment(message) {
    return is_element_in_message_content(message, "a[href^='/user_uploads']");
}
