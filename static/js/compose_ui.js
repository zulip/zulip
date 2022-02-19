import autosize from "autosize";
import $ from "jquery";
import {set, wrapSelection} from "text-field-edit";

import * as common from "./common";
import {$t} from "./i18n";
import * as loading from "./loading";
import * as people from "./people";
import * as popover_menus from "./popover_menus";
import * as rtl from "./rtl";
import * as user_status from "./user_status";

let full_size_status = false; // true or false

// Some functions to handle the full size status explicitly
export function set_full_size(is_full) {
    full_size_status = is_full;
}

export function is_full_size() {
    return full_size_status;
}

export function autosize_textarea(textarea) {
    // Since this supports both compose and file upload, one must pass
    // in the text area to autosize.
    if (!is_full_size()) {
        autosize.update(textarea);
    }
}

export function smart_insert(textarea, syntax) {
    function is_space(c) {
        return c === " " || c === "\t" || c === "\n";
    }

    const pos = textarea.caret();
    const before_str = textarea.val().slice(0, pos);
    const after_str = textarea.val().slice(pos);

    if (
        pos > 0 &&
        // If there isn't space either at the end of the content
        // before the insert or (unlikely) at the start of the syntax,
        // add one.
        !is_space(before_str.slice(-1)) &&
        !is_space(syntax[0])
    ) {
        syntax = " " + syntax;
    }

    // If there isn't whitespace either at the end of the syntax or the
    // start of the content after the syntax, add one.
    if (
        !(
            (after_str.length > 0 && is_space(after_str[0])) ||
            (syntax.length > 0 && is_space(syntax.slice(-1)))
        )
    ) {
        syntax += " ";
    }

    textarea.trigger("focus");

    // We prefer to use insertText, which supports things like undo better
    // for rich-text editing features like inserting links.  But we fall
    // back to textarea.caret if the browser doesn't support insertText.
    if (!document.execCommand("insertText", false, syntax)) {
        textarea.caret(syntax);
    }

    autosize_textarea(textarea);
}

export function insert_syntax_and_focus(syntax, textarea = $("#compose-textarea")) {
    // Generic helper for inserting syntax into the main compose box
    // where the cursor was and focusing the area.  Mostly a thin
    // wrapper around smart_insert.
    smart_insert(textarea, syntax);
}

export function replace_syntax(old_syntax, new_syntax, textarea = $("#compose-textarea")) {
    // Replaces `old_syntax` with `new_syntax` text in the compose box. Due to
    // the way that JavaScript handles string replacements, if `old_syntax` is
    // a string it will only replace the first instance. If `old_syntax` is
    // a RegExp with a global flag, it will replace all instances.
    textarea.val(
        textarea.val().replace(
            old_syntax,
            () =>
                // We need this anonymous function to avoid JavaScript's
                // replace() function treating `$`s in new_syntax as special syntax.  See
                // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/replace#Description
                // for details.
                new_syntax,
        ),
    );
}

export function compute_placeholder_text(opts) {
    // Computes clear placeholder text for the compose box, depending
    // on what heading values have already been filled out.
    //
    // We return text with the stream and topic name unescaped,
    // because the caller is expected to insert this into the
    // placeholder field in a way that does HTML escaping.
    if (opts.message_type === "stream") {
        if (opts.topic) {
            return $t(
                {defaultMessage: "Message #{stream_name} > {topic_name}"},
                {stream_name: opts.stream, topic_name: opts.topic},
            );
        } else if (opts.stream) {
            return $t({defaultMessage: "Message #{stream_name}"}, {stream_name: opts.stream});
        }
    }

    // For private messages
    if (opts.private_message_recipient) {
        const recipient_list = opts.private_message_recipient.split(",");
        const recipient_names = recipient_list
            .map((recipient) => {
                const user = people.get_by_email(recipient);
                return user.full_name;
            })
            .join(", ");

        if (recipient_list.length === 1) {
            // If it's a single user, display status text if available
            const user = people.get_by_email(recipient_list[0]);
            const status = user_status.get_status_text(user.user_id);
            if (status) {
                return $t(
                    {defaultMessage: "Message {recipient_name} ({recipient_status})"},
                    {recipient_name: recipient_names, recipient_status: status},
                );
            }
        }
        return $t({defaultMessage: "Message {recipient_names}"}, {recipient_names});
    }
    return $t({defaultMessage: "Compose your message here"});
}

