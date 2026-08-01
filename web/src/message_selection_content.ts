// Helpers for multi-message selection body coverage (first/last bookends and
// which rows contribute message content).
//
// Partial bookends are only resolved for a single selection range (Chrome and
// modern Firefox). When the browser splits a multi-message selection into
// multiple ranges (older Firefox), partial first/last content is not recovered
// and callers use full message bodies:
// https://chat.zulip.org/#narrow/channel/101-design/topic/Improve.20the.20message.20copying.20experience.20.236316/with/681915

import {$} from "jquery";
import assert from "minimalistic-assert";

import * as message_lists from "./message_lists.ts";
import * as rows from "./rows.ts";
import {the} from "./util.ts";

export type RangeContainer = "start" | "end";

export type BookendContentHtml = {
    html: string;
    is_partial: boolean;
};

export type MultiMessageSelectionContent = {
    message_ids: number[];
    // Undefined means the caller should use the full message body.
    first: BookendContentHtml | undefined;
    last: BookendContentHtml | undefined;
};

// Returns the selected `.message_content`s in the current range.
function get_selected_message_content_elements(): NodeListOf<HTMLElement> | undefined {
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
function get_html_for_bookend_message_content(
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
    //
    // For a start bookend, also insert a zero-width space after the marker.
    // If the selection continues with "(", converting the HTML to markdown
    // would otherwise treat the marker as the label of a link.
    const ellipsis_text = type === "start" ? "[...]\u{200B}" : "[...]";
    const $ellipsis_span = $("<span>").text(ellipsis_text);
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

function message_content_element_for_id(message_id: number): Element {
    assert(message_lists.current !== undefined);
    const $row = message_lists.current.get_row(message_id);
    assert($row.length > 0);
    const content = the($row).querySelector(".message_content");
    assert(content !== null);
    return content;
}

// Returns contentful message ids for the selection from start_id through end_id, plus
// first/last bookend HTML when a single range allows partial recovery.
//
// Returns undefined when there are no contentful messages (e.g. empty visible
// range, or username-only / no `.message_content` in a single-range selection).
//
// Multi-range selections (older Firefox): returns all visible row ids between
// the endpoints and leaves first/last undefined so callers use full bodies.
export function get_multi_message_selection_content(
    start_id: number,
    end_id: number,
): MultiMessageSelectionContent | undefined {
    const content_rows = rows.visible_range(start_id, end_id);
    if (content_rows.length === 0) {
        return undefined;
    }

    const range_count = window.getSelection()?.rangeCount ?? 0;
    // Multi-range selections do not attempt the trailing username-only
    // drop or partial bookends; callers use full bodies for every row.
    if (range_count !== 1) {
        return {
            message_ids: content_rows.map(($row) => rows.id($row)),
            first: undefined,
            last: undefined,
        };
    }

    const selected_message_content_elements = get_selected_message_content_elements();
    assert(selected_message_content_elements !== undefined);

    // Happens for a special case:
    // Highlighting the timestamp from a /me message, followed by highlighting the
    // username from the following message.
    if (selected_message_content_elements.length === 0) {
        return undefined;
    }

    // Case where the last message doesn't have any highlighted `.message_content`.
    // Here, end_id is set to id of the message whose username at the top
    // was highlighted, but has no highlighted `.message_content`.
    // (See analyze_selection for details.)
    // So the actually useful/contentful last message of this selection is
    // at content_rows[content_rows.length - 2]
    if (selected_message_content_elements.length === content_rows.length - 1) {
        content_rows.splice(-1, 1);
        if (content_rows.length === 0) {
            // In case this just involved selecting the username of a message.
            return undefined;
        }
    }

    const message_ids = content_rows.map(($row) => rows.id($row));
    assert(message_ids.length > 0);

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

    return {message_ids, first, last};
}
