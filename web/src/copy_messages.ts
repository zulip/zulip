// Because this logic is heavily focused around managing browser quirks,
// this module is currently tested manually and via
// by web/e2e-tests/copy_messages.test.ts, not with node tests.
import $ from "jquery";
import assert from "minimalistic-assert";

import * as message_lists from "./message_lists.ts";
import * as rows from "./rows.ts";

function find_boundary_tr(
    $initial_tr: JQuery,
    iterate_row: ($tr: JQuery) => JQuery,
): [number, boolean] | undefined {
    let j;
    let skip_same_td_check = false;
    let $tr = $initial_tr;

    // If the selection boundary is somewhere that does not have a
    // parent tr, we should let the browser handle the copy-paste
    // entirely on its own
    if ($tr.length === 0) {
        return undefined;
    }

    // If the selection boundary is on a table row that does not have an
    // associated message id (because the user clicked between messages),
    // then scan downwards until we hit a table row with a message id.
    // To ensure we can't enter an infinite loop, bail out (and let the
    // browser handle the copy-paste on its own) if we don't hit what we
    // are looking for within 10 rows.
    for (j = 0; !$tr.is(".message_row") && j < 10; j += 1) {
        $tr = iterate_row($tr);
    }
    if (j === 10) {
        return undefined;
    } else if (j !== 0) {
        // If we updated tr, then we are not dealing with a selection
        // that is entirely within one td, and we can skip the same td
        // check (In fact, we need to because it won't work correctly
        // in this case)
        skip_same_td_check = true;
    }
    return [rows.id($tr), skip_same_td_check];
}

function construct_recipient_header($message_row: JQuery): JQuery {
    const message_header_content = rows
        .get_message_recipient_header($message_row)
        .text()
        .replaceAll(/\s+/g, " ")
        .replace(/^\s/, "")
        .replace(/\s$/, "");
    return $("<p>").append($("<strong>").text(message_header_content));
}
/*
The techniques we use in this code date back to
2013 and may be obsolete today (and may not have
been even the best workaround back then).

https://github.com/zulip/zulip/commit/fc0b7c00f16316a554349f0ad58c6517ebdd7ac4

The idea is that we build a temp div, let jQuery process the
selection, then restore the selection on a zero-second timer back
to the original selection.

Do not be afraid to change this code if you understand
how modern browsers deal with copy/paste.  Just test
your changes carefully.
*/
function construct_copy_div($div: JQuery, start_id: number, end_id: number): void {
    if (message_lists.current === undefined) {
        return;
    }
    const copy_rows = rows.visible_range(start_id, end_id);

    const $start_row = copy_rows[0];
    assert($start_row !== undefined);
    const $start_recipient_row = rows.get_message_recipient_row($start_row);
    const start_recipient_row_id = rows.id_for_recipient_row($start_recipient_row);
    let should_include_start_recipient_header = false;
    let last_recipient_row_id = start_recipient_row_id;

    for (const $row of copy_rows) {
        const recipient_row_id = rows.id_for_recipient_row(rows.get_message_recipient_row($row));
        // if we found a message from another recipient,
        // it means that we have messages from several recipients,
        // so we have to add new recipient's bar to final copied message
        // and wouldn't forget to add start_recipient's bar at the beginning of final message
        if (recipient_row_id !== last_recipient_row_id) {
            construct_recipient_header($row).appendTo($div);
            last_recipient_row_id = recipient_row_id;
            should_include_start_recipient_header = true;
        }
        const message = message_lists.current.get(rows.id($row));
        assert(message !== undefined);
        const $content = $(message.content);
        $content.first().prepend(
            $("<span>")
                .text(message.sender_full_name + ": ")
                .contents(),
        );
        $div.append($content);
    }

    if (should_include_start_recipient_header) {
        construct_recipient_header($start_row).prependTo($div);
    }
}

// We want to grab the closest katex span up the tree
// in cases where we can resolve the selected katex expression
// from a math block into an inline expression.
// The returned element from this function
// is the one we call 'closest' on.
function get_nearest_html_element(node: Node | null): Element | null {
    if (node === null || node instanceof Element) {
        return node;
    }
    return node.parentElement;
}

