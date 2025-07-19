/* Compose box module responsible for manipulating the compose box
   textarea correctly. */

import autosize from "autosize";
import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";
import {
    insertTextIntoField,
    replaceFieldText,
    setFieldText,
    wrapFieldSelection,
} from "text-field-edit";
import * as z from "zod/mini";

import type {Typeahead} from "./bootstrap_typeahead.ts";
import * as bulleted_numbered_list_util from "./bulleted_numbered_list_util.ts";
import * as channel from "./channel.ts";
import * as common from "./common.ts";
import * as compose_state from "./compose_state.ts";
import type {TypeaheadSuggestion} from "./composebox_typeahead.ts";
import {$t, $t_html} from "./i18n.ts";
import * as loading from "./loading.ts";
import * as markdown from "./markdown.ts";
import * as people from "./people.ts";
import {postprocess_content} from "./postprocess_content.ts";
import * as rendered_markdown from "./rendered_markdown.ts";
import * as rtl from "./rtl.ts";
import {current_user} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as user_status from "./user_status.ts";
import * as util from "./util.ts";

export const DEFAULT_COMPOSE_PLACEHOLDER = $t({defaultMessage: "Compose your message here"});

export type ComposeTriggeredOptions = {
    trigger: string;
} & (
    | {
          message_type: "stream";
          topic: string;
          stream_id?: number | undefined;
      }
    | {
          message_type: "private";
          private_message_recipient_ids: number[];
      }
);
export type ComposePlaceholderOptions =
    | {
          message_type: "stream";
          stream_id: number | undefined;
          topic: string;
      }
    | {
          message_type: "private";
          direct_message_user_ids: number[];
      };
type SelectedLinesSections = {
    before_lines: string;
    separating_new_line_before: boolean;
    selected_lines: string;
    separating_new_line_after: boolean;
    after_lines: string;
};

const message_render_response_schema = z.object({
    msg: z.string(),
    result: z.string(),
    rendered: z.string(),
});

export let compose_spinner_visible = false;

export function rewire_compose_spinner_visible(value: typeof compose_spinner_visible): void {
    compose_spinner_visible = value;
}

export let shift_pressed = false; // true or false
export let code_formatting_button_triggered = false; // true or false
export let compose_textarea_typeahead: Typeahead<TypeaheadSuggestion> | undefined;
let full_size_status = false; // true or false
let expanded_status = false; // true or false

export function set_compose_textarea_typeahead(typeahead: Typeahead<TypeaheadSuggestion>): void {
    compose_textarea_typeahead = typeahead;
}

export function set_code_formatting_button_triggered(value: boolean): void {
    code_formatting_button_triggered = value;
}

// Some functions to handle the expanded status explicitly
export function set_expanded_status(is_expanded: boolean, is_full = is_expanded): void {
    expanded_status = is_expanded;
    full_size_status = is_full;
    // Show typeahead at bottom of textarea on compose full size.
    if (compose_textarea_typeahead) {
        compose_textarea_typeahead.dropup = !is_full;
    }
}

export function is_expanded(): boolean {
    return expanded_status;
}

export function is_full_size(): boolean {
    return full_size_status;
}

export let autosize_textarea = ($textarea: JQuery<HTMLTextAreaElement>): void => {
    // Since this supports both compose and file upload, one must pass
    // in the text area to autosize.
    if (!is_expanded()) {
        autosize.update($textarea);
    }
};

export function rewire_autosize_textarea(value: typeof autosize_textarea): void {
    autosize_textarea = value;
}

export let insert_and_scroll_into_view = (
    content: string,
    $textarea: JQuery<HTMLTextAreaElement>,
    replace_all = false,
    replace_all_without_undo_support = false,
): void => {
    if (replace_all_without_undo_support) {
        // setFieldText is very slow and noticeable when inserting 10k+
        // characters of text like from a drafted response,
        // but we use it since we want to support `undo`. If we don't want
        // to support `undo`, we can use a faster method.
        $textarea.val(content);
    } else if (replace_all) {
        setFieldText(util.the($textarea), content);
    } else {
        insertTextIntoField(util.the($textarea), content);
    }
    // Blurring and refocusing ensures the cursor / selection is in view
    // in chromium browsers.
    $textarea.trigger("blur");
    $textarea.trigger("focus");
    autosize_textarea($textarea);
};

export function rewire_insert_and_scroll_into_view(
    value: typeof insert_and_scroll_into_view,
): void {
    insert_and_scroll_into_view = value;
}

