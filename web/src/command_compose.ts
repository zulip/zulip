/**
 * Command compose mode - structured input for bot slash commands.
 *
 * When a user selects a bot command from the typeahead, this module manages
 * a Discord-style inline input mode where the command and its arguments
 * flow naturally within the text.
 */

import $ from "jquery";

import * as bot_command_store from "./bot_command_store.ts";

export type CommandOption = {
    name: string;
    type: string;
    description?: string;
    required?: boolean;
    choices?: Array<{name: string; value: string}>;
};

export type CommandFieldState = {
    option: CommandOption;
    value: string;
};

// Focus can be on: command name, a field, or trailing text
type FocusPosition =
    | {type: "command"}
    | {type: "field"; index: number}
    | {type: "trailing"};

type CommandModeState = {
    active: boolean;
    command: bot_command_store.BotCommand | null;
    command_text: string; // The editable command name (without /)
    fields: CommandFieldState[];
    focus: FocusPosition;
    trailing_text: string; // Text after the command invocation
    // Track which required fields have been visited but left empty
    visited_empty_required: Set<number>;
};

// Global state for command mode
let state: CommandModeState = {
    active: false,
    command: null,
    command_text: "",
    fields: [],
    focus: {type: "command"},
    trailing_text: "",
    visited_empty_required: new Set(),
};

// Event callbacks
let on_exit_callback: (() => void) | null = null;
let on_send_callback: ((command_name: string, args: Record<string, string>) => void) | null = null;

// Sending state - prevents edits while request is in flight
let is_sending = false;

/**
 * Check if command mode is currently active.
 */
export function is_active(): boolean {
    return state.active;
}

/**
 * Check if a command is currently being sent.
 */
export function get_is_sending(): boolean {
    return is_sending;
}

/**
 * Set the sending state. When true, inputs are disabled.
 */
export function set_sending(sending: boolean): void {
    is_sending = sending;
    if (state.active) {
        update_sending_state();
    }
}

/**
 * Update the UI to reflect the sending state.
 */
function update_sending_state(): void {
    const $container = $(`#${COMMAND_UI_CONTAINER_ID}`);
    if (is_sending) {
        $container.addClass("sending");
        $container.find("input, select").prop("disabled", true);
    } else {
        $container.removeClass("sending");
        $container.find("input, select").prop("disabled", false);
    }
}

/**
 * Get the current command being composed.
 */
export function get_current_command(): bot_command_store.BotCommand | null {
    return state.command;
}

/**
 * Get all field states.
 */
export function get_fields(): CommandFieldState[] {
    return state.fields;
}

/**
 * Get the current focus position.
 */
export function get_focus(): FocusPosition {
    return state.focus;
}

/**
 * Get the currently focused field index, or -1 if not focused on a field.
 */
export function get_current_field_index(): number {
    if (state.focus.type === "field") {
        return state.focus.index;
    }
    return -1;
}

/**
 * Get the currently focused field.
 */
export function get_current_field(): CommandFieldState | null {
    if (state.focus.type === "field") {
        const index = state.focus.index;
        if (index >= 0 && index < state.fields.length) {
            return state.fields[index] ?? null;
        }
    }
    return null;
}

/**
 * Get the trailing text (text after the command invocation).
 */
export function get_trailing_text(): string {
    return state.trailing_text;
}

/**
 * Get the command text (editable command name without /).
 */
export function get_command_text(): string {
    return state.command_text;
}

/**
 * Enter command mode for a specific command.
 */
export function enter(command: bot_command_store.BotCommand): void {
    state = {
        active: true,
        command,
        command_text: command.name,
        fields: command.options.map((option) => ({
            option,
            value: "",
        })),
        focus: command.options.length > 0 ? {type: "field", index: 0} : {type: "trailing"},
        trailing_text: "",
        visited_empty_required: new Set(),
    };

    render_command_ui();
}

/**
 * Exit command mode, returning to normal compose.
 */
export function exit(): void {
    state = {
        active: false,
        command: null,
        command_text: "",
        fields: [],
        focus: {type: "command"},
        trailing_text: "",
        visited_empty_required: new Set(),
    };

    is_sending = false;
    hide_command_ui();

    if (on_exit_callback) {
        on_exit_callback();
    }
}

/**
 * Set the value for the current field.
 * Note: This only updates the internal state, not the UI.
 * The UI input already shows the value as the user types.
 */
