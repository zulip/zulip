import $ from "jquery";
import SimpleBar from "simplebar";

// What, if anything, obscures the home tab?

export function replace_emoji_with_text($element) {
    $element.find(".emoji").replaceWith(function () {
        if ($(this).is("img")) {
            return $(this).attr("alt");
        }
        return $(this).text();
    });
}

export function get_content_element($element) {
    const element = $element.expectOne()[0];
    const sb = SimpleBar.instances.get(element);
    if (sb) {
        return $(sb.getContentElement());
    }
    return $element;
}

export function get_scroll_element($element) {
    const element = $element.expectOne()[0];
    const sb = SimpleBar.instances.get(element);
    if (sb) {
        return $(sb.getScrollElement());
    } else if ("simplebar" in element.dataset) {
        // The SimpleBar mutation observer hasn’t processed this element yet.
        // Create the SimpleBar early in case we need to add event listeners.
        return $(new SimpleBar(element).getScrollElement());
    }
    return $element;
}

export function reset_scrollbar($element) {
    const element = $element.expectOne()[0];
    const sb = SimpleBar.instances.get(element);
    if (sb) {
        sb.getScrollElement().scrollTop = 0;
    } else {
        element.scrollTop = 0;
    }
}

// Save the compose content cursor position and restore when we
// shift-tab back in (see hotkey.js).
let saved_compose_cursor = 0;

export function set_compose_textarea_handlers() {
    $("#compose-textarea").on("blur", function () {
        saved_compose_cursor = $(this).caret();
    });

    // on the end of the modified-message fade in, remove the fade-in-message class.
    const animationEnd = "webkitAnimationEnd oanimationend msAnimationEnd animationend";
    $("body").on(animationEnd, ".fade-in-message", function () {
        $(this).removeClass("fade-in-message");
    });
}

export function restore_compose_cursor() {
    $("#compose-textarea").trigger("focus").caret(saved_compose_cursor);
}

export function initialize() {
    set_compose_textarea_handlers();
}
