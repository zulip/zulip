import $ from "jquery";

import * as markdown from "./markdown";

// Save the compose content cursor position and restore when we
// shift-tab back in (see hotkey.js).
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

export function position_inside_code_block(content: string, position: number): boolean {
    let unique_insert = "UNIQUEINSERT:" + Math.random();
    while (content.includes(unique_insert)) {
        unique_insert = "UNIQUEINSERT:" + Math.random();
    }
    const unique_insert_content =
        content.slice(0, position) + unique_insert + content.slice(position);
    const rendered_content = markdown.parse_non_message(unique_insert_content);
    const rendered_html = new DOMParser().parseFromString(rendered_content, "text/html");
    const code_blocks = rendered_html.querySelectorAll("pre > code");
    return [...code_blocks].some((code_block) => code_block?.textContent?.includes(unique_insert));
}

export function initialize(): void {
    set_compose_textarea_handlers();
}