export function set_current_field_value(value: string): void {
    const field = get_current_field();
    if (field) {
        field.value = value;
        // Don't re-render here - the input already shows the value
        // Re-rendering on every keystroke causes performance issues
        // and can cause cursor position problems
    }
}

/**
 * Set the command text (name without /).
 */
export function set_command_text(value: string): void {
    state.command_text = value;
}

/**
 * Set the trailing text.
 */
export function set_trailing_text(value: string): void {
    state.trailing_text = value;
}

/**
 * Check if a field is required and empty, and track it if so.
 * Called when leaving a field.
 */
function check_required_field_on_leave(index: number): void {
    const field = state.fields[index];
    if (field && field.option.required && !field.value.trim()) {
        state.visited_empty_required.add(index);
    } else if (field) {
        // Field has been filled, remove from visited empty set
        state.visited_empty_required.delete(index);
    }
}

/**
 * Move focus to the next position.
 * Returns true if moved, false if already at the end.
 */
export function advance_focus(): boolean {
    if (!state.active) {
        return false;
    }

    // Track if leaving an empty required field
    if (state.focus.type === "field") {
        check_required_field_on_leave(state.focus.index);
    }

    if (state.focus.type === "command") {
        // Move from command to first field or trailing
        if (state.fields.length > 0) {
            state.focus = {type: "field", index: 0};
        } else {
            state.focus = {type: "trailing"};
        }
        focus_current_position();
        return true;
    } else if (state.focus.type === "field") {
        const index = state.focus.index;
        if (index < state.fields.length - 1) {
            // Move to next field
            state.focus = {type: "field", index: index + 1};
            focus_current_position();
            return true;
        } else {
            // Move to trailing text
            state.focus = {type: "trailing"};
            focus_current_position();
            return true;
        }
    }
    // Already at trailing - nowhere to go
    return false;
}

/**
 * Move focus to the previous position.
 * Returns true if moved, false if at the beginning.
 */
export function retreat_focus(): boolean {
    if (!state.active) {
        return false;
    }

    // Track if leaving an empty required field
    if (state.focus.type === "field") {
        check_required_field_on_leave(state.focus.index);
    }

    if (state.focus.type === "trailing") {
        // Move from trailing to last field or command
        if (state.fields.length > 0) {
            state.focus = {type: "field", index: state.fields.length - 1};
        } else {
            state.focus = {type: "command"};
        }
        focus_current_position();
        return true;
    } else if (state.focus.type === "field") {
        const index = state.focus.index;
        if (index > 0) {
            // Move to previous field
            state.focus = {type: "field", index: index - 1};
            focus_current_position();
            return true;
        } else {
            // Move to command
            state.focus = {type: "command"};
            focus_current_position();
            return true;
        }
    }
    // Already at command - nowhere to go
    return false;
}

/**
 * Navigate to a specific field by index.
 */
export function go_to_field(index: number): void {
    if (!state.active || index < 0 || index >= state.fields.length) {
        return;
    }

    state.focus = {type: "field", index};
    focus_current_position();
}

/**
 * Navigate to command.
 */
export function go_to_command(): void {
    if (!state.active) {
        return;
    }
    state.focus = {type: "command"};
    focus_current_position();
}

/**
 * Navigate to trailing text.
 */
export function go_to_trailing(): void {
    if (!state.active) {
        return;
    }
    state.focus = {type: "trailing"};
    focus_current_position();
}

// Legacy compatibility - advance_field now just advances focus
export function advance_field(): boolean {
    return advance_focus();
}

// Legacy compatibility - retreat_field now just retreats focus
export function retreat_field(): boolean {
    return retreat_focus();
}

/**
 * Try to send the command. Returns true if sent, false if validation fails.
 */
export function try_send(): boolean {
    if (!state.active || !state.command) {
        return false;
    }

    // Validate command name is not empty
    if (!state.command_text.trim()) {
        go_to_command();
        show_validation_error(-1, "Command name is required");
        return false;
    }

    // Check required fields
    for (const field of state.fields) {
        if (field.option.required && !field.value.trim()) {
            // Focus the first empty required field
            const index = state.fields.indexOf(field);
            go_to_field(index);
            show_validation_error(index, "This field is required");
            return false;
        }
    }

    // Build arguments object - only include non-empty values
    // The API uses named parameters so order doesn't matter
    const args: Record<string, string> = {};
    for (const field of state.fields) {
        const value = field.value.trim();
        if (value) {
            args[field.option.name] = value;
        }
    }

    // Use the (possibly edited) command text
    const command_name = state.command_text.trim();

    // Exit command mode first
    exit();

    // Trigger send callback
    if (on_send_callback) {
        on_send_callback(command_name, args);
    }

    return true;
}

