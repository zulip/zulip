import $ from "jquery";
import type * as tippy from "tippy.js";

import * as blueslip from "./blueslip.ts";
import * as hash_parser from "./hash_parser.ts";
import * as keydown_util from "./keydown_util.ts";

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

function extract_emoji_code_from_class(emoji_class_string: string | undefined): string | undefined {
    if (emoji_class_string === undefined) {
        return undefined;
    }

    const classes = emoji_class_string.split(/\s+/);
    const regex = /^emoji-([0-9a-fA-F-]+)$/;

    for (const cls of classes) {
        const match = regex.exec(cls);
        if (match) {
            return match?.[1] ?? undefined;
        }
    }
    return undefined;
}

export function convert_emoji_element_to_unicode($emoji_elt: JQuery): string {
    // This is a custom emoji, we do not have corresponding emoji
    // unicode for these so we return original markdown.
    if ($emoji_elt.is("img")) {
        return $emoji_elt.attr("alt") ?? "";
    }

    const emoji_class_string = $emoji_elt.attr("class");
    const emoji_code_hex_string = extract_emoji_code_from_class(emoji_class_string);
    if (emoji_code_hex_string === undefined) {
        return $emoji_elt.text();
    }

    const emoji_code_parts = emoji_code_hex_string.split("-");
    const emoji_unicode = emoji_code_parts
        .map((emoji_code) => {
            const emoji_code_int = Number.parseInt(emoji_code, 16);
            // Validate the parameter passed to String.fromCodePoint() (here, emoji_code_int).
            // "An integer between 0 and 0x10FFFF (inclusive) representing a Unicode code point."
            // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/fromCodePoint
            // for details.
            if (
                Number.isNaN(emoji_code_int) ||
                !(emoji_code_int >= 0 && emoji_code_int <= 0x10ffff)
            ) {
                blueslip.error("Invalid unicode codepoint for emoji", {emoji_code_int});
                return $emoji_elt.text();
            }
            return String.fromCodePoint(emoji_code_int);
        })
        .join("");
    return emoji_unicode;
}

export function convert_unicode_eligible_emoji_to_unicode($element: JQuery): void {
    $element
        .find(".emoji")
        .text(function () {
            return convert_emoji_element_to_unicode($(this));
        })
        .contents()
        .unwrap();
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

export let get_collapsible_status_array = ($elements: JQuery): boolean[] =>
    [...$elements].map(
        (element) => $(element).is("blockquote") || is_user_said_paragraph($(element)),
    );

export function rewire_get_collapsible_status_array(
    value: typeof get_collapsible_status_array,
): void {
    get_collapsible_status_array = value;
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
export async function play_audio(elem: HTMLAudioElement): Promise<void> {
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
export function show_left_sidebar_menu_icon(element: Element): void {
    $(element).closest(".sidebar-menu-icon").addClass("left_sidebar_menu_icon_visible");
}

// Remove the class from element when popover is closed
export function hide_left_sidebar_menu_icon(): void {
    $(".left_sidebar_menu_icon_visible").removeClass("left_sidebar_menu_icon_visible");
}

export function matches_viewport_state(state_string: string): boolean {
    const app_main = document.querySelector(".app-main");
    if (app_main instanceof HTMLElement) {
        const app_main_after_content = getComputedStyle(app_main, ":after").content ?? "";
        /* The .content property includes the quotation marks, so we
           strip them before splitting on the empty space. */
        const app_main_after_content_array = app_main_after_content.replaceAll('"', "").split(" ");

        return app_main_after_content_array.includes(state_string);
    }
    return false;
}

export function disable_element_and_add_tooltip($element: JQuery, tooltip_text: string): void {
    // Since disabled elements do not fire events, it is not possible to trigger
    // tippy tooltips on disabled elements. So, as a workaround, we wrap the
    // disabled element in a span and show the tooltip on this wrapper instead.
    // https://atomiks.github.io/tippyjs/v6/constructor/#disabled-elements
    $element.prop("disabled", true);
    const $disabled_tooltip_wrapper = $element.parent(".disabled-tooltip");
    if ($disabled_tooltip_wrapper.length > 0) {
        // If element is already wrapped in a disabled-tooltip wrapper,
        // only update the tooltip text if it has changed.
        if ($disabled_tooltip_wrapper.attr("data-tippy-content") !== tooltip_text) {
            $disabled_tooltip_wrapper.attr("data-tippy-content", tooltip_text);
        }
        return;
    }
    const $tooltip_target_wrapper = $("<span>");
    $tooltip_target_wrapper.addClass("disabled-tooltip");
    $tooltip_target_wrapper.attr("data-tippy-content", tooltip_text).attr("tabindex", "0");
    $element.wrap($tooltip_target_wrapper);
}

export function enable_element_and_remove_tooltip($element: JQuery): void {
    // This method reverses the effects of disable_element_and_add_tooltip,
    // and explicitly removes any attached tooltips on the wrapper to prevent
    // ghost tooltips.
    $element.prop("disabled", false);
    const tooltip_wrapper: tippy.ReferenceElement | undefined =
        $element.parent(".disabled-tooltip")[0];
    if (tooltip_wrapper) {
        if (tooltip_wrapper._tippy) {
            tooltip_wrapper._tippy.destroy();
        }
        $element.unwrap(".disabled-tooltip");
    }
}
