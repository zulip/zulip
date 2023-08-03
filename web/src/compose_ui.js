/* Compose box module responsible for manipulating the compose box
   textarea correctly. */

import autosize from "autosize";
import $ from "jquery";
import {insert, replace, set, wrapSelection} from "text-field-edit";

import * as common from "./common";
import {$t} from "./i18n";
import * as loading from "./loading";
import * as people from "./people";
import * as popover_menus from "./popover_menus";
import * as rtl from "./rtl";
import * as stream_data from "./stream_data";
import * as user_status from "./user_status";

export let compose_spinner_visible = false;
let full_size_status = false; // true or false

// Some functions to handle the full size status explicitly
export function set_full_size(is_full) {
    full_size_status = is_full;
}

export function is_full_size() {
    return full_size_status;
}

export function autosize_textarea($textarea) {
    // Since this supports both compose and file upload, one must pass
    // in the text area to autosize.
    if (!is_full_size()) {
        autosize.update($textarea);
    }
}

function get_focus_area(msg_type, opts) {
    // Set focus to "Topic" when narrowed to a stream+topic and "New topic" button clicked.
    if (msg_type === "stream" && opts.stream_id && !opts.topic) {
        return "#stream_message_recipient_topic";
    } else if (
        (msg_type === "stream" && opts.stream_id) ||
        (msg_type === "private" && opts.private_message_recipient)
    ) {
        if (opts.trigger === "new topic button") {
            return "#stream_message_recipient_topic";
        }
        return "#compose-textarea";
    }

    if (msg_type === "stream") {
        return "#compose_select_recipient_widget_wrapper";
    }
    return "#private_message_recipient";
}

// Export for testing
export const _get_focus_area = get_focus_area;

export function set_focus(msg_type, opts) {
    // Called mainly when opening the compose box or switching the
    // message type to set the focus in the first empty input in the
    // compose box.
    if (window.getSelection().toString() === "" || opts.trigger !== "message click") {
        const focus_area = get_focus_area(msg_type, opts);
        $(focus_area).trigger("focus");
    }
}

export function smart_insert_inline($textarea, syntax) {
    function is_space(c) {
        return c === " " || c === "\t" || c === "\n";
    }

    const pos = $textarea.caret();
    const before_str = $textarea.val().slice(0, pos);
    const after_str = $textarea.val().slice(pos);

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

    insert($textarea[0], syntax);
    autosize_textarea($textarea);
}

export function smart_insert_block($textarea, syntax, padding_newlines = 2) {
    const pos = $textarea.caret();
    const before_str = $textarea.val().slice(0, pos);
    const after_str = $textarea.val().slice(pos);

    if (pos > 0) {
        // Insert newline/s before the content block if there is
        // already some content in the compose box and the content
        // block is not being inserted at the beginning, such
        // that there are at least padding_newlines number of new
        // lines between the content and start of the content block.
        let new_lines_before_count = 0;
        let current_pos = pos - 1;
        while (
            current_pos >= 0 &&
            before_str.charAt(current_pos) === "\n" &&
            new_lines_before_count < padding_newlines
        ) {
            // count up to padding_newlines number of new lines before cursor
            current_pos -= 1;
            new_lines_before_count += 1;
        }
        const new_lines_needed_before_count = padding_newlines - new_lines_before_count;
        syntax = "\n".repeat(new_lines_needed_before_count) + syntax;
    }

    let new_lines_after_count = 0;
    let current_pos = 0;
    while (
        current_pos < after_str.length &&
        after_str.charAt(current_pos) === "\n" &&
        new_lines_after_count < padding_newlines
    ) {
        // count up to padding_newlines number of new lines after cursor
        current_pos += 1;
        new_lines_after_count += 1;
    }
    // Insert newline/s after the content block, such that there
    // are at least padding_newlines number of new lines between
    // the content block and the content after the cursor, if any.
    const new_lines_needed_after_count = padding_newlines - new_lines_after_count;
    syntax = syntax + "\n".repeat(new_lines_needed_after_count);

    insert($textarea[0], syntax);
    autosize_textarea($textarea);
}

export function insert_syntax_and_focus(
    syntax,
    $textarea = $("#compose-textarea"),
    mode = "inline",
    padding_newlines,
) {
    // Generic helper for inserting syntax into the main compose box
    // where the cursor was and focusing the area.  Mostly a thin
    // wrapper around smart_insert_inline and smart_inline_block.
    //
    // We focus the textarea first. In theory, we could let the
    // `insert` function of text-area-edit take care of this, since it
    // will focus the target element before manipulating it.
    //
    // But it unfortunately will blur it afterwards if the original
    // focus was something else, which is not behavior we want, so we
    // just focus the textarea in question ourselves before calling
    // it.
    $textarea.trigger("focus");

    if (mode === "inline") {
        smart_insert_inline($textarea, syntax);
    } else if (mode === "block") {
        smart_insert_block($textarea, syntax, padding_newlines);
    }
}