/**
 * Build the message content string from current state.
 */
export function build_message_content(): string {
    if (!state.command_text) {
        return state.trailing_text;
    }

    let content = `/${state.command_text}`;

    for (const field of state.fields) {
        if (field.value.trim()) {
            content += ` ${field.value.trim()}`;
        }
    }

    // Add trailing text if present
    if (state.trailing_text) {
        content += ` ${state.trailing_text}`;
    }

    return content;
}

/**
 * Register callback for when command mode is exited.
 */
export function on_exit(callback: () => void): void {
    on_exit_callback = callback;
}

/**
 * Register callback for when command is sent.
 */
export function on_send(callback: (command_name: string, args: Record<string, string>) => void): void {
    on_send_callback = callback;
}

// ============ UI Rendering ============

const COMMAND_UI_CONTAINER_ID = "command-compose-container";

/**
 * Render the command mode UI, replacing the textarea.
 */
function render_command_ui(): void {
    if (!state.command) {
        return;
    }

    // Hide the regular textarea
    const $textarea = $("#compose-textarea");
    $textarea.hide();

    // Create or get the command UI container
    let $container = $(`#${COMMAND_UI_CONTAINER_ID}`);
    if ($container.length === 0) {
        $container = $(`<div id="${COMMAND_UI_CONTAINER_ID}" class="command-compose-container"></div>`);
        $textarea.after($container);
    }

    // Build the UI
    const command_html = build_command_html();
    $container.html(command_html);
    $container.show();

    // Unbind previous events and bind fresh (avoid duplicates from re-renders)
    $container.off();
    bind_events($container);

    // Focus current position
    focus_current_position();
}

/**
 * Hide the command UI and show the textarea.
 */
function hide_command_ui(): void {
    const $container = $(`#${COMMAND_UI_CONTAINER_ID}`);
    $container.hide().empty();

    const $textarea = $("#compose-textarea");
    $textarea.show();
    $("textarea#compose-textarea").trigger("focus");
}

/**
 * Build HTML for the inline command mode UI.
 * This is a textual, Discord-like layout where command and fields flow inline.
 */
function build_command_html(): string {
    if (!state.command) {
        return "";
    }

    const is_command_focused = state.focus.type === "command";
    const is_trailing_focused = state.focus.type === "trailing";

    let html = `<div class="command-compose-inline">`;

    // Command invocation block - contains slash, command name, and fields
    html += `<span class="command-invocation-block">`;

    // Slash prefix (non-editable)
    html += `<span class="command-slash">/</span>`;

    // Command name - editable when focused
    if (is_command_focused) {
        html += `<input type="text" class="command-name-input" value="${escape_html(state.command_text)}" autocomplete="off" data-1p-ignore data-lpignore="true" data-form-type="other" spellcheck="false" />`;
    } else {
        html += `<span class="command-name-text" data-focus="command">${escape_html(state.command_text)}</span>`;
    }

    // Field inputs - inline with subtle styling
    for (let i = 0; i < state.fields.length; i++) {
        const field = state.fields[i]!;
        const is_field_focused = state.focus.type === "field" && state.focus.index === i;
        const is_required = field.option.required;
        const has_value = field.value.trim() !== "";
        const has_choices = field.option.choices && field.option.choices.length > 0;
        const is_unfilled_required = state.visited_empty_required.has(i);

        html += `<span class="command-field-inline${is_required ? " required" : ""}${has_value ? " has-value" : ""}${is_unfilled_required ? " unfilled-required" : ""}" data-field-index="${i}">`;

        if (is_field_focused) {
            const placeholder = field.option.name + (is_required ? "*" : "");

            if (has_choices) {
                // Use select for options with choices
                html += `<select class="command-field-select-inline" data-field-index="${i}">`;
                html += `<option value="" disabled ${!has_value ? "selected" : ""}>${escape_html(placeholder)}</option>`;
                for (const choice of field.option.choices!) {
                    const is_selected = field.value === choice.value;
                    html += `<option value="${escape_html(choice.value)}" ${is_selected ? "selected" : ""}>${escape_html(choice.name)}</option>`;
                }
                html += `</select>`;
            } else {
                // Use text input for options without choices
                html += `<input type="text" class="command-field-input-inline" value="${escape_html(field.value)}" placeholder="${escape_html(placeholder)}" data-field-index="${i}" autocomplete="off" data-1p-ignore data-lpignore="true" data-form-type="other" spellcheck="false" />`;
            }
        } else if (has_value) {
            // Show display name for choices, raw value otherwise
            let display_value = field.value;
            if (has_choices) {
                const choice = field.option.choices!.find((c) => c.value === field.value);
                if (choice) {
                    display_value = choice.name;
                }
            }
            html += `<span class="field-value-text" data-field-index="${i}">${escape_html(display_value)}</span>`;
        } else {
            // Show placeholder
            html += `<span class="field-placeholder" data-field-index="${i}">${escape_html(field.option.name)}${is_required ? "*" : ""}</span>`;
        }

        html += `</span>`;
    }

    html += `</span>`; // End command-invocation-block

    // Trailing text input - always present, allows typing after the command
    if (is_trailing_focused) {
        html += `<input type="text" class="command-trailing-input" value="${escape_html(state.trailing_text)}" placeholder="additional text..." autocomplete="off" data-1p-ignore data-lpignore="true" data-form-type="other" spellcheck="false" />`;
    } else if (state.trailing_text) {
        html += `<span class="command-trailing-text" data-focus="trailing">${escape_html(state.trailing_text)}</span>`;
    } else {
        // Empty trailing - subtle click target
        html += `<span class="command-trailing-placeholder" data-focus="trailing"></span>`;
    }

    html += `</div>`;

    // Description footer for current field
    const current_field = get_current_field();
    if (current_field?.option.description) {
        html += `<div class="command-field-description">${escape_html(current_field.option.description)}</div>`;
    }

    return html;
}