// selection_element will be either the start_element or end_element
function expand_range_based_on_katex_parent(
    selection_element: Element,
    is_range_start: boolean,
    range: Range,
): void {
    // Here, we have three cases:
    // 1. This element lies within a math block expression i.e. within a  `.katex-display`
    // 2. This element lies within an inline math expression i.e. inside a `.katex` span
    // with no `.katex-display` parent for that `.katex`
    // 3. This element does not lie within a math expression, we directly return without expansion.
    // We cascade through these cases, expanding the range and prioritizing math blocks over expressions
    // in case we encounter them.

    const is_within_math_block = selection_element.closest(".katex-display") !== null;
    const is_within_math_expression = selection_element.closest(".katex") !== null;
    if (!is_within_math_block && !is_within_math_expression) {
        return;
    }
    if (is_within_math_block) {
        // One might think that this will break in case of empty katex-display(s)
        // being the start or end node which is/are created when we insert
        // some extra newlines within a math block.
        // However, is it not possible to select those empty katex-displays
        // as per my observation on Chrome and Firefox.
        if (is_range_start) {
            range.setStart(selection_element.closest(".katex-display")!, 0);
        } else {
            // The offset 1 selects the only child of `.katex-display`
            // which is `.katex`.
            range.setEnd(selection_element.closest(".katex-display")!, 1);
        }
    } else {
        if (is_range_start) {
            range.setStart(selection_element.closest(".katex")!, 0);
        } else {
            // The offset 2 selects the two children of `.katex`
            // namely `.katex-mathml` and `.katex-html`
            range.setEnd(selection_element.closest(".katex")!, 2);
        }
    }
}

/*
    Our paste behavior for KaTeX relies on processing the MathML
    annotations generated by KaTeX in `<annotation>` tags. This
    function is responsible for expanding selections of math copied
    out of Zulip to ensure the annotations are included in what is
    copied, so that it pastes nicely.

    We expand the selection range only in the following cases:

    1. Either the startContainer or endContainer or both are within an
       inline expression where the range covers one or more math
       expressions.
    2. Either the startContainer, endContainer, or both are within a
       math block where the range covers one or more math expressions.

    In principle, we only need to expand the start of the selection
    range for the cases where multiple expressions are selected
    because the end of the range always contains the annotation
    element in case it lies within the math block.

    But, we still expand the end of the range to select the complete
    expression, since our paste handler has no way to split the
    annotation, so we'll always be converting entire expressions.
*/
function improve_katex_selection_range(range: Range): void {
    const start_element = get_nearest_html_element(range.startContainer);
    const end_element = get_nearest_html_element(range.endContainer);
    if (!end_element || !start_element) {
        return;
    }

    // Only perform expansion if either the start or end element
    // is itself a `.katex` element or is contained within one.
    if (end_element.closest(".katex") === null && start_element.closest(".katex") === null) {
        return;
    }

    expand_range_based_on_katex_parent(start_element, true, range);
    expand_range_based_on_katex_parent(end_element, false, range);
}

export function copy_handler(ev: ClipboardEvent): boolean {
    // This is the main handler for copying message content via
    // `Ctrl+C` in Zulip (note that this is totally independent of the
    // "select region" copy behavior on Linux; that is handled
    // entirely by the browser, our HTML layout, and our use of the
    // no-select CSS classes).  We put considerable effort
    // into producing a nice result that pastes well into other tools.
    // Our user-facing specification is the following:
    //
    // * If the selection is contained within a single message, we
    //   want to just copy the portion that was selected, which we
    //   implement by letting the browser handle the Ctrl+C event.
    //
    // * Otherwise, we want to copy the bodies of all messages that
    //   were partially covered by the selection.

    const selection = window.getSelection();
    assert(selection !== null);

    const analysis = analyze_selection(selection);
    const start_id = analysis.start_id;
    const end_id = analysis.end_id;
    const skip_same_td_check = analysis.skip_same_td_check;

    if (start_id === undefined || end_id === undefined || start_id > end_id) {
        // In this case either the starting message or the ending
        // message is not defined, so this is definitely not a
        // multi-message selection and we can let the browser handle
        // the copy.
        //
        // Also, if our logic is not sound about the selection range
        // (start_id > end_id), we let the browser handle the copy.
        //
        // NOTE: `startContainer (~ start_id)` and `endContainer (~ end_id)`
        // of a `Range` are always from top to bottom in the DOM tree, independent
        // of the direction of the selection.
        // TODO: Add a reference for this statement, I just tested
        // it in console for various selection directions and found this
        // to be the case not sure why there is no online reference for it.
        return false;
    }

    if (!skip_same_td_check && start_id === end_id) {
        // Check whether the selection both starts and ends in the
        // same message and let the browser handle the copying.

        // Firefox uses multiple ranges when selecting multiple messages.
        // See https://drafts.csswg.org/css-ui-4/#valdef-user-select-none
        // Instead of relying on Selection API's anchorNode and focusNode,
        // we iterate over all ranges and expand them if needed.
        //
        // The reason is that anchorNode and focusNode only reflect the first range,
        // which becomes an issue in Firefox. When the selection spans multiple ranges,
        // for example, due to `user-select: none` elements in between the selection,
        // Firefox creates disjoint ranges but only sets anchor/focus for the first one.
        //
        // So to handle multi-range selections correctly (especially in Firefox),
        // we process all ranges individually.
        for (let i = 0; i < selection.rangeCount; i += 1) {
            improve_katex_selection_range(selection.getRangeAt(i));
        }

        return false;
    }

    // We've now decided to handle the copy event ourselves.
    //
    // We construct a temporary div for what we want the copy to pick up.
    // We construct the div only once, rather than for each range as we can
    // determine the starting and ending point with more confidence for the
    // whole selection. When constructing for each `Range`, there is a high
    // chance for overlaps between same message ids, avoiding which is much
    // more difficult since we can get a range (start_id and end_id) for
    // each selection `Range`.
    const $div = $("<div>");
    construct_copy_div($div, start_id, end_id);

    const html_content = $div.html().trim();
    const plain_text = $div.text().trim();
    ev.clipboardData?.setData("text/html", html_content);
    ev.clipboardData?.setData("text/plain", plain_text);

    // Tell the keyboard code that we did the copy ourselves, and thus
    // the browser should not handle the copy.
    return true;
}