export function set_compose_box_top(set_top) {
    if (set_top) {
        // As `#compose` has `position: fixed` property, we cannot
        // make the compose-box to attain the correct height just by
        // using CSS. If that wasn't the case, we could have somehow
        // refactored the HTML so as to consider only the space below
        // below the `#navbar_alerts` as `height: 100%` of `#compose`.
        const compose_top =
            $("#navbar_alerts_wrapper").height() +
            $(".header").height() +
            Number.parseInt($(".header").css("paddingBottom"), 10);
        $("#compose").css("top", compose_top + "px");
    } else {
        $("#compose").css("top", "");
    }
}

export function make_compose_box_full_size() {
    set_full_size(true);

    // The autosize should be destroyed for the full size compose
    // box else it will interfere and shrink its size accordingly.
    autosize.destroy($("#compose-textarea"));

    $("#compose").addClass("compose-fullscreen");

    // Set the `top` property of compose-box.
    set_compose_box_top(true);

    $(".collapse_composebox_button").show();
    $(".expand_composebox_button").hide();
    $("#scroll-to-bottom-button-container").hide();
    $("#compose-textarea").trigger("focus");
}

export function make_compose_box_original_size() {
    set_full_size(false);

    $("#compose").removeClass("compose-fullscreen");

    // Unset the `top` property of compose-box.
    set_compose_box_top(false);

    // Again initialise the compose textarea as it was destroyed
    // when compose box was made full screen
    autosize($("#compose-textarea"));

    $(".collapse_composebox_button").hide();
    $(".expand_composebox_button").show();
    $("#compose-textarea").trigger("focus");
}

export function handle_keydown(event, textarea) {
    // The event.key property will have uppercase letter if
    // the "Shift + <key>" combo was used or the Caps Lock
    // key was on. We turn to key to lowercase so the key bindings
    // work regardless of whether Caps Lock was on or not.
    const key = event.key.toLowerCase();
    let type;
    if (key === "b") {
        type = "bold";
    } else if (key === "i" && !event.shiftKey) {
        type = "italic";
    } else if (key === "l" && event.shiftKey) {
        type = "link";
    }

    // detect Cmd and Ctrl key
    const isCmdOrCtrl = common.has_mac_keyboard() ? event.metaKey : event.ctrlKey;

    if (type && isCmdOrCtrl) {
        format_text(textarea, type);
        autosize_textarea(textarea);
        event.preventDefault();
    }
}

export function handle_keyup(event, textarea) {
    // Set the rtl class if the text has an rtl direction, remove it otherwise
    rtl.set_rtl_class_for_textarea(textarea);
}

