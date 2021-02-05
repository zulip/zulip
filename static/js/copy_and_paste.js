"use strict";

const TurndownService = require("turndown/lib/turndown.cjs");

function find_boundary_tr(initial_tr, iterate_row) {
    let j;
    let skip_same_td_check = false;
    let tr = initial_tr;

    // If the selection boundary is somewhere that does not have a
    // parent tr, we should let the browser handle the copy-paste
    // entirely on its own
    if (tr.length === 0) {
        return undefined;
    }

    // If the selection boundary is on a table row that does not have an
    // associated message id (because the user clicked between messages),
    // then scan downwards until we hit a table row with a message id.
    // To ensure we can't enter an infinite loop, bail out (and let the
    // browser handle the copy-paste on its own) if we don't hit what we
    // are looking for within 10 rows.
    for (j = 0; !tr.is(".message_row") && j < 10; j += 1) {
        tr = iterate_row(tr);
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
    return [rows.id(tr), skip_same_td_check];
}

function construct_recipient_header(message_row) {
    const message_header_content = rows
        .get_message_recipient_header(message_row)
        .text()
        .replace(/\s+/g, " ")
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
function construct_copy_div(div, start_id, end_id) {
    const copy_rows = rows.visible_range(start_id, end_id);

    const start_row = copy_rows[0];
    const start_recipient_row = rows.get_message_recipient_row(start_row);
    const start_recipient_row_id = rows.id_for_recipient_row(start_recipient_row);
    let should_include_start_recipient_header = false;
    let last_recipient_row_id = start_recipient_row_id;

    for (const row of copy_rows) {
        const recipient_row_id = rows.id_for_recipient_row(rows.get_message_recipient_row(row));
        // if we found a message from another recipient,
        // it means that we have messages from several recipients,
        // so we have to add new recipient's bar to final copied message
        // and wouldn't forget to add start_recipient's bar at the beginning of final message
        if (recipient_row_id !== last_recipient_row_id) {
            div.append(construct_recipient_header(row));
            last_recipient_row_id = recipient_row_id;
            should_include_start_recipient_header = true;
        }
        const message = current_msg_list.get(rows.id(row));
        const message_firstp = $(message.content).slice(0, 1);
        message_firstp.prepend(message.sender_full_name + ": ");
        div.append(message_firstp);
        div.append($(message.content).slice(1));
    }

    if (should_include_start_recipient_header) {
        div.prepend(construct_recipient_header(start_row));
    }
}

function select_div(div, selection) {
    div.css({
        position: "absolute",
        left: "-99999px",
        // Color and background is made according to "day mode"
        // exclusively here because when copying the content
        // into, say, Gmail compose box, the styles come along.
        // This is done to avoid copying the content with dark
        // background when using the app in night mode.
        // We can avoid other custom styles since they are wrapped
        // inside another parent such as `.message_content`.
        color: "#333",
        background: "#FFF",
    }).attr("id", "copytempdiv");
    $("body").append(div);
    selection.selectAllChildren(div[0]);
}

function remove_div(div, ranges, selection) {
    window.setTimeout(() => {
        selection = window.getSelection();
        selection.removeAllRanges();

        for (const range of ranges) {
            selection.addRange(range);
        }

        $("#copytempdiv").remove();
    }, 0);
}

exports.copy_handler = function () {
    // This is the main handler for copying message content via
    // `Ctrl+C` in Zulip (note that this is totally independent of the
    // "select region" copy behavior on Linux; that is handled
    // entirely by the browser, our HTML layout, and our use of the
    // no-select/auto-select CSS classes).  We put considerable effort
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
    const analysis = exports.analyze_selection(selection);
    const ranges = analysis.ranges;
    const start_id = analysis.start_id;
    const end_id = analysis.end_id;
    const skip_same_td_check = analysis.skip_same_td_check;
    const div = $("<div>");

    if (start_id === undefined || end_id === undefined) {
        // In this case either the starting message or the ending
        // message is not defined, so this is definitely not a
        // multi-message selection and we can let the browser handle
        // the copy.
        document.execCommand("copy");
        return;
    }

    if (!skip_same_td_check && start_id === end_id) {
        // Check whether the selection both starts and ends in the
        // same message.  If so, Let the browser handle this.
        document.execCommand("copy");
        return;
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
    construct_copy_div(div, start_id, end_id);

    // Select div so that the browser will copy it
    // instead of copying the original selection
    select_div(div, selection);
    document.execCommand("copy");
    remove_div(div, ranges, selection);
};

exports.analyze_selection = function (selection) {
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
    let startc;
    let endc;
    let initial_end_tr;
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

        startc = $(range.startContainer);
        start_data = find_boundary_tr(
            $(startc.parents(".selectable_row, .message_header")[0]),
            (row) => row.next(),
        );
        if (start_data === undefined) {
            // Skip any selection sections that don't intersect a message.
            continue;
        }
        if (start_id === undefined) {
            // start_id is the Zulip message ID of the first message
            // touched by the selection.
            start_id = start_data[0];
        }

        endc = $(range.endContainer);
        // If the selection ends in the bottom whitespace, we should
        // act as though the selection ends on the final message.
        // This handles the issue that Chrome seems to like selecting
        // the compose_close button when you go off the end of the
        // last message
        if (endc.attr("id") === "bottom_whitespace" || endc.attr("id") === "compose_close") {
            initial_end_tr = $(".message_row").last();
            // The selection goes off the end of the message feed, so
            // this is a multi-message selection.
            skip_same_td_check = true;
        } else {
            initial_end_tr = $(endc.parents(".selectable_row")[0]);
        }
        end_data = find_boundary_tr(initial_end_tr, (row) => row.prev());

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
};

exports.paste_handler_converter = function (paste_html) {
    const turndownService = new TurndownService();
    turndownService.addRule("headings", {
        filter: ["h1", "h2", "h3", "h4", "h5", "h6"],
        replacement(content) {
            return content;
        },
    });
    turndownService.addRule("emphasis", {
        filter: ["em", "i"],
        replacement(content) {
            return "*" + content + "*";
        },
    });
    // Checks for raw links without custom text or title.
    turndownService.addRule("links", {
        filter(node) {
            return (
                node.nodeName === "A" && node.href === node.innerHTML && node.href === node.title
            );
        },
        replacement(content) {
            return content;
        },
    });

    let markdown_text = turndownService.turndown(paste_html);

    // Checks for escaped ordered list syntax.
    markdown_text = markdown_text.replace(/^(\W* {0,3})(\d+)\\\. /gm, "$1$2. ");

    // Removes newlines before the start of a list and between list elements.
    markdown_text = markdown_text.replace(/\n+([*+-])/g, "\n$1");
    return markdown_text;
};

exports.paste_handler = function (event) {
    const clipboardData = event.originalEvent.clipboardData;
    if (!clipboardData) {
        // On IE11, ClipboardData isn't defined.  One can instead
        // access it with `window.clipboardData`, but even that
        // doesn't support text/html, so this code path couldn't do
        // anything special anyway.  So we instead just let the
        // default paste handler run on IE11.
        return;
    }

    if (clipboardData.getData) {
        const paste_html = clipboardData.getData("text/html");
        if (paste_html && page_params.development_environment) {
            const text = exports.paste_handler_converter(paste_html);
            const mdImageRegex = /^!\[.*]\(.*\)$/;
            if (mdImageRegex.test(text)) {
                // This block catches cases where we are pasting an
                // image into Zulip, which is handled by upload.js.
                return;
            }
            event.preventDefault();
            event.stopPropagation();
            compose_ui.insert_syntax_and_focus(text);
        }
    }
};

exports.initialize = function () {
    $("#compose-textarea").on("paste", exports.paste_handler);
    $("body").on("paste", "#message_edit_form", exports.paste_handler);
};

window.copy_and_paste = exports;
