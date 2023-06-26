import $ from "jquery";

// Save the compose content cursor position and restore when we
// shift-tab back in (see hotkey.js).
let saved_compose_cursor = 0;

function set_compose_textarea_handlers(): void {
    $("#compose-textarea").on("blur", function () {
        saved_compose_cursor = $(this).caret();
    });

    // on the end of the modified-message fade in, remove the fade-in-message class.
    const animationEnd = "webkitAnimationEnd oanimationend msAnimationEnd animationend";
    $("body").on(animationEnd, ".fade-in-message", function () {
        $(this).removeClass("fade-in-message");
    });
}

export function restore_compose_cursor(): void {
    $("#compose-textarea").trigger("focus").caret(saved_compose_cursor);
}

export function initialize(): void {
    set_compose_textarea_handlers();
}