/**
 * Bind event handlers for all interactions.
 */
function bind_events($container: JQuery): void {
    // Click on command name text to focus it
    $container.on("click", ".command-name-text", function () {
        go_to_command();
        render_command_ui();
    });

    // Click on field placeholder/value to focus it
    $container.on("click", ".field-value-text, .field-placeholder", function () {
        const index = Number.parseInt($(this).attr("data-field-index")!, 10);
        go_to_field(index);
        render_command_ui();
    });

    // Click on trailing text/placeholder to focus it
    $container.on("click", ".command-trailing-text, .command-trailing-placeholder", function () {
        go_to_trailing();
        render_command_ui();
    });

    // Command name input events
    $container.on("input", ".command-name-input", function () {
        const value = $(this).val() as string;
        set_command_text(value);
    });

    $container.on("keydown", ".command-name-input", function (e) {
        handle_keydown(e, "command", this as HTMLInputElement);
    });

    // Field input events (text inputs)
    $container.on("input", ".command-field-input-inline", function () {
        const value = $(this).val() as string;
        set_current_field_value(value);
    });

    $container.on("keydown", ".command-field-input-inline", function (e) {
        const index = Number.parseInt($(this).attr("data-field-index")!, 10);
        handle_keydown(e, "field", this as HTMLInputElement, index);
    });

    // Field select events (dropdowns for options with choices)
    $container.on("change", ".command-field-select-inline", function () {
        const value = $(this).val() as string;
        set_current_field_value(value);
        // Auto-advance to next field after selection
        if (advance_focus()) {
            render_command_ui();
        }
    });

    $container.on("keydown", ".command-field-select-inline", function (e) {
        const index = Number.parseInt($(this).attr("data-field-index")!, 10);
        if (e.key === "Tab") {
            e.preventDefault();
            if (e.shiftKey) {
                if (!retreat_focus()) {
                    exit();
                } else {
                    render_command_ui();
                }
            } else {
                if (advance_focus()) {
                    render_command_ui();
                }
            }
        } else if (e.key === "Escape") {
            e.preventDefault();
            exit();
        } else if (e.key === "Enter") {
            e.preventDefault();
            try_send();
        } else if (e.key === "Backspace" && !$(this).val()) {
            // Backspace when no selection - go to previous field
            e.preventDefault();
            if (index === 0) {
                go_to_command();
            } else {
                state.focus = {type: "field", index: index - 1};
            }
            render_command_ui();
        }
    });

    // Trailing text input events
    $container.on("input", ".command-trailing-input", function () {
        const value = $(this).val() as string;
        set_trailing_text(value);
    });

    $container.on("keydown", ".command-trailing-input", function (e) {
        handle_keydown(e, "trailing", this as HTMLInputElement);
    });
}

