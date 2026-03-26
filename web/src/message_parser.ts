// We only use jquery for parsing.
import $ from "jquery";

import * as emoji from "./emoji.ts";
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

export function message_has_reaction(message: Message): boolean {
    return message.clean_reactions.size > 0;
}

export function message_has_specific_reaction(message: Message, reaction_name: string): boolean {
    if (message.clean_reactions.size === 0) {
        return false;
    }

    // Resolve the reaction name to an emoji_code for comparison,
    // since the same emoji may be stored under different names
    // (e.g., "hundred_points" vs "100" both map to code "1f4af").
    const emoji_details = emoji.get_emoji_details_by_name(reaction_name);
    return [...message.clean_reactions.values()].some(
        (reaction) =>
            reaction.emoji_code === emoji_details.emoji_code &&
            reaction.reaction_type === emoji_details.reaction_type,
    );
}