export function replace_syntax(old_syntax, new_syntax, $textarea = $("#compose-textarea")) {
    // The following couple lines are needed to later restore the initial
    // logical position of the cursor after the replacement
    const prev_caret = $textarea.caret();
    const replacement_offset = $textarea.val().indexOf(old_syntax);

    // Replaces `old_syntax` with `new_syntax` text in the compose box. Due to
    // the way that JavaScript handles string replacements, if `old_syntax` is
    // a string it will only replace the first instance. If `old_syntax` is
    // a RegExp with a global flag, it will replace all instances.

    // We need use anonymous function for `new_syntax` to avoid JavaScript's
    // replace() function treating `$`s in new_syntax as special syntax.  See
    // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/replace#Description
    // for details.

    const old_text = $textarea.val();
    replace($textarea[0], old_syntax, () => new_syntax, "after-replacement");
    const new_text = $textarea.val();

    // When replacing content in a textarea, we need to move the cursor
    // to preserve its logical position if and only if the content we
    // just added was before the current cursor position. If it was,
    // we need to move the cursor forward by the increase in the
    // length of the content after the replacement.
    if (prev_caret >= replacement_offset + old_syntax.length) {
        $textarea.caret(prev_caret + new_syntax.length - old_syntax.length);
    } else if (prev_caret > replacement_offset) {
        // In the rare case that our cursor was inside the
        // placeholder, we treat that as though the cursor was
        // just after the placeholder.
        $textarea.caret(replacement_offset + new_syntax.length + 1);
    } else {
        // Otherwise we simply restore it to it's original position
        $textarea.caret(prev_caret);
    }

    // Return if anything was actually replaced.
    return old_text !== new_text;
}

export function compute_placeholder_text(opts) {
    // Computes clear placeholder text for the compose box, depending
    // on what heading values have already been filled out.
    //
    // We return text with the stream and topic name unescaped,
    // because the caller is expected to insert this into the
    // placeholder field in a way that does HTML escaping.
    if (opts.message_type === "stream") {
        const stream = stream_data.get_sub_by_id(opts.stream_id);
        const stream_name = stream ? stream.name : "";

        if (stream_name && opts.topic) {
            return $t(
                {defaultMessage: "Message #{stream_name} > {topic_name}"},
                {stream_name, topic_name: opts.topic},
            );
        } else if (stream_name) {
            return $t({defaultMessage: "Message #{stream_name}"}, {stream_name});
        }
    }

    // For direct messages
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
        const compose_top = $("#navbar-fixed-container").height();
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
    $("#scroll-to-bottom-button-container").removeClass("show");
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

export function handle_keydown(event, $textarea) {
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
        format_text($textarea, type);
        autosize_textarea($textarea);
        event.preventDefault();
    }
}

export function handle_keyup(_event, $textarea) {
    // Set the rtl class if the text has an rtl direction, remove it otherwise
    rtl.set_rtl_class_for_textarea($textarea);
}

export function format_text($textarea, type, inserted_content) {
    const italic_syntax = "*";
    const bold_syntax = "**";
    const bold_and_italic_syntax = "***";
    let is_selected_text_italic = false;
    let is_inner_text_italic = false;
    const field = $textarea.get(0);
    let range = $textarea.range();
    let text = $textarea.val();
    const selected_text = range.text;

    // Remove new line and space around selected text.
    const left_trim_length = range.text.length - range.text.trimStart().length;
    const right_trim_length = range.text.length - range.text.trimEnd().length;

    field.setSelectionRange(range.start + left_trim_length, range.end - right_trim_length);
    range = $textarea.range();

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
        case "linked": {
            // From a paste event with a URL as inserted content
            wrapSelection(field, "[", `](${inserted_content})`);
            // Put the cursor at the end of the selection range
            // and all wrapped material
            $textarea.caret(range.end + `[](${inserted_content})`.length);
            break;
        }
    }
}

/* TODO: This functions don't belong in this module, as they have
 * nothing to do with the compose textarea. */
export function hide_compose_spinner() {
    compose_spinner_visible = false;
    $(".compose-submit-button .loader").hide();
    $(".compose-submit-button span").show();
    $(".compose-submit-button").removeClass("disable-btn");
}

export function show_compose_spinner() {
    compose_spinner_visible = true;
    // Always use white spinner.
    loading.show_button_spinner($(".compose-submit-button .loader"), true);
    $(".compose-submit-button span").hide();
    $(".compose-submit-button").addClass("disable-btn");
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