export function analyze_selection(selection: Selection): {
    ranges: Range[];
    start_id: number | undefined;
    end_id: number | undefined;
    skip_same_td_check: boolean;
} {
    // Here we analyze our selection to determine if part of a message
    // or multiple messages are selected.
    //
    // Firefox and Chrome handle selection of multiple messages
    // differently. Firefox typically creates multiple ranges for the
    // selection, whereas Chrome typically creates just one.
    //
    // Our goal in the below loop is to compute and be prepared to
    // analyze the combined range of the selections, and copy their
    // full content.

    let i;
    let range;
    const ranges = [];
    let $startc;
    let $endc;
    let $initial_end_tr;
    let start_id;
    let end_id;
    let start_data;
    let end_data;
    // skip_same_td_check is true whenever we know for a fact that the
    // selection covers multiple messages (and thus we should no
    // longer consider letting the browser handle the copy event).
    let skip_same_td_check = false;

    for (i = 0; i < selection.rangeCount; i += 1) {
        range = selection.getRangeAt(i);
        ranges.push(range);

        $startc = $(range.startContainer);
        start_data = find_boundary_tr(
            $startc
                .parents(".selectable_row, .message_header")
                .not(".overlay-message-header")
                .first(),
            ($row) => $row.next(),
        );
        if (start_data === undefined) {
            // Skip any selection sections that don't intersect a message.
            continue;
        }
        // start_id is the Zulip message ID of the first message
        // touched by the selection.
        start_id ??= start_data[0];

        $endc = $(range.endContainer);
        $initial_end_tr = get_end_tr_from_endc($endc);
        end_data = find_boundary_tr($initial_end_tr, ($row) => $row.prev());

        if (end_data === undefined) {
            // Skip any selection sections that don't intersect a message.
            continue;
        }
        if (end_data[0] !== undefined) {
            end_id = end_data[0];
        }

        if (start_data[1] || end_data[1]) {
            // If the find_boundary_tr call for either the first or
            // the last message covered by the selection
            skip_same_td_check = true;
        }
    }

    return {
        ranges,
        start_id,
        end_id,
        skip_same_td_check,
    };
}

function get_end_tr_from_endc($endc: JQuery<Node>): JQuery {
    if ($endc.attr("id") === "bottom_whitespace" || $endc.attr("id") === "compose_close") {
        // If the selection ends in the bottom whitespace, we should
        // act as though the selection ends on the final message.
        // This handles the issue that Chrome seems to like selecting
        // the compose_close button when you go off the end of the
        // last message
        return rows.last_visible();
    }

    // Sometimes (especially when three click selecting in Chrome) the selection
    // can end in a hidden element in e.g. the next message, a date divider.
    // We can tell this is the case because the selection isn't inside a
    // `messagebox-content` div, which is where the message text itself is.
    // TODO: Ideally make it so that the selection cannot end there.
    // For now, we find the message row directly above wherever the
    // selection ended.
    if ($endc.closest(".messagebox-content").length === 0) {
        // If the selection ends within the message following the selected
        // messages, go back to use the actual last message.
        if ($endc.parents(".message_row").length > 0) {
            const $parent_msg = $endc.parents(".message_row").first();
            return $parent_msg.prev(".message_row");
        }
        // If it's not in a .message_row, it's probably in a .message_header and
        // we can use the last message from the previous recipient_row.
        // NOTE: It is possible that the selection started and ended inside the
        // message header and in that case we would be returning the message before
        // the selected header if it exists, but that is not the purpose of this
        // function to handle.
        if ($endc.parents(".message_header").length > 0) {
            const $overflow_recipient_row = $endc.parents(".recipient_row").first();
            return $overflow_recipient_row.prev(".recipient_row").children(".message_row").last();
        }
        // If somehow we get here, do the default return.
    }

    return $endc.parents(".selectable_row").first();
}

export function initialize(): void {
    document.addEventListener("copy", (ev) => {
        if (copy_handler(ev)) {
            ev.preventDefault();
        }
    });
}
