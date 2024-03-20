import isUrl from "is-url";
import $ from "jquery";
import _ from "lodash";
import TurndownService from "turndown";

import * as compose_ui from "./compose_ui";
import * as message_lists from "./message_lists";
import * as rows from "./rows";

function find_boundary_tr($initial_tr, iterate_row) {
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

function construct_recipient_header($message_row) {
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
function construct_copy_div($div, start_id, end_id) {
    if (message_lists.current === undefined) {
        return;
    }
    const copy_rows = rows.visible_range(start_id, end_id);

    const $start_row = copy_rows[0];
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

function select_div($div, selection) {
    $div.css({
        position: "absolute",
        left: "-99999px",
        // Color and background is made according to "light theme"
        // exclusively here because when copying the content
        // into, say, Gmail compose box, the styles come along.
        // This is done to avoid copying the content with dark
        // background when using the app in dark theme.
        // We can avoid other custom styles since they are wrapped
        // inside another parent such as `.message_content`.
        color: "#333",
        background: "#FFF",
    }).attr("id", "copytempdiv");
    $("body").append($div);
    selection.selectAllChildren($div[0]);
}

function remove_div(_div, ranges, selection) {
    window.setTimeout(() => {
        selection = window.getSelection();
        selection.removeAllRanges();

        for (const range of ranges) {
            selection.addRange(range);
        }

        $("#copytempdiv").remove();
    }, 0);
}

export function copy_handler() {
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
    const analysis = analyze_selection(selection);
    const ranges = analysis.ranges;
    const start_id = analysis.start_id;
    const end_id = analysis.end_id;
    const skip_same_td_check = analysis.skip_same_td_check;
    const $div = $("<div>");

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
    construct_copy_div($div, start_id, end_id);

    // Select div so that the browser will copy it
    // instead of copying the original selection
    select_div($div, selection);
    document.execCommand("copy");
    remove_div($div, ranges, selection);
}

export function analyze_selection(selection) {
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
            $startc.parents(".selectable_row, .message_header").first(),
            ($row) => $row.next(),
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

function get_end_tr_from_endc($endc) {
    if ($endc.attr("id") === "bottom_whitespace" || $endc.attr("id") === "compose_close") {
        // If the selection ends in the bottom whitespace, we should
        // act as though the selection ends on the final message.
        // This handles the issue that Chrome seems to like selecting
        // the compose_close button when you go off the end of the
        // last message
        return $(".message_row").last();
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
        if ($endc.parents(".message_header").length > 0) {
            const $overflow_recipient_row = $endc.parents(".recipient_row").first();
            return $overflow_recipient_row.prev(".recipient_row").last(".message_row");
        }
        // If somehow we get here, do the default return.
    }

    return $endc.parents(".selectable_row").first();
}

function deduplicate_newlines(attribute) {
    // We replace any occurrences of one or more consecutive newlines followed by
    // zero or more whitespace characters with a single newline character.
    return attribute ? attribute.replaceAll(/(\n+\s*)+/g, "\n") : "";
}

function image_to_zulip_markdown(_content, node) {
    if (node.nodeName === "IMG" && node.classList.contains("emoji") && node.hasAttribute("alt")) {
        // For Zulip's custom emoji
        return node.getAttribute("alt");
    }
    const src = node.getAttribute("src") || node.getAttribute("href") || "";
    const title = deduplicate_newlines(node.getAttribute("title")) || "";
    // Using Zulip's link like syntax for images
    return src ? "[" + title + "](" + src + ")" : node.getAttribute("alt") || "";
}

function within_single_element(html_fragment) {
    return (
        html_fragment.childNodes.length === 1 &&
        html_fragment.firstElementChild &&
        html_fragment.firstElementChild.innerHTML
    );
}

export function is_white_space_pre(paste_html) {
    const html_fragment = new DOMParser()
        .parseFromString(paste_html, "text/html")
        .querySelector("body");
    return (
        within_single_element(html_fragment) &&
        html_fragment.firstElementChild.style.whiteSpace === "pre"
    );
}

export function paste_handler_converter(paste_html) {
    const copied_html_fragment = new DOMParser()
        .parseFromString(paste_html, "text/html")
        .querySelector("body");
    const copied_within_single_element = within_single_element(copied_html_fragment);
    const outer_elements_to_retain = ["PRE", "UL", "OL", "A", "CODE"];
    // If the entire selection copied is within a single HTML element (like an
    // `h1`), we don't want to retain its styling, except when it is needed to
    // identify the intended structure of the copied content.
    if (
        copied_within_single_element &&
        !outer_elements_to_retain.includes(copied_html_fragment.firstElementChild.nodeName)
    ) {
        paste_html = copied_html_fragment.firstChild.innerHTML;
    }

    // turning off escaping (for now) to remove extra `/`
    TurndownService.prototype.escape = (string) => string;

    const turndownService = new TurndownService({
        emDelimiter: "*",
        codeBlockStyle: "fenced",
        headingStyle: "atx",
        br: "",
    });
    turndownService.addRule("style", {
        filter: "style",
        replacement() {
            return "";
        },
    });
    turndownService.addRule("strikethrough", {
        filter: ["del", "s", "strike"],
        replacement(content) {
            return "~~" + content + "~~";
        },
    });
    turndownService.addRule("links", {
        filter: ["a"],
        replacement(content, node) {
            if (node.href === content) {
                // Checks for raw links without custom text.
                return content;
            }
            if (node.childNodes.length === 1 && node.firstChild.nodeName === "IMG") {
                // ignore link's url if it only has an image
                return content;
            }
            return "[" + content + "](" + node.href + ")";
        },
    });
    turndownService.addRule("listItem", {
        // We override the original upstream implementation of this rule
        // to have a custom indent of 2 spaces for list items, instead of
        // the default 4 spaces. Everything else is the same as upstream.
        filter: "li",
        replacement(content, node) {
            content = content
                .replace(/^\n+/, "") // remove leading newlines
                .replace(/\n+$/, "\n") // replace trailing newlines with just a single one
                .replaceAll(/\n/gm, "\n  "); // custom 2 space indent
            let prefix = "* ";
            const parent = node.parentNode;
            if (parent.nodeName === "OL") {
                const start = parent.getAttribute("start");
                const index = Array.prototype.indexOf.call(parent.children, node);
                prefix = (start ? Number(start) + index : index + 1) + ". ";
            }
            return prefix + content + (node.nextSibling && !/\n$/.test(content) ? "\n" : "");
        },
    });
    turndownService.addRule("zulipImagePreview", {
        filter(node) {
            // select image previews in Zulip messages
            return (
                node.classList.contains("message_inline_image") && node.firstChild.nodeName === "A"
            );
        },

        replacement(content, node) {
            // We parse the copied html to then check if the generating link (which, if
            // present, always comes before the preview in the copied html) is also there.

            // If the 1st element with the same image link in the copied html
            // does not have the `message_inline_image` class, it means it is the generating
            // link, and not the preview, meaning the generating link is copied as well.
            const copied_html = new DOMParser().parseFromString(paste_html, "text/html");
            if (
                !copied_html
                    .querySelector("a[href='" + node.firstChild.getAttribute("href") + "']")
                    ?.parentNode?.classList.contains("message_inline_image")
            ) {
                // We skip previews which have their generating link copied too, to avoid
                // double pasting the same link.
                return "";
            }
            return image_to_zulip_markdown(content, node.firstChild);
        },
    });
    turndownService.addRule("images", {
        filter: "img",

        replacement: image_to_zulip_markdown,
    });
    turndownService.addRule("math", {
        // We don't have a way to get the original LaTeX code from the rendered
        // `math` so we drop it to avoid pasting gibberish.
        // In the future, we could have a data-original-latex feature in Zulip HTML
        // if we wanted to paste the original LaTeX for Zulip messages.
        filter: "math",

        replacement() {
            return "";
        },
    });

    // We override the original upstream implementation of this rule to make
    // several tweaks:
    // - We turn any single line code blocks into inline markdown code.
    // - We generalise the filter condition to allow a `pre` element with a
    // `code` element as its only non-empty child, which applies to Zulip code
    // blocks too.
    // - For Zulip code blocks, we extract the language of the code block (if
    // any) correctly.
    // Everything else works the same.
    turndownService.addRule("fencedCodeBlock", {
        filter(node, options) {
            return (
                options.codeBlockStyle === "fenced" &&
                node.nodeName === "PRE" &&
                [...node.childNodes].filter((child) => child.textContent.trim() !== "").length ===
                    1 &&
                [...node.childNodes].find((child) => child.textContent.trim() !== "").nodeName ===
                    "CODE"
            );
        },

        replacement(_content, node, options) {
            const codeElement = [...node.childNodes].find((child) => child.nodeName === "CODE");
            const code = codeElement.textContent;

            // We convert single line code inside a code block to inline markdown code,
            // and the code for this is taken from upstream's `code` rule.
            if (!code.includes("\n")) {
                if (!code) {
                    return "";
                }
                const extraSpace = /^`|^ .*?[^ ].* $|`$/.test(code) ? " " : "";

                // Pick the shortest sequence of backticks that is not found in the code
                // to be the delimiter.
                let delimiter = "`";
                const matches = code.match(/`+/gm) || [];
                while (matches.includes(delimiter)) {
                    delimiter = delimiter + "`";
                }

                return delimiter + extraSpace + code + extraSpace + delimiter;
            }

            const className = codeElement.getAttribute("class") || "";
            const language = node.parentElement?.classList.contains("zulip-code-block")
                ? node.closest(".codehilite")?.dataset?.codeLanguage || ""
                : (className.match(/language-(\S+)/) || [null, ""])[1];

            const fenceChar = options.fence.charAt(0);
            let fenceSize = 3;
            const fenceInCodeRegex = new RegExp("^" + fenceChar + "{3,}", "gm");

            let match;
            while ((match = fenceInCodeRegex.exec(code))) {
                if (match[0].length >= fenceSize) {
                    fenceSize = match[0].length + 1;
                }
            }

            const fence = fenceChar.repeat(fenceSize);

            return (
                "\n\n" + fence + language + "\n" + code.replace(/\n$/, "") + "\n" + fence + "\n\n"
            );
        },
    });

    let markdown_text = turndownService.turndown(paste_html);

    // Checks for escaped ordered list syntax.
    markdown_text = markdown_text.replaceAll(/^(\W* {0,3})(\d+)\\\. /gm, "$1$2. ");

    // Removes newlines before the start of a list and between list elements.
    markdown_text = markdown_text.replaceAll(/\n+([*+-])/g, "\n$1");
    return markdown_text;
}

function is_safe_url_paste_target($textarea) {
    const range = $textarea.range();

    if (!range.text) {
        // No range is selected
        return false;
    }

    if (isUrl(range.text.trim())) {
        // Don't engage our URL paste logic over existing URLs
        return false;
    }

    if (range.start <= 2) {
        // The range opens too close to the start of the textarea
        // to have to worry about Markdown link syntax
        return true;
    }

    // Look at the two characters before the start of the original
    // range in search of the tell-tale `](` from existing Markdown
    // link syntax
    const possible_markdown_link_markers = $textarea[0].value.slice(range.start - 2, range.start);

    if (possible_markdown_link_markers === "](") {
        return false;
    }

    return true;
}

export function maybe_transform_html(html, text) {
    if (is_white_space_pre(html)) {
        // Copied content styled with `white-space: pre` is pasted as is
        // but formatted as code. We need this for content copied from
        // VS Code like sources.
        return "<pre><code>" + _.escape(text) + "</code></pre>";
    }
    return html;
}

export function paste_handler(event) {
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
        const $textarea = $(event.currentTarget);
        const paste_text = clipboardData.getData("text");
        let paste_html = clipboardData.getData("text/html");
        // Trim the paste_text to accommodate sloppy copying
        const trimmed_paste_text = paste_text.trim();

        // Only intervene to generate formatted links when dealing
        // with a URL and a URL-safe range selection.
        if (isUrl(trimmed_paste_text) && is_safe_url_paste_target($textarea)) {
            event.preventDefault();
            event.stopPropagation();
            const url = trimmed_paste_text;
            compose_ui.format_text($textarea, "linked", url);
            return;
        }

        // We do not paste formatted markdoown when inside a code block.
        // Unlike Chrome, Firefox doesn't automatically paste plainly on using Ctrl+Shift+V,
        // hence we need to handle it ourselves, by checking if shift key is pressed, and only
        // if not, we proceed with the default formatted paste.
        if (
            !compose_ui.cursor_inside_code_block($textarea) &&
            paste_html &&
            !compose_ui.shift_pressed
        ) {
            event.preventDefault();
            event.stopPropagation();
            paste_html = maybe_transform_html(paste_html, paste_text);
            const text = paste_handler_converter(paste_html);
            compose_ui.insert_and_scroll_into_view(text, $textarea);
        }
    }
}

export function initialize() {
    $("textarea#compose-textarea").on("paste", paste_handler);
    $("body").on("paste", ".message_edit_content", paste_handler);
}