export function maybe_show_scrolling_formatting_buttons(container_selector: string): void {
    const button_container = document.querySelector(container_selector);
    const button_bar = document.querySelector(
        `${container_selector} .compose-control-buttons-container`,
    );

    if (!button_container || !button_bar) {
        return;
    }

    const button_container_width = button_container?.clientWidth;
    const button_bar_width = button_bar?.scrollWidth;
    const button_bar_scroll_left = button_bar?.scrollLeft;

    const button_bar_max_left_scroll = button_bar_width - button_container_width;

    assert(
        typeof button_container_width === "number" &&
            typeof button_bar_width === "number" &&
            typeof button_bar_scroll_left === "number",
    );

    // Set these values as data attributes for ready access by
    // other scrolling logic
    //
    // TODO: Modify eslint config, if we wish to avoid dataset
    //
    /* eslint unicorn/prefer-dom-node-dataset: "off" */
    button_container.setAttribute("data-button-container-width", button_container_width.toString());
    button_container.setAttribute("data-button-bar-width", button_bar_width.toString());
    button_container.setAttribute(
        "data-button-bar-max-left-scroll",
        button_bar_max_left_scroll.toString(),
    );

    button_container.classList.remove("can-scroll-forward", "can-scroll-backward");

    if (button_container_width < button_bar_width) {
        // It's possible that the buttons may be scrolled prior
        // to the viewport being resized
        if (button_bar_scroll_left < button_bar_max_left_scroll) {
            button_container?.classList.add("can-scroll-forward");
        }

        if (button_bar_scroll_left > 0) {
            button_container?.classList.add("can-scroll-backward");
        }
    }
}

function get_focus_area(opts: ComposeTriggeredOptions): string {
    // Set focus to "Topic" when narrowed to a stream+topic
    // and "Start new conversation" button clicked.
    if (
        opts.message_type === "stream" &&
        opts.stream_id &&
        !opts.topic &&
        !stream_data.can_use_empty_topic(opts.stream_id)
    ) {
        return "input#stream_message_recipient_topic";
    } else if (
        (opts.message_type === "stream" && opts.stream_id !== undefined) ||
        (opts.message_type === "private" && opts.private_message_recipient_ids.length > 0)
    ) {
        if (
            opts.trigger === "clear topic button" ||
            opts.trigger === "compose_hotkey" ||
            opts.trigger === "inbox_nofocus"
        ) {
            return "input#stream_message_recipient_topic";
        }
        return "textarea#compose-textarea";
    }

    if (opts.message_type === "stream") {
        return "#compose_select_recipient_widget_wrapper";
    }
    return "#private_message_recipient";
}

// Export for testing
export const _get_focus_area = get_focus_area;

export function set_focus(opts: ComposeTriggeredOptions): void {
    // Called mainly when opening the compose box or switching the
    // message type to set the focus in the first empty input in the
    // compose box.
    if (window.getSelection()!.toString() === "" || opts.trigger !== "message click") {
        const focus_area = get_focus_area(opts);
        $(focus_area).trigger("focus");
    }
}

export let smart_insert_inline = ($textarea: JQuery<HTMLTextAreaElement>, syntax: string): void => {
    function is_space(c: string | undefined): boolean {
        return c === " " || c === "\t" || c === "\n";
    }

    const pos = $textarea.caret();
    const before_str = $textarea.val()!.slice(0, pos);
    const after_str = $textarea.val()!.slice(pos);

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

    insert_and_scroll_into_view(syntax, $textarea);
};

export function rewire_smart_insert_inline(value: typeof smart_insert_inline): void {
    smart_insert_inline = value;
}

export function smart_insert_block(
    $textarea: JQuery<HTMLTextAreaElement>,
    syntax: string,
    padding_newlines = 2,
): void {
    const pos = $textarea.caret();
    const before_str = $textarea.val()!.slice(0, pos);
    const after_str = $textarea.val()!.slice(pos);

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

    insert_and_scroll_into_view(syntax, $textarea);
}

export let insert_syntax_and_focus = (
    syntax: string,
    $textarea = $<HTMLTextAreaElement>("textarea#compose-textarea"),
    mode = "inline",
    padding_newlines?: number,
): void => {
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
};

export function rewire_insert_syntax_and_focus(value: typeof insert_syntax_and_focus): void {
    insert_syntax_and_focus = value;
}

export let replace_syntax = (
    old_syntax: string,
    new_syntax: string,
    $textarea = $<HTMLTextAreaElement>("textarea#compose-textarea"),
    ignore_caret = false,
): boolean => {
    // The following couple lines are needed to later restore the initial
    // logical position of the cursor after the replacement
    const prev_caret = $textarea.caret();
    const replacement_offset = $textarea.val()!.indexOf(old_syntax);

    // Replaces `old_syntax` with `new_syntax` text in the compose box. Due to
    // the way that JavaScript handles string replacements, if `old_syntax` is
    // a string it will only replace the first instance. If `old_syntax` is
    // a RegExp with a global flag, it will replace all instances.

    // We need use anonymous function for `new_syntax` to avoid JavaScript's
    // replace() function treating `$`s in new_syntax as special syntax.  See
    // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/replace#Description
    // for details.

    const old_text = $textarea.val();
    replaceFieldText(util.the($textarea), old_syntax, () => new_syntax, "after-replacement");
    const new_text = $textarea.val();
    const has_changed = old_text !== new_text;

    // If the caller wants to ignore the caret position, we return early.
    // This is useful e.g. when we are replacing content without affecting
    // which element has focus.
    if (ignore_caret) {
        return has_changed;
    }

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
    return has_changed;
};

export function rewire_replace_syntax(value: typeof replace_syntax): void {
    replace_syntax = value;
}

