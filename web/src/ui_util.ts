import $ from "jquery";

import * as blueslip from "./blueslip";
import * as hash_parser from "./hash_parser";
import * as keydown_util from "./keydown_util";

// Add functions to this that have no non-trivial
// dependencies other than jQuery.

// https://stackoverflow.com/questions/4233265/contenteditable-set-caret-at-the-end-of-the-text-cross-browser
export function place_caret_at_end(el: HTMLElement): void {
    el.focus();
    if (el instanceof HTMLInputElement) {
        el.setSelectionRange(el.value.length, el.value.length);
    } else {
        const range = document.createRange();
        range.selectNodeContents(el);
        range.collapse(false);
        const sel = window.getSelection();
        sel?.removeAllRanges();
        sel?.addRange(range);
    }
}

export function replace_emoji_name_with_unicode_hex($element: JQuery): void {
    // Find the emoji class in the passed JQuery element
    $element.find("span.emoji").each(function () {
        const emoji_class: string | undefined = $(this).attr("class");
        // If no emoji class is found do nothing to the element
        if (emoji_class === undefined) {
            return;
        }

        // Emojis have a class with the emoji code next to them i.e. emoji-1f951
        // The code 1f951 represents an avocado 🥑
        const regex = /emoji-(\w+)/;
        const match = regex.exec(emoji_class);
        const emoji_code = match?.[1] ?? "";

        // Convert the emoji code to its hex code representation
        // Then use String.fromCodePoint to get the standard unicode representation of the hex code
        try {
            const hex_code = Number.parseInt(emoji_code, 16);
            if (Number.isNaN(hex_code)) {
                throw new Error(`Invalid emoji code: ${emoji_code}`);
            }
            const emoji_char = String.fromCodePoint(hex_code);
            $(this).text(emoji_char);
        } catch (error: unknown) {
            if (error instanceof Error) {
                console.error(`Failed to convert emoji code to character: ${error.message}`);
            } else {
                console.error('Failed to convert emoji code to character: Unknown error');
            }
            // Fallback behavior: leave the original content unchanged
            return;
        }
    });
}

export function change_katex_to_raw_latex($element: JQuery): void {
    // Find all the span elements with the class "katex"
    $element.find("span.katex").each(function () {
        // Find the text within the <annotation> tag
        const latex_text = $(this).find('annotation[encoding="application/x-tex"]').text();

        // Create a new <span> element with the raw latex wrapped in $$
        const $latex_span = $("<span>").text("$$" + latex_text + "$$");

        // Replace the current .katex element with the new <span> containing the text
        $(this).replaceWith($latex_span);
    });
}

export function is_user_said_paragraph($element: JQuery): boolean {
    // Irrespective of language, the user said paragraph has these exact elements:
    // 1. A user mention
    // 2. A same server message link ("said")
    // 3. A colon (:)
    const $user_mention = $element.find(".user-mention");
    if ($user_mention.length !== 1) {
        return false;
    }
    const $message_link = $element.find("a[href]").filter((_index, element) => {
        const href = $(element).attr("href")!;
        return href ? hash_parser.is_same_server_message_link(href) : false;
    });
    if ($message_link.length !== 1) {
        return false;
    }
    const remaining_text = $element
        .text()
        .replace($user_mention.text(), "")
        .replace($message_link.text(), "");
    return remaining_text.trim() === ":";
}

export function get_collapsible_status_array($elements: JQuery): boolean[] {
    return [...$elements].map(
        (element) => $(element).is("blockquote") || is_user_said_paragraph($(element)),
    );
}

export function potentially_collapse_quotes($element: JQuery): boolean {
    const $children = $element.children();
    const collapsible_status = get_collapsible_status_array($children);

    if (collapsible_status.every(Boolean) || collapsible_status.every((x) => !x)) {
        // If every element is collapsible or none of them is collapsible,
        // we don't collapse any element.
        return false;
    }

    for (const [index, element] of [...$children].entries()) {
        if (collapsible_status[index]) {
            if (index > 0 && collapsible_status[index - 1]) {
                // If the previous element was also collapsible, remove its text
                // to have a single collapsed block instead of multiple in a row.
                $(element).text("");
            } else {
                // Else, collapse this element.
                $(element).text("[…]");
            }
        }
    }
    return true;
}

export function blur_active_element(): void {
    // this blurs anything that may perhaps be actively focused on.
    if (document.activeElement instanceof HTMLElement) {
        document.activeElement.blur();
    }
}

export function convert_enter_to_click(e: JQuery.KeyDownEvent): void {
    if (keydown_util.is_enter_event(e)) {
        e.preventDefault();
        e.stopPropagation();
        $(e.currentTarget).trigger("click");
    }
}

export function update_unread_count_in_dom($unread_count_elem: JQuery, count: number): void {
    // This function is used to update unread count in top left corner
    // elements.
    const $unread_count_span = $unread_count_elem.find(".unread_count");

    if (count === 0) {
        $unread_count_span.addClass("hide");
        $unread_count_span.text("");
        return;
    }

    $unread_count_span.removeClass("hide");
    $unread_count_span.text(count);
}

export function update_unread_mention_info_in_dom(
    $unread_mention_info_elem: JQuery,
    stream_has_any_unread_mention_messages: boolean,
): void {
    const $unread_mention_info_span = $unread_mention_info_elem.find(".unread_mention_info");
    if (!stream_has_any_unread_mention_messages) {
        $unread_mention_info_span.hide();
        $unread_mention_info_span.text("");
        return;
    }

    $unread_mention_info_span.show();
    $unread_mention_info_span.text("@");
}

/**
 * Parse HTML and return a DocumentFragment.
 *
 * Like any consumer of HTML, this function must only be given input
 * from trusted producers of safe HTML, such as auto-escaping
 * templates; violating this expectation will introduce bugs that are
 * likely to be security vulnerabilities.
 */
export function parse_html(html: string): DocumentFragment {
    const template = document.createElement("template");
    template.innerHTML = html;
    return template.content;
}

/*
 * Handle permission denied to play audio by the browser.
 * This can happen due to two reasons: user denied permission to play audio
 * unconditionally and browser denying permission to play audio without
 * any interactive trigger like a button. See
 * https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/play for more details.
 */
export async function play_audio(elem: HTMLVideoElement): Promise<void> {
    try {
        await elem.play();
    } catch (error) {
        if (!(error instanceof DOMException)) {
            throw error;
        }
        blueslip.debug(`Unable to play audio. ${error.name}: ${error.message}`);
    }
}

export function listener_for_preferred_color_scheme_change(callback: () => void): void {
    const media_query_list = window.matchMedia("(prefers-color-scheme: dark)");
    // MediaQueryList.addEventListener is missing in Safari < 14
    const listener = (): void => {
        if ($(":root").hasClass("color-scheme-automatic")) {
            callback();
        }
    };
    if (media_query_list.addEventListener) {
        media_query_list.addEventListener("change", listener);
    } else {
        // eslint-disable-next-line @typescript-eslint/no-deprecated
        media_query_list.addListener(listener);
    }
}

// Keep the menu icon over which the popover is based off visible.
export function show_left_sidebar_menu_icon(element: HTMLElement): void {
    $(element).closest(".sidebar-menu-icon").addClass("left_sidebar_menu_icon_visible");
}

// Remove the class from element when popover is closed
export function hide_left_sidebar_menu_icon(): void {
    $(".left_sidebar_menu_icon_visible").removeClass("left_sidebar_menu_icon_visible");
}
