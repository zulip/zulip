// Helpers for multi-message selection body coverage (first/last bookends and
// which rows contribute message content).
//
// Partial bookends are only resolved for a single selection range (Chrome and
// modern Firefox). When the browser splits a multi-message selection into
// multiple ranges (older Firefox), partial first/last content is not recovered
// and callers use full message bodies:
// https://chat.zulip.org/#narrow/channel/101-design/topic/Improve.20the.20message.20copying.20experience.20.236316/with/681915

import $ from "jquery";
import assert from "minimalistic-assert";

import * as message_lists from "./message_lists.ts";
import * as rows from "./rows.ts";
import {the} from "./util.ts";

export type RangeContainer = "start" | "end";

export type BookendContentHtml = {
    html: string;
    is_partial: boolean;
};

export type MultiMessageBookendHtml = {
    // Undefined means the caller should use the full message body.
    first: BookendContentHtml | undefined;
    last: BookendContentHtml | undefined;
};

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
//
// Also reports whether the selection is partial (`is_partial`).
// Mutates `selected_message_content_element` when inserting ellipsis text.
export function get_html_for_bookend_message_content(
    type: RangeContainer,
    original_message_content_element: Element,
    selected_message_content_element: Node | undefined,
): BookendContentHtml {
    assert(
        selected_message_content_element !== undefined &&
            selected_message_content_element instanceof HTMLElement,
    );

    // Special case for /me messages.
    // We wrap the /me message content in a `div` to ensure newlines are
    // inserted before and after the message content, which is important
    // when copy pasting multiple messages.
    if (selected_message_content_element.classList.contains("status-message")) {
        return {
            html: `<div>` + selected_message_content_element.outerHTML + `</div>`,
            // Status messages are treated as whole units for selection.
            is_partial: false,
        };
    }

    // If the selected `.message_content` HTML is same as the complete `.message_content` HTML,
    // we return early and don't append/prepend ellipsis text.
    if (
        selected_message_content_element.innerHTML.trim() ===
        original_message_content_element.innerHTML.trim()
    ) {
        return {
            html: selected_message_content_element.innerHTML,
            is_partial: false,
        };
    }

    // The ellipsis marks where the partial selection was truncated, so it
    // belongs within the text flow of the truncated paragraph. Inserting it
    // inside the first/last paragraph (rather than as a sibling of it) keeps
    // turndown from rendering it on its own line, separated from the text by
    // a blank line.
    const $ellipsis_span = $("<span>").text("[...]");
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
    return {
        html: selected_message_content_element.innerHTML,
        is_partial: true,
    };
}

// Contentful message ids from start_id through end_id (inclusive), after
// dropping a trailing username-only row when applicable.
export function get_selected_contentful_message_ids(
    start_id: number,
    end_id: number,
): number[] | undefined {
    const content_rows = [...rows.visible_range(start_id, end_id)];
    if (content_rows.length === 0) {
        return undefined;
    }

    const range_count = window.getSelection()?.rangeCount ?? 0;
    // Multi-range selections do not attempt the trailing username-only
    // drop; copy expands bookends and uses full bodies for every row.
    if (range_count !== 1) {
        return content_rows.map(($row) => rows.id($row));
    }

    const selected_message_content_elements = get_selected_message_content_elements();
    if (selected_message_content_elements === undefined) {
        return undefined;
    }

    // Case where the last message doesn't have any highlighted `.message_content`.
    // Here, end_id is set to id of the message whose username at the top
    // was highlighted, but has no highlighted `.message_content`.
    // (See analyze_selection for details.)
    // So the actually useful/contentful last message of this selection is
    // at copy_rows[copy_rows.length - 2]
    if (selected_message_content_elements.length === content_rows.length - 1) {
        content_rows.splice(-1, 1);
        if (content_rows.length === 0) {
            // In case this just involved selecting the username of a message.
            return undefined;
        }
    }

    return content_rows.map(($row) => rows.id($row));
}

function message_content_element_for_id(message_id: number): Element {
    assert(message_lists.current !== undefined);
    const $row = message_lists.current.get_row(message_id);
    assert($row.length > 0);
    const content = the($row).querySelector(".message_content");
    assert(content !== null);
    return content;
}

// First/last bookend HTML for the given contentful message ids. When
// rangeCount > 1, first and last are undefined (callers use full bodies).
export function get_multi_message_bookend_contents(message_ids: number[]): MultiMessageBookendHtml {
    assert(message_ids.length > 0);

    const range_count = window.getSelection()?.rangeCount ?? 0;
    if (range_count !== 1) {
        return {first: undefined, last: undefined};
    }

    const selected_message_content_elements = get_selected_message_content_elements();
    if (
        selected_message_content_elements === undefined ||
        selected_message_content_elements.length === 0
    ) {
        return {first: undefined, last: undefined};
    }

    const first_id = message_ids[0]!;
    const last_id = message_ids.at(-1)!;
    const first_original = message_content_element_for_id(first_id);
    const last_original = message_content_element_for_id(last_id);

    const first = get_html_for_bookend_message_content(
        "start",
        first_original,
        selected_message_content_elements[0],
    );

    // Avoid treating a single selected fragment as both first and last when
    // only one `.message_content` appears in the cloned selection across
    // multiple rows (last then falls back to full body).
    let last: BookendContentHtml | undefined;
    if (message_ids.length === 1) {
        last = first;
    } else if (selected_message_content_elements.length > 1) {
        const len = selected_message_content_elements.length;
        last = get_html_for_bookend_message_content(
            "end",
            last_original,
            selected_message_content_elements[len - 1],
        );
    }

    return {first, last};
}