export function compute_placeholder_text(opts: ComposePlaceholderOptions): string {
    // Computes clear placeholder text for the compose box, depending
    // on what heading values have already been filled out.
    //
    // We return text with the stream and topic name unescaped,
    // because the caller is expected to insert this into the
    // placeholder field in a way that does HTML escaping.
    if (opts.message_type === "stream") {
        let stream_name = "";
        if (opts.stream_id !== undefined) {
            const stream = stream_data.get_sub_by_id(opts.stream_id);
            if (stream !== undefined) {
                stream_name = stream.name;
            }
        }

        // The following block of code will do nothing if the channel is
        // not selected as the placeholder in that case will be "Compose your message here".
        let topic_display_name: string | undefined;
        if (opts.topic !== "") {
            topic_display_name = opts.topic;
        } else if (
            stream_data.can_use_empty_topic(opts.stream_id) &&
            !$("input#stream_message_recipient_topic").is(":focus")
        ) {
            topic_display_name = util.get_final_topic_display_name(opts.topic);
        }

        if (stream_name && topic_display_name !== undefined) {
            return $t(
                {defaultMessage: "Message #{channel_name} > {topic_name}"},
                {channel_name: stream_name, topic_name: topic_display_name},
            );
        } else if (stream_name) {
            return $t({defaultMessage: "Message #{channel_name}"}, {channel_name: stream_name});
        }
    } else if (opts.direct_message_user_ids.length > 0) {
        const user_ids = opts.direct_message_user_ids;
        if (people.is_direct_message_conversation_with_self(user_ids)) {
            return $t({defaultMessage: "Message yourself"});
        }
        const users = people.get_users_from_ids(user_ids);
        const recipient_parts = users.map((user) => {
            if (people.should_add_guest_user_indicator(user.user_id)) {
                return $t({defaultMessage: "{name} (guest)"}, {name: user.full_name});
            }
            return user.full_name;
        });
        const recipient_names = util.format_array_as_list(recipient_parts, "long", "conjunction");

        if (users.length === 1 && users[0] !== undefined) {
            // If it's a single user, display status text if available
            const user = users[0];
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
    return DEFAULT_COMPOSE_PLACEHOLDER;
}

export let set_compose_box_top = (set_top: boolean): void => {
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
};

export function rewire_set_compose_box_top(value: typeof set_compose_box_top): void {
    set_compose_box_top = value;
}

export function make_compose_box_full_size(): void {
    set_expanded_status(true);

    // The autosize should be destroyed for the full size compose
    // box else it will interfere and shrink its size accordingly.
    autosize.destroy($("textarea#compose-textarea"));

    $("#compose").removeClass("compose-intermediate");
    $("#compose").removeClass("automatically-expanded");
    $("#compose").addClass("compose-fullscreen");

    // Set the `top` property of compose-box.
    set_compose_box_top(true);

    $("#scroll-to-bottom-button-container").removeClass("show");
    $("textarea#compose-textarea").trigger("focus");
}

export function make_compose_box_intermediate_size(): void {
    set_expanded_status(true, false);

    // The autosize should be destroyed for the intermediate size compose
    // box else it will interfere and shrink its size accordingly.
    autosize.destroy($("textarea#compose-textarea"));

    $("#compose").removeClass("compose-fullscreen");
    $("#compose").removeClass("automatically-expanded");
    $("#compose").addClass("compose-intermediate");

    // Unset the `top` property of compose-box.
    set_compose_box_top(false);

    $("textarea#compose-textarea").trigger("focus");
}

export function make_compose_box_original_size(): void {
    set_expanded_status(false);

    $("#compose").removeClass("compose-fullscreen");
    $("#compose").removeClass("compose-intermediate");
    $("#compose").removeClass("automatically-expanded");

    // Unset the `top` property of compose-box.
    set_compose_box_top(false);

    // Again initialise the compose textarea as it was destroyed
    // when compose box was made full screen
    autosize($("textarea#compose-textarea"));

    $("textarea#compose-textarea").trigger("focus");
}

export function handle_scrolling_formatting_buttons(event: JQuery.ScrollEvent): void {
    event.stopPropagation();
    const $button_bar = $(event.currentTarget);
    const $button_container = $button_bar.closest(".compose-scrolling-buttons-container");
    const button_bar_max_left_scroll = Number(
        $button_container.attr("data-button-bar-max-left-scroll"),
    );
    const button_bar_left_scroll = $button_bar.scrollLeft();

    // If we're within 4px of the start or end of the formatting buttons,
    // go ahead and hide the respective scrolling button
    const hide_scroll_button_threshold_px = 4;

    $button_container.addClass("can-scroll-forward can-scroll-backward");

    assert(typeof button_bar_left_scroll === "number");

    if (button_bar_left_scroll >= button_bar_max_left_scroll - hide_scroll_button_threshold_px) {
        $button_container.removeClass("can-scroll-forward");
    }
    if (button_bar_left_scroll <= hide_scroll_button_threshold_px) {
        $button_container.removeClass("can-scroll-backward");
    }
}

export function handle_keydown(
    event: JQuery.KeyboardEventBase,
    $textarea: JQuery<HTMLTextAreaElement>,
): void {
    if (event.key === "Shift") {
        shift_pressed = true;
    }
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

export function handle_keyup(
    _event: JQuery.KeyboardEventBase | null,
    $textarea: JQuery<HTMLTextAreaElement>,
): void {
    if (_event?.key === "Shift") {
        shift_pressed = false;
    }
    // Set the rtl class if the text has an rtl direction, remove it otherwise
    rtl.set_rtl_class_for_textarea($textarea);
}

export function cursor_inside_code_block($textarea: JQuery<HTMLTextAreaElement>): boolean {
    // Returns whether the cursor is at a point that would be inside
    // a code block on rendering the textarea content as markdown.
    const cursor_position = $textarea.caret();
    const current_content = $textarea.val()!;

    return position_inside_code_block(current_content, cursor_position);
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

export let format_text = (
    $textarea: JQuery<HTMLTextAreaElement>,
    type: string,
    inserted_content = "",
): void => {
    const italic_syntax = "*";
    const bold_syntax = "**";
    const bold_and_italic_syntax = "***";
    let is_selected_text_italic = false;
    let is_inner_text_italic = false;
    const field = $textarea.get(0)!;
    let range = $textarea.range();
    let text = $textarea.val()!;
    // Remove new line and space around selected text, except list formatting,
    // where we want to especially preserve any selected new line character
    // before the selected text, as it is conventionally depicted with a highlight
    // at the end of the previous line, which we would like to format.
    const TRIM_ONLY_END_TYPES = ["bulleted", "numbered"];

    let start_trim_length;
    if (TRIM_ONLY_END_TYPES.includes(type)) {
        start_trim_length = 0;
    } else {
        start_trim_length = range.text.length - range.text.trimStart().length;
    }
    const end_trim_length = range.text.length - range.text.trimEnd().length;
    field.setSelectionRange(range.start + start_trim_length, range.end - end_trim_length);
    range = $textarea.range();
    const selected_text = range.text;

    // Check if the selection is already surrounded by syntax
    const is_selection_formatted = (syntax_start: string, syntax_end = syntax_start): boolean =>
        range.start >= syntax_start.length &&
        text.length - range.end >= syntax_end.length &&
        text.slice(range.start - syntax_start.length, range.start) === syntax_start &&
        text.slice(range.end, range.end + syntax_end.length) === syntax_end;

    // Check if selected text itself has syntax inside it.
    const is_inner_text_formatted = (syntax_start: string, syntax_end = syntax_start): boolean =>
        range.length >= syntax_start.length + syntax_end.length &&
        selected_text.startsWith(syntax_start) &&
        selected_text.endsWith(syntax_end);

    const section_off_selected_lines = (): SelectedLinesSections => {
        // Divide all lines of text (separated by `\n`) into those entirely or
        // partially selected, and those before and after these selected lines.
        const before = text.slice(0, range.start);
        const after = text.slice(range.end);
        let separating_new_line_before = false;
        let closest_new_line_beginning_before_index;
        if (before.includes("\n")) {
            separating_new_line_before = true;
            closest_new_line_beginning_before_index = before.lastIndexOf("\n");
        } else {
            separating_new_line_before = false;
            // The beginning of the entire text acts as a new line.
            closest_new_line_beginning_before_index = -1;
        }
        let separating_new_line_after = false;
        let closest_new_line_char_after_index;
        if (after.includes("\n")) {
            separating_new_line_after = true;
            closest_new_line_char_after_index =
                after.indexOf("\n") + before.length + selected_text.length;
        } else {
            separating_new_line_after = false;
            // The end of the entire text acts as a new line.
            closest_new_line_char_after_index = text.length;
        }
        // selected_lines neither includes the `\n` character that marks its
        // beginning (which exists if there are before_lines) nor the one
        // that marks its end (which exists if there are after_lines).
        const selected_lines = text.slice(
            closest_new_line_beginning_before_index + 1,
            closest_new_line_char_after_index,
        );
        // before_lines excludes the `\n` character that separates it from selected_lines.
        const before_lines = text.slice(0, Math.max(0, closest_new_line_beginning_before_index));
        // after_lines excludes the `\n` character that separates it from selected_lines.
        const after_lines = text.slice(closest_new_line_char_after_index + 1);
        return {
            before_lines,
            separating_new_line_before,
            selected_lines,
            separating_new_line_after,
            after_lines,
        };
    };

    const format_list = (type: string): void => {
        let is_marked: (line: string) => boolean;
        let mark: (line: string, i: number) => string;
        let strip_marking: (line: string) => string;
        if (type === "bulleted") {
            is_marked = bulleted_numbered_list_util.is_bulleted;
            mark = (line: string) => "- " + line;
            strip_marking = bulleted_numbered_list_util.strip_bullet;
        } else {
            is_marked = bulleted_numbered_list_util.is_numbered;
            mark = (line, i) => i + 1 + ". " + line;
            strip_marking = bulleted_numbered_list_util.strip_numbering;
        }
        // We toggle complete lines even when they are partially selected (and just selecting the
        // newline character after a line counts as partial selection too).
        const sections = section_off_selected_lines();
        let {before_lines, selected_lines, after_lines} = sections;
        const {separating_new_line_before, separating_new_line_after} = sections;
        // If there is even a single unmarked line selected, we mark all.
        const should_mark = selected_lines.split("\n").some((line) => !is_marked(line));
        if (should_mark) {
            selected_lines = selected_lines
                .split("\n")
                .map((line, i) => mark(line, i))
                .join("\n");
            // We always ensure a blank line after the list, as we want
            // a clean separation between the list and the rest of the text, especially
            // when the markdown is rendered.

            // Add blank line between list and rest of text if not already present.
            if (after_lines.length > 0 && after_lines.at(0) !== "\n") {
                after_lines = "\n" + after_lines;
            }
        } else {
            // Unmark all marked lines by removing the marking syntax characters.
            selected_lines = selected_lines
                .split("\n")
                .map((line) => strip_marking(line))
                .join("\n");
        }
        // Restore the separating newlines that were removed by section_off_selected_lines.
        if (separating_new_line_before) {
            before_lines += "\n";
        }
        if (separating_new_line_after) {
            after_lines = "\n" + after_lines;
        }
        text = before_lines + selected_lines + after_lines;
        insert_and_scroll_into_view(text, $textarea, true);
        // If no text was selected, that is, marking was added to the line with the
        // cursor, nothing will be selected and the cursor will remain as it was.
        if (selected_text === "") {
            field.setSelectionRange(
                before_lines.length + selected_lines.length,
                before_lines.length + selected_lines.length,
            );
        } else {
            field.setSelectionRange(
                before_lines.length,
                before_lines.length + selected_lines.length,
            );
        }
    };

    const format = (syntax_start: string, syntax_end = syntax_start): boolean => {
        let linebreak_start = "";
        let linebreak_end = "";
        if (syntax_start.startsWith("\n")) {
            linebreak_start = "\n";
        }
        if (syntax_end.endsWith("\n")) {
            linebreak_end = "\n";
        }
        if (is_selection_formatted(syntax_start, syntax_end)) {
            text =
                text.slice(0, range.start - syntax_start.length) +
                linebreak_start +
                text.slice(range.start, range.end) +
                linebreak_end +
                text.slice(range.end + syntax_end.length);
            insert_and_scroll_into_view(text, $textarea, true);
            field.setSelectionRange(
                range.start - syntax_start.length,
                range.end - syntax_start.length,
            );
            return false;
        } else if (is_inner_text_formatted(syntax_start, syntax_end)) {
            // Remove syntax inside the selection, if present.
            text =
                text.slice(0, range.start) +
                linebreak_start +
                text.slice(range.start + syntax_start.length, range.end - syntax_end.length) +
                linebreak_end +
                text.slice(range.end);
            insert_and_scroll_into_view(text, $textarea, true);
            field.setSelectionRange(
                range.start,
                range.end - syntax_start.length - syntax_end.length,
            );
            return false;
        }

        // Otherwise, we don't have syntax within or around, so we add it.
        wrapFieldSelection(field, syntax_start, syntax_end);
        return true;
    };

    const format_spoiler = (): void => {
        const spoiler_syntax_start = "```spoiler \n";
        let spoiler_syntax_start_without_break = "```spoiler ";
        let spoiler_syntax_end = "\n```";

        // For when the entire spoiler block (with no header) is selected.
        if (is_inner_text_formatted(spoiler_syntax_start, spoiler_syntax_end)) {
            text =
                text.slice(0, range.start) +
                text.slice(
                    range.start + spoiler_syntax_start.length,
                    range.end - spoiler_syntax_end.length,
                ) +
                text.slice(range.end);
            if (text.startsWith("\n")) {
                text = text.slice(1);
            }
            insert_and_scroll_into_view(text, $textarea, true);
            field.setSelectionRange(
                range.start,
                range.end - spoiler_syntax_start.length - spoiler_syntax_end.length,
            );
            return;
        }

        // For when the entire spoiler block (with a header) is selected.
        if (is_inner_text_formatted(spoiler_syntax_start_without_break, spoiler_syntax_end)) {
            text =
                text.slice(0, range.start) +
                text.slice(
                    range.start + spoiler_syntax_start_without_break.length,
                    range.end - spoiler_syntax_end.length,
                ) +
                text.slice(range.end);
            if (text.startsWith("\n")) {
                text = text.slice(1);
            }
            insert_and_scroll_into_view(text, $textarea, true);
            field.setSelectionRange(
                range.start,
                range.end - spoiler_syntax_start_without_break.length - spoiler_syntax_end.length,
            );
            return;
        }

        // For when the text (including the header) inside a spoiler block is selected.
        if (is_selection_formatted(spoiler_syntax_start_without_break, spoiler_syntax_end)) {
            text =
                text.slice(0, range.start - spoiler_syntax_start_without_break.length) +
                selected_text +
                text.slice(range.end + spoiler_syntax_end.length);
            insert_and_scroll_into_view(text, $textarea, true);
            field.setSelectionRange(
                range.start - spoiler_syntax_start_without_break.length,
                range.end - spoiler_syntax_start_without_break.length,
            );
            return;
        }

        // For when only the text inside a spoiler block (without a header) is selected.
        if (is_selection_formatted(spoiler_syntax_start, spoiler_syntax_end)) {
            text =
                text.slice(0, range.start - spoiler_syntax_start.length) +
                selected_text +
                text.slice(range.end + spoiler_syntax_end.length);
            insert_and_scroll_into_view(text, $textarea, true);
            field.setSelectionRange(
                range.start - spoiler_syntax_start.length,
                range.end - spoiler_syntax_start.length,
            );
            return;
        }

        const is_inner_content_selected = (): boolean =>
            range.start >= spoiler_syntax_start.length &&
            text.length - range.end >= spoiler_syntax_end.length &&
            text.slice(range.end, range.end + spoiler_syntax_end.length) === spoiler_syntax_end &&
            text[range.start - 1] === "\n" &&
            text.lastIndexOf(spoiler_syntax_start_without_break, range.start - 1) ===
                text.lastIndexOf("\n", range.start - 2) + 1;

        // For when only the text inside a spoiler block (with a header) is selected.
        if (is_inner_content_selected()) {
            const new_selection_start = text.lastIndexOf(
                spoiler_syntax_start_without_break,
                range.start,
            );
            text =
                text.slice(0, new_selection_start) +
                text.slice(
                    new_selection_start + spoiler_syntax_start_without_break.length,
                    range.start,
                ) +
                selected_text +
                text.slice(range.end + spoiler_syntax_end.length);
            insert_and_scroll_into_view(text, $textarea, true);
            field.setSelectionRange(
                new_selection_start,
                range.end - spoiler_syntax_start_without_break.length,
            );
            return;
        }

        const is_header_selected = (): boolean =>
            range.start >= spoiler_syntax_start_without_break.length &&
            text.slice(range.start - spoiler_syntax_start_without_break.length, range.start) ===
                spoiler_syntax_start_without_break &&
            text.length - range.end >= spoiler_syntax_end.length &&
            text[range.end] === "\n";

        // For when only the header of a spoiler block  is selected.
        if (is_header_selected()) {
            const header = range.text;
            const new_range_end = text.indexOf(spoiler_syntax_end, range.start);
            const new_range_start = header ? range.start : range.start + 1;
            text =
                text.slice(0, range.start - spoiler_syntax_start_without_break.length) +
                text.slice(new_range_start, new_range_end) +
                text.slice(new_range_end + spoiler_syntax_end.length);
            insert_and_scroll_into_view(text, $textarea, true);
            field.setSelectionRange(
                new_range_start - spoiler_syntax_start_without_break.length - (header ? 0 : 1),
                new_range_end - spoiler_syntax_start_without_break.length - (header ? 0 : 1),
            );
            return;
        }

        if (range.start > 0 && text[range.start - 1] !== "\n") {
            spoiler_syntax_start_without_break = "\n" + spoiler_syntax_start_without_break;
        }
        if (range.end < text.length && text[range.end] !== "\n") {
            spoiler_syntax_end = spoiler_syntax_end + "\n";
        }

        const spoiler_syntax_start_with_header = spoiler_syntax_start_without_break + "Header\n";

        // Otherwise, we don't have spoiler syntax, so we add it.
        wrapFieldSelection(field, spoiler_syntax_start_with_header, spoiler_syntax_end);

        field.setSelectionRange(
            range.start + spoiler_syntax_start_without_break.length,
            range.start + spoiler_syntax_start_with_header.length - 1,
        );
    };

    // Links have to be formatted differently because formatting is not only
    // at the beginning and end of the text, but also in the middle
    // Therefore more checks are necessary if selected text is already formatted
    const format_link = (): void => {
        const link_syntax_start = "[";
        const link_syntax_end = "](url)";

        const space_between_description_and_url = (descr: string, url: string): string => {
            if (descr === "" || url === "" || url === "url") {
                return "";
            }
            return " ";
        };

        const url_to_retain = (url: string): string => {
            if (url === "" || url === "url") {
                return "";
            }
            return url;
        };

        // Captures:
        // [<description>](<url>)
        // with just <url> selected
        const is_selection_url = (): boolean =>
            range.start >= "[](".length &&
            text.length - range.end >= ")".length &&
            text.slice(range.start - 2, range.start) === "](" &&
            text[range.end] === ")" &&
            text.lastIndexOf("[", range.start - 3) < text.lastIndexOf("]", range.start - 2);

        if (is_selection_url()) {
            const beginning = text.lastIndexOf("[", range.start);
            const description = text.slice(beginning + 1, range.start - 2);
            const url = url_to_retain(selected_text);
            text =
                text.slice(0, beginning) +
                description +
                space_between_description_and_url(description, url) +
                url +
                text.slice(range.end + 1);
            insert_and_scroll_into_view(text, $textarea, true);
            field.setSelectionRange(
                range.start - 3 + space_between_description_and_url(description, url).length,
                range.start -
                    3 +
                    space_between_description_and_url(description, url).length +
                    url.length,
            );
            return;
        }

        // Captures:
        // [<description>](<url>)
        // with just <description> selected
        const is_selection_description_of_link = (): boolean =>
            range.start >= "[".length &&
            text.length - range.end >= "]()".length &&
            text.slice(range.start - 1, range.start) === "[" &&
            text.slice(range.end, range.end + 2) === "](" &&
            text.includes(")", range.end + 2) &&
            (text.includes("(", range.end + 2)
                ? text.indexOf(")", range.end + 2) < text.indexOf("(", range.end + 2)
                : true);

        if (is_selection_description_of_link()) {
            let url = text.slice(range.end + 2, text.indexOf(")", range.end));
            url = url_to_retain(url);
            text =
                text.slice(0, range.start - 1) +
                selected_text +
                space_between_description_and_url(selected_text, url) +
                url +
                text.slice(text.indexOf(")", range.end) + 1);
            insert_and_scroll_into_view(text, $textarea, true);
            field.setSelectionRange(range.start - 1, range.end - 1);
            return;
        }

        // Captures:
        // [<description>](<url>)
        // with [<description>](<url>) selected
        const is_selection_link = (): boolean =>
            range.length >= "[]()".length &&
            text[range.start] === "[" &&
            text[range.end - 1] === ")" &&
            text.slice(range.start + 1, range.end - 1).includes("](");

        if (is_selection_link()) {
            const i = selected_text.indexOf("](", 1);
            const description = selected_text.slice(1, i);
            let url = selected_text.slice(i + "](".length, -1);
            url = url_to_retain(url);
            text =
                text.slice(0, range.start) +
                description +
                space_between_description_and_url(description, url) +
                url +
                text.slice(range.end);
            insert_and_scroll_into_view(text, $textarea, true);
            field.setSelectionRange(
                range.start,
                range.start +
                    description.length +
                    space_between_description_and_url(description, url).length +
                    url.length,
            );
            return;
        }

        // Otherwise, we don't have link syntax, so we add it.
        wrapFieldSelection(field, link_syntax_start, link_syntax_end);

        // Highlight the new `url` part of the syntax.
        // If <text> marks the selected region, we're mapping:
        // <text> => [text](<url>).
        const new_start = range.end + "[](".length;
        const new_end = new_start + "url".length;
        field.setSelectionRange(new_start, new_end);
    };

    switch (type) {
        case "bold":
            // Ctrl + B: Toggle bold syntax on selection.
            format(bold_syntax);
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

                if (is_selection_formatted(bold_syntax)) {
                    // If text has bold_syntax around it.
                    if (
                        range.start > bold_syntax.length &&
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
                insert_and_scroll_into_view(text, $textarea, true);
                field.setSelectionRange(
                    range.start - italic_syntax.length,
                    range.end - italic_syntax.length,
                );
                break;
            } else if (
                selected_text.length > italic_syntax.length * 2 &&
                // If the selected text contains italic syntax
                selected_text.startsWith(italic_syntax) &&
                selected_text.endsWith(italic_syntax)
            ) {
                if (is_inner_text_formatted(bold_syntax)) {
                    if (
                        selected_text.length > bold_and_italic_syntax.length * 2 &&
                        selected_text.startsWith(bold_and_italic_syntax) &&
                        selected_text.endsWith(bold_and_italic_syntax)
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
                insert_and_scroll_into_view(text, $textarea, true);
                field.setSelectionRange(range.start, range.end - italic_syntax.length * 2);
                break;
            }

            wrapFieldSelection(field, italic_syntax);
            break;
        case "bulleted":
        case "numbered":
            format_list(type);
            break;
        case "strikethrough": {
            const strikethrough_syntax = "~~";
            format(strikethrough_syntax);
            break;
        }
        case "code": {
            const inline_code_syntax = "`";
            let block_code_syntax_start = "```\n";
            let block_code_syntax_end = "\n```";
            // If there is no text selected or the selected text is either multiline or
            // already using multiline code syntax, we use multiline code syntax.
            if (
                selected_text === "" ||
                selected_text.includes("\n") ||
                is_selection_formatted(block_code_syntax_start, block_code_syntax_end)
            ) {
                // Add newlines before and after, if not already present.
                if (range.start > 0 && text[range.start - 1] !== "\n") {
                    block_code_syntax_start = "\n" + block_code_syntax_start;
                }
                if (range.end < text.length && text[range.end] !== "\n") {
                    block_code_syntax_end = block_code_syntax_end + "\n";
                }
                const added_fence = format(block_code_syntax_start, block_code_syntax_end);
                if (added_fence) {
                    const cursor_after_opening_fence =
                        range.start + block_code_syntax_start.length - 1;
                    field.setSelectionRange(cursor_after_opening_fence, cursor_after_opening_fence);
                    set_code_formatting_button_triggered(true);
                    // Trigger typeahead lookup with a click.
                    field.click();
                }
            } else {
                format(inline_code_syntax);
            }
            break;
        }
        case "link": {
            // Ctrl + L: Insert a link to selected text
            format_link();
            break;
        }
        case "linked": {
            // From a paste event with a URL as inserted content
            wrapFieldSelection(field, "[", `](${inserted_content})`);
            // Put the cursor at the end of the selection range
            // and all wrapped material
            $textarea.caret(range.end + `[](${inserted_content})`.length);
            break;
        }
        case "quote": {
            let quote_syntax_start = "```quote\n";
            let quote_syntax_end = "\n```";
            // Add newlines before and after, if not already present.
            if (range.start > 0 && text[range.start - 1] !== "\n") {
                quote_syntax_start = "\n" + quote_syntax_start;
            }
            if (range.end < text.length && text[range.end] !== "\n") {
                quote_syntax_end = quote_syntax_end + "\n";
            }
            format(quote_syntax_start, quote_syntax_end);
            break;
        }
        case "spoiler":
            format_spoiler();
            break;
        case "latex": {
            const inline_latex_syntax = "$$";
            let block_latex_syntax_start = "```math\n";
            let block_latex_syntax_end = "\n```";
            // If there is no text selected or the selected text is either multiline or
            // already using multiline math syntax, we use multiline math syntax.
            if (
                selected_text === "" ||
                selected_text.includes("\n") ||
                is_selection_formatted(block_latex_syntax_start, block_latex_syntax_end)
            ) {
                // Add newlines before and after, if not already present.
                if (range.start > 0 && text[range.start - 1] !== "\n") {
                    block_latex_syntax_start = "\n" + block_latex_syntax_start;
                }
                if (range.end < text.length && text[range.end] !== "\n") {
                    block_latex_syntax_end = block_latex_syntax_end + "\n";
                }
                format(block_latex_syntax_start, block_latex_syntax_end);
            } else {
                format(inline_latex_syntax);
            }
            break;
        }
    }
};

export function rewire_format_text(value: typeof format_text): void {
    format_text = value;
}

/* TODO: This functions don't belong in this module, as they have
 * nothing to do with the compose textarea. */
export function hide_compose_spinner(): void {
    compose_spinner_visible = false;
    $(".compose-submit-button .loader").hide();
    $(".compose-submit-button .zulip-icon-send").show();
    $(".compose-submit-button").removeClass("compose-button-disabled");
}

export function show_compose_spinner(): void {
    compose_spinner_visible = true;
    // Always use white spinner.
    loading.show_button_spinner($(".compose-submit-button .loader"), true);
    $(".compose-submit-button .zulip-icon-send").hide();
    $(".compose-submit-button").addClass("compose-button-disabled");
}

export function render_and_show_preview(
    $preview_container: JQuery,
    $preview_spinner: JQuery,
    $preview_content_box: JQuery,
    content: string,
): void {
    const preview_render_count = compose_state.get_preview_render_count() + 1;
    compose_state.set_preview_render_count(preview_render_count);

    function show_preview(rendered_content: string, raw_content?: string): void {
        // content is passed to check for status messages ("/me ...")
        // and will be undefined in case of errors
        let rendered_preview_html;
        if (raw_content !== undefined && markdown.is_status_message(raw_content)) {
            // Handle previews of /me messages
            rendered_preview_html =
                "<p><strong>" +
                _.escape(current_user.full_name) +
                "</strong>" +
                rendered_content.slice("<p>/me".length);
        } else {
            rendered_preview_html = rendered_content;
        }

        $preview_content_box.html(postprocess_content(rendered_preview_html));
        rendered_markdown.update_elements($preview_content_box);
    }

    if (content.length === 0) {
        show_preview($t_html({defaultMessage: "Nothing to preview"}));
    } else {
        if (markdown.contains_backend_only_syntax(content)) {
            const $spinner = $preview_spinner.expectOne();
            loading.make_indicator($spinner);
        } else {
            // For messages that don't appear to contain syntax that
            // is only supported by our backend Markdown processor, we
            // render using the frontend Markdown processor (but still
            // render server-side to ensure the preview is accurate;
            // if the `markdown.contains_backend_only_syntax` logic is
            // wrong, users will see a brief flicker of the locally
            // echoed frontend rendering before receiving the
            // authoritative backend rendering from the server).
            markdown.render(content);
        }
        void channel.post({
            url: "/json/messages/render",
            data: {content},
            success(response_data) {
                if (
                    preview_render_count !== compose_state.get_preview_render_count() ||
                    !$preview_container.hasClass("preview_mode")
                ) {
                    // The user is no longer in preview mode or the compose
                    // input has already been updated with new raw Markdown
                    // since this rendering request was sent off to the server, so
                    // there's nothing to do.
                    return;
                }
                const data = message_render_response_schema.parse(response_data);
                if (markdown.contains_backend_only_syntax(content)) {
                    loading.destroy_indicator($preview_spinner);
                }
                show_preview(data.rendered, content);
            },
            error() {
                if (markdown.contains_backend_only_syntax(content)) {
                    loading.destroy_indicator($preview_spinner);
                }
                show_preview($t_html({defaultMessage: "Failed to generate preview"}));
            },
        });
    }
}
