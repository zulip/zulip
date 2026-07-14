import $ from "jquery";
import assert from "minimalistic-assert";

import {the} from "./util.ts";

export type RangeContainer = "start" | "end";

// Returns the selected `.message_content`s in the current range.
export function get_selected_message_content_elements(): NodeListOf<HTMLElement> | undefined {
    return document
        .getSelection()
        ?.getRangeAt(0)
        .cloneContents()
        .querySelectorAll(".message_content");
}

// Returns the the inner HTML of the `.message_content` element
// for the first or last message of a single range selection.
// The caller is expected to only pass the first or last message
// from a selection range, as the intermediate selected messages
// anyways contain the entire `.message_content` HTML.
export function get_html_for_bookend_message_content(
    type: RangeContainer,
    original_message_content_element: Element,
    selected_message_content_element: Node | undefined,
): string {
    assert(window.getSelection()?.rangeCount === 1);
    assert(
        selected_message_content_element !== undefined &&
            selected_message_content_element instanceof HTMLElement,
    );

    // Special case for /me messages.
    // We wrap the /me message content in a `div` to ensure newlines are
    // inserted before and after the message content, which is important
    // when copy pasting multiple messages.
    if (selected_message_content_element.classList.contains("status-message")) {
        return `<div>` + selected_message_content_element.outerHTML + `</div>`;
    }

    // If the selected `.message_content` HTML is same as the complete `.message_content` HTML,
    // we return early and don't append/prepend ellipsis text.
    if (
        selected_message_content_element.innerHTML.trim() ===
        original_message_content_element.innerHTML.trim()
    ) {
        return selected_message_content_element.innerHTML;
    }

    // The ellipsis marks where the partial selection was truncated, so it
    // belongs within the text flow of the truncated paragraph. Inserting it
    // inside the first/last paragraph (rather than as a sibling of it) keeps
    // turndown from rendering it on its own line, separated from the text by
    // a blank line.
    const $ellipsis_span = $("<span>").text("...");
    const $content_children = $(selected_message_content_element).children();
    if (type === "start") {
        const $first_child = $content_children.first();
        if ($first_child.is("p")) {
            the($first_child).prepend(the($ellipsis_span));
        } else {
            selected_message_content_element.prepend(the($ellipsis_span));
        }
    } else {
        const $last_child = $content_children.last();
        if ($last_child.is("p")) {
            the($last_child).append(the($ellipsis_span));
        } else {
            selected_message_content_element.append(the($ellipsis_span));
        }
    }
    return selected_message_content_element.innerHTML;
}
