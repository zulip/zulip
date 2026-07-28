import $ from "jquery";

import {fence_re} from "./fenced_code.ts";

// Save the compose content cursor position and restore when we
// shift-tab back in (see hotkey.ts).
let saved_compose_cursor = 0;

function set_compose_textarea_handlers(): void {
    $("textarea#compose-textarea").on("blur", function () {
        saved_compose_cursor = $(this).caret();
    });

    // on the end of the modified-message fade in, remove the fade-in-message class.
    const animationEnd = "webkitAnimationEnd oanimationend msAnimationEnd animationend";
    $("body").on(animationEnd, ".fade-in-message", function () {
        $(this).removeClass("fade-in-message");
    });
}

export function restore_compose_cursor(): void {
    $("textarea#compose-textarea").trigger("focus").caret(saved_compose_cursor);
}

export type CodeBlockRange = readonly [number, number];

// Returns the [start, end) character ranges of the content that lie inside a
// code block, so callers can avoid splitting a message inside one. Fenced
// blocks reuse fenced_code.ts's fence_re and its exact-close rule; 4-space/tab
// indented blocks follow CommonMark, so they start only after a blank line and
// blank lines alone don't close them.
export function get_code_block_ranges(content: string): CodeBlockRange[] {
    const ranges: [number, number][] = [];
    let offset = 0;
    let fence: string | undefined;
    let fence_start = 0;
    let indent_start: number | undefined;
    let indent_end = 0;
    let prev_line_blank = true;

    for (const line of content.split("\n")) {
        const line_start = offset;
        const line_end = offset + line.length;
        offset = line_end + 1;

        if (fence !== undefined) {
            if (line === fence) {
                ranges.push([fence_start, line_end]);
                fence = undefined;
            }
            prev_line_blank = false;
            continue;
        }

        const fence_match = fence_re.exec(line);
        if (fence_match) {
            if (indent_start !== undefined) {
                ranges.push([indent_start, indent_end]);
                indent_start = undefined;
            }
            fence = fence_match[1];
            fence_start = line_start;
            prev_line_blank = false;
            continue;
        }

        if (line.trim() === "") {
            prev_line_blank = true;
            continue;
        }

        if (
            (line.startsWith("    ") || line.startsWith("\t")) &&
            (indent_start !== undefined || prev_line_blank)
        ) {
            indent_start ??= line_start;
            indent_end = line_end;
        } else if (indent_start !== undefined) {
            ranges.push([indent_start, indent_end]);
            indent_start = undefined;
        }
        prev_line_blank = false;
    }

    if (fence !== undefined) {
        ranges.push([fence_start, content.length]);
    } else if (indent_start !== undefined) {
        ranges.push([indent_start, indent_end]);
    }
    return ranges;
}

export function position_inside_code_block(content: string, position: number): boolean {
    return get_code_block_ranges(content).some(
        ([start, end]) => position >= start && position < end,
    );
}

export function initialize(): void {
    set_compose_textarea_handlers();
}
