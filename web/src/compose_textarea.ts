import $ from "jquery";

import * as markdown from "./markdown.ts";

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

export function get_code_block_ranges(content: string): CodeBlockRange[] {
    let marker_prefix = "ZCBM" + Math.random().toString(36).slice(2);
    while (content.includes(marker_prefix)) {
        marker_prefix = "ZCBM" + Math.random().toString(36).slice(2);
    }
    const newline_positions: number[] = [];
    for (let i = content.indexOf("\n"); i !== -1; i = content.indexOf("\n", i + 1)) {
        newline_positions.push(i);
    }
    if (newline_positions.length === 0) {
        return [];
    }

    let annotated = "";
    let cursor = 0;
    for (const [idx, pos] of newline_positions.entries()) {
        annotated += content.slice(cursor, pos + 1) + `${marker_prefix}${idx} `;
        cursor = pos + 1;
    }
    annotated += content.slice(cursor);

    const rendered = markdown.parse_non_message(annotated);
    const doc = new DOMParser().parseFromString(rendered, "text/html");
    const inside_indices = new Set<number>();
    const re = new RegExp(`${marker_prefix}(\\d+)`, "g");
    for (const block of doc.querySelectorAll("pre > code, code")) {
        const text = block.textContent ?? "";
        for (const match of text.matchAll(re)) {
            inside_indices.add(Number(match[1]));
        }
    }

    const ranges: [number, number][] = [];
    let start_pos: number | undefined;
    for (const [idx, pos] of newline_positions.entries()) {
        if (inside_indices.has(idx)) {
            start_pos ??= pos;
        } else if (start_pos !== undefined) {
            ranges.push([start_pos, newline_positions[idx - 1]! + 1]);
            start_pos = undefined;
        }
    }
    if (start_pos !== undefined) {
        ranges.push([start_pos, content.length]);
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