export function format_text(textarea, type) {
    const italic_syntax = "*";
    const bold_syntax = "**";
    const bold_and_italic_syntax = "***";
    let is_selected_text_italic = false;
    let is_inner_text_italic = false;
    const field = textarea.get(0);
    let range = textarea.range();
    let text = textarea.val();
    const selected_text = range.text;

    // Remove new line and space around selected text.
    const left_trim_length = range.text.length - range.text.trimStart().length;
    const right_trim_length = range.text.length - range.text.trimEnd().length;

    field.setSelectionRange(range.start + left_trim_length, range.end - right_trim_length);
    range = textarea.range();

    const is_selection_bold = () =>
        // First check if there are enough characters before/after selection.
        range.start >= bold_syntax.length &&
        text.length - range.end >= bold_syntax.length &&
        // And then if the characters have bold_syntax around them.
        text.slice(range.start - bold_syntax.length, range.start) === bold_syntax &&
        text.slice(range.end, range.end + bold_syntax.length) === bold_syntax;

    const is_inner_text_bold = () =>
        // Check if selected text itself has bold_syntax inside it.
        range.length > 4 &&
        selected_text.slice(0, bold_syntax.length) === bold_syntax &&
        selected_text.slice(-bold_syntax.length) === bold_syntax;

    switch (type) {
        case "bold":
            // Ctrl + B: Toggle bold syntax on selection.

            // If the selection is already surrounded by bold syntax,
            // remove it rather than adding another copy.
            if (is_selection_bold()) {
                // Remove the bold_syntax from text.
                text =
                    text.slice(0, range.start - bold_syntax.length) +
                    text.slice(range.start, range.end) +
                    text.slice(range.end + bold_syntax.length);
                set(field, text);
                field.setSelectionRange(
                    range.start - bold_syntax.length,
                    range.end - bold_syntax.length,
                );
                break;
            } else if (is_inner_text_bold()) {
                // Remove bold syntax inside the selection, if present.
                text =
                    text.slice(0, range.start) +
                    text.slice(range.start + bold_syntax.length, range.end - bold_syntax.length) +
                    text.slice(range.end);
                set(field, text);
                field.setSelectionRange(range.start, range.end - bold_syntax.length * 2);
                break;
            }

            // Otherwise, we don't have bold syntax, so we add it.
            wrapSelection(field, bold_syntax);
            break;
        case "italic":
            // Ctrl + I: Toggle italic syntax on selection. This is
            // much more complex than toggling bold syntax, because of
            // the following subtle detail: If our selection is
            // **foo**, toggling italics should add italics, since in
            // fact it's just bold syntax, even though with *foo* and
            // ***foo*** should remove italics.

            // If the text is already italic, we remove the italic_syntax from text.
            if (range.start >= 1 && text.length - range.end >= italic_syntax.length) {
                // If text has italic_syntax around it.
                const has_italic_syntax =
                    text.slice(range.start - italic_syntax.length, range.start) === italic_syntax &&
                    text.slice(range.end, range.end + italic_syntax.length) === italic_syntax;

                if (is_selection_bold()) {
                    // If text has bold_syntax around it.
                    if (
                        range.start >= 3 &&
                        text.length - range.end >= bold_and_italic_syntax.length
                    ) {
                        // If text is both bold and italic.
                        const has_bold_and_italic_syntax =
                            text.slice(range.start - bold_and_italic_syntax.length, range.start) ===
                                bold_and_italic_syntax &&
                            text.slice(range.end, range.end + bold_and_italic_syntax.length) ===
                                bold_and_italic_syntax;
                        if (has_bold_and_italic_syntax) {
                            is_selected_text_italic = true;
                        }
                    }
                } else if (has_italic_syntax) {
                    // If text is only italic.
                    is_selected_text_italic = true;
                }
            }

            if (is_selected_text_italic) {
                // If text has italic syntax around it, we remove the italic syntax.
                text =
                    text.slice(0, range.start - italic_syntax.length) +
                    text.slice(range.start, range.end) +
                    text.slice(range.end + italic_syntax.length);
                set(field, text);
                field.setSelectionRange(
                    range.start - italic_syntax.length,
                    range.end - italic_syntax.length,
                );
                break;
            } else if (
                selected_text.length > italic_syntax.length * 2 &&
                // If the selected text contains italic syntax
                selected_text.slice(0, italic_syntax.length) === italic_syntax &&
                selected_text.slice(-italic_syntax.length) === italic_syntax
            ) {
                if (is_inner_text_bold()) {
                    if (
                        selected_text.length > bold_and_italic_syntax.length * 2 &&
                        selected_text.slice(0, bold_and_italic_syntax.length) ===
                            bold_and_italic_syntax &&
                        selected_text.slice(-bold_and_italic_syntax.length) ===
                            bold_and_italic_syntax
                    ) {
                        // If selected text is both bold and italic.
                        is_inner_text_italic = true;
                    }
                } else {
                    // If selected text is only italic.
                    is_inner_text_italic = true;
                }
            }

            if (is_inner_text_italic) {
                // We remove the italic_syntax from within the selected text.
                text =
                    text.slice(0, range.start) +
                    text.slice(
                        range.start + italic_syntax.length,
                        range.end - italic_syntax.length,
                    ) +
                    text.slice(range.end);
                set(field, text);
                field.setSelectionRange(range.start, range.end - italic_syntax.length * 2);
                break;
            }

            wrapSelection(field, italic_syntax);
            break;
        case "link": {
            // Ctrl + L: Insert a link to selected text
            wrapSelection(field, "[", "](url)");

            // Change selected text to `url` part of the syntax.
            // If <text> marks the selected region, we're mapping:
            // <text> => [text](<url>).
            const new_start = range.end + "[](".length;
            const new_end = new_start + "url".length;
            field.setSelectionRange(new_start, new_end);
            break;
        }
    }
}

export function hide_compose_spinner() {
    $("#compose-send-button .loader").hide();
    $("#compose-send-button span").show();
    $("#compose-send-button").removeClass("disable-btn");
}

export function show_compose_spinner() {
    // Always use white spinner.
    loading.show_button_spinner($("#compose-send-button .loader"), true);
    $("#compose-send-button span").hide();
    $("#compose-send-button").addClass("disable-btn");
}

export function get_compose_click_target(e) {
    const compose_control_buttons_popover = popover_menus.get_compose_control_buttons_popover();
    if (
        compose_control_buttons_popover &&
        $(compose_control_buttons_popover.popper).has(e.target).length
    ) {
        return compose_control_buttons_popover.reference;
    }
    return e.target;
}