/**
 * Unified keyboard event handler for all input types.
 */
function handle_keydown(
    e: JQuery.KeyDownEvent,
    position_type: "command" | "field" | "trailing",
    input: HTMLInputElement,
    field_index?: number,
): void {
    const cursor_at_start = input.selectionStart === 0 && input.selectionEnd === 0;
    const cursor_at_end = input.selectionStart === input.value.length;

    if (e.key === "Tab") {
        e.preventDefault();
        if (e.shiftKey) {
            // Shift+Tab - go backward
            if (!retreat_focus()) {
                // At command, can't go further back - exit command mode
                exit();
            } else {
                render_command_ui();
            }
        } else {
            // Tab - go forward
            if (advance_focus()) {
                render_command_ui();
            }
            // If already at trailing, Tab does nothing (stays in trailing)
        }
    } else if (e.key === "Escape") {
        e.preventDefault();
        exit();
    } else if (e.key === "Enter") {
        e.preventDefault();
        try_send();
    } else if (e.key === "Backspace" && cursor_at_start) {
        // Backspace at start of field - go to previous position
        e.preventDefault();

        if (position_type === "command") {
            // At start of command name with nothing to delete - if empty, exit
            if (input.value === "") {
                exit();
            }
            // Otherwise let the backspace happen naturally (it won't since we're at position 0)
        } else if (position_type === "field" && field_index === 0) {
            // First field - backspace into command name
            go_to_command();
            render_command_ui();
            // After re-render, we'll focus command and cursor will be at end
        } else if (position_type === "field" && field_index !== undefined && field_index > 0) {
            // Not first field - go to previous field
            state.focus = {type: "field", index: field_index - 1};
            render_command_ui();
        } else if (position_type === "trailing") {
            // Trailing - go to last field or command
            if (state.fields.length > 0) {
                state.focus = {type: "field", index: state.fields.length - 1};
            } else {
                state.focus = {type: "command"};
            }
            render_command_ui();
        }
    } else if (e.key === "ArrowLeft" && cursor_at_start) {
        // Arrow left at start - navigate backward
        e.preventDefault();
        if (retreat_focus()) {
            render_command_ui();
        }
    } else if (e.key === "ArrowRight" && cursor_at_end) {
        // Arrow right at end - navigate forward
        e.preventDefault();
        if (advance_focus()) {
            render_command_ui();
        }
    }
}

/**
 * Focus the input for the current position and place cursor at end.
 */
function focus_current_position(): void {
    let $element: JQuery<HTMLElement>;

    if (state.focus.type === "command") {
        $element = $(".command-name-input");
    } else if (state.focus.type === "field") {
        // Check for select first, then input
        $element = $(`.command-field-select-inline[data-field-index="${state.focus.index}"]`);
        if ($element.length === 0) {
            $element = $(`.command-field-input-inline[data-field-index="${state.focus.index}"]`);
        }
    } else {
        $element = $(".command-trailing-input");
    }

    if ($element.length > 0) {
        $element.trigger("focus");
        // Move cursor to end for text inputs (not applicable for selects)
        const element = $element[0];
        if (element instanceof HTMLInputElement) {
            element.selectionStart = element.selectionEnd = element.value.length;
        }
    }
}

/**
 * Show a validation error for a field or command.
 */
function show_validation_error(index: number, _message: string): void {
    let $element: JQuery;
    if (index === -1) {
        // Command name error
        $element = $(".command-name-input, .command-name-text");
    } else {
        $element = $(`.command-field-inline[data-field-index="${index}"]`);
    }
    $element.addClass("validation-error");
    setTimeout(() => {
        $element.removeClass("validation-error");
    }, 2000);
}

/**
 * Escape HTML special characters.
 */
function escape_html(text: string): string {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

/**
 * Reset state for testing.
 */
export function clear_for_testing(): void {
    state = {
        active: false,
        command: null,
        command_text: "",
        fields: [],
        focus: {type: "command"},
        trailing_text: "",
        visited_empty_required: new Set(),
    };
    on_exit_callback = null;
    on_send_callback = null;
    is_sending = false;
}
