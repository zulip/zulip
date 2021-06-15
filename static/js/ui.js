import $ from "jquery";
import SimpleBar from "simplebar";

import {$t} from "./i18n";
import * as message_list from "./message_list";
import * as message_lists from "./message_lists";

// What, if anything, obscures the home tab?

export function replace_emoji_with_text(element) {
    element.find(".emoji").replaceWith(function () {
        if ($(this).is("img")) {
            return $(this).attr("alt");
        }
        return $(this).text();
    });
}

export function get_content_element(element_selector) {
    const element = element_selector.expectOne()[0];
    const sb = SimpleBar.instances.get(element);
    if (sb) {
        return $(sb.getContentElement());
    }
    return element_selector;
}

export function get_scroll_element(element_selector) {
    const element = element_selector.expectOne()[0];
    const sb = SimpleBar.instances.get(element);
    if (sb) {
        return $(sb.getScrollElement());
    } else if ("simplebar" in element.dataset) {
        // The SimpleBar mutation observer hasn’t processed this element yet.
        // Create the SimpleBar early in case we need to add event listeners.
        return $(new SimpleBar(element).getScrollElement());
    }
    return element_selector;
}

export function reset_scrollbar(element_selector) {
    const element = element_selector.expectOne()[0];
    const sb = SimpleBar.instances.get(element);
    if (sb) {
        sb.getScrollElement().scrollTop = 0;
    } else {
        element.scrollTop = 0;
    }
}

function update_message_in_all_views(message_id, callback) {
    for (const list of [message_lists.home, message_list.narrowed]) {
        if (list === undefined) {
            continue;
        }
        const row = list.get_row(message_id);
        if (row === undefined) {
            // The row may not exist, e.g. if you do an action on a message in
            // a narrowed view
            continue;
        }
        callback(row);
    }
}

export function update_starred_view(message_id, new_value) {
    const starred = new_value;

    // Avoid a full re-render, but update the star in each message
    // table in which it is visible.
    update_message_in_all_views(message_id, (row) => {
        const elt = row.find(".star");
        const star_container = row.find(".star_container");
        if (starred) {
            elt.addClass("fa-star").removeClass("fa-star-o");
            star_container.removeClass("empty-star");
        } else {
            elt.removeClass("fa-star").addClass("fa-star-o");
            star_container.addClass("empty-star");
        }
        const title_state = starred ? $t({defaultMessage: "Unstar"}) : $t({defaultMessage: "Star"});
        star_container.attr(
            "data-tippy-content",
            $t(
                {defaultMessage: "{starred_status} this message (Ctrl + s)"},
                {starred_status: title_state},
            ),
        );
    });
}

export function show_message_failed(message_id, failed_msg) {
    // Failed to send message, so display inline retry/cancel
    update_message_in_all_views(message_id, (row) => {
        const failed_div = row.find(".message_failed");
        failed_div.toggleClass("notvisible", false);
        failed_div.find(".failed_text").attr("title", failed_msg);
    });
}

export function show_failed_message_success(message_id) {
    // Previously failed message succeeded
    update_message_in_all_views(message_id, (row) => {
        row.find(".message_failed").toggleClass("notvisible", true);
    });
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
