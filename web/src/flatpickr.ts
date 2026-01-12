import {formatISO} from "date-fns";
import $ from "jquery";

import {$t} from "./i18n.ts";

// Keep a reference to the current picker state
let current_picker_state:
    | {
          container: JQuery<HTMLElement>;
          input: JQuery<HTMLInputElement>;
          callback: (time: string) => void;
      }
    | undefined;

// For backwards compatibility - some code might reference this
export const flatpickr_instance = undefined;

export function is_open(): boolean {
    return current_picker_state !== undefined;
}

export function show_flatpickr(
    element: HTMLElement,
    callback: (time: string) => void,
    default_timestamp: Date | string | number,
    options?: {
        minDate?: Date | string | number;
        position?: string;
        ignoredFocusElements?: unknown[];
    },
): {close: () => void; destroy: () => void} {
    // Provide default empty object if options is undefined
    const opts = options ?? {};

    // Close any existing picker first
    if (current_picker_state) {
        close_picker();
    }

    // Convert default_timestamp to Date object
    const default_date = new Date(default_timestamp);
    
    // Convert minDate if provided
    const min_date = opts.minDate ? new Date(opts.minDate) : undefined;

    // Format date for datetime-local input (YYYY-MM-DDTHH:MM)
    const format_for_input = (date: Date): string => {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, "0");
        const day = String(date.getDate()).padStart(2, "0");
        const hours = String(date.getHours()).padStart(2, "0");
        const minutes = String(date.getMinutes()).padStart(2, "0");
        return `${year}-${month}-${day}T${hours}:${minutes}`;
    };

    // Create the native datetime picker
    const $input = $<HTMLInputElement>("<input>")
        .attr("type", "datetime-local")
        .attr("id", "native-datetime-picker")
        .val(format_for_input(default_date))
        .css({
            width: "100%",
            padding: "8px",
            "font-size": "14px",
            border: "1px solid hsl(0deg 0% 80%)",
            "border-radius": "4px",
            "box-sizing": "border-box",
        });

    if (min_date) {
        $input.attr("min", format_for_input(min_date));
    }

    // Create container for the picker UI
    const $container = $("<div>")
        .attr("id", "native-datetime-container")
        .css({
            position: "absolute",
            "z-index": "1000",  // Changed from 105 to 1000
            background: "hsl(0deg 0% 100%)",
            padding: "16px",
            "border-radius": "4px",
            "box-shadow": "0 2px 8px rgba(0, 0, 0, 0.15)",
            border: "1px solid hsl(0deg 0% 87%)",
            "min-width": "280px",
        });

    // Create confirm button
    const $confirm_button = $("<button>")
        .addClass("native-datetime-confirm")
        .text($t({defaultMessage: "Confirm"}))
        .css({
            "margin-top": "10px",
            padding: "8px 16px",
            background: "hsl(213deg 100% 50%)",
            color: "white",
            border: "none",
            "border-radius": "4px",
            cursor: "pointer",
            width: "100%",
            "font-weight": "600",
        });

    // Add input and button to container
    $container.append($input).append($confirm_button);
    $("body").append($container);

    // Position the container near the trigger element
    const position_picker = (): void => {
        const element_rect = element.getBoundingClientRect();
        const container_height = $container.outerHeight() ?? 0;
        const container_width = $container.outerWidth() ?? 0;
    
        // Position near the schedule button (clock icon) in the compose box
        // Default to center-right of the screen if element position is invalid
        let top = element_rect.bottom + 5;
        let left = element_rect.left;

        // If element has no valid position (0,0), center the picker
        if (element_rect.top === 0 && element_rect.left === 0) {
            top = (window.innerHeight - container_height) / 2;
            left = (window.innerWidth - container_width) / 2;
        } else {
            // Adjust if it goes off screen
            if (top + container_height > window.innerHeight) {
                top = element_rect.top - container_height - 5;
            }
        
            if (left + container_width > window.innerWidth) {
                left = window.innerWidth - container_width - 10;
            }
        
            // Ensure minimum margins
            if (left < 10) {
                left = 10;
            }
            if (top < 10) {
                top = 10;
            }
        }

        $container.css({
            top: `${top}px`,
            left: `${left}px`,
        });
    };

    // Position after a short delay to allow popover to close
    setTimeout(() => {
        position_picker();
    }, 10);

    position_picker();

    // Handle confirm button click
    $confirm_button.on("click", () => {
        const value = $input.val();
        if (typeof value === "string" && value) {
            const selected_date = new Date(value);
            
            // Check if date is valid and meets min requirement
            if (min_date && selected_date < min_date) {
                // Could show error here, for now just return
                return;
            }
            
            const iso_time = formatISO(selected_date);
            callback(iso_time);
            close_picker();
        }
    });

    // Handle Enter key on input
    $input.on("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            $confirm_button.trigger("click");
        } else if (e.key === "Escape") {
            e.preventDefault();
            close_picker();
        }
    });

    // Handle Escape key globally
    $(document).on("keydown.native-datetime", (e) => {
        if (e.key === "Escape") {
            close_picker();
        }
    });

    // Handle click outside to close
    $(document).on("click.native-datetime", (e) => {
        const target = e.target;
        if (!(target instanceof Node)) {
            return;
        }
        if (
            $(target).closest("#native-datetime-container").length === 0 &&
            !element.contains(target)
        ) {
            close_picker();
    }
    });

    // Store current state
    current_picker_state = {
        container: $container,
        input: $input,
        callback,
    };

    // Focus the input
    setTimeout(() => {
        $input.trigger("focus");
    }, 0);

    // Return instance-like object
    return {
        close: close_picker,
        destroy: close_picker,
    };
}

function close_picker(): void {
    if (current_picker_state) {
        current_picker_state.container.remove();
        $(document).off("keydown.native-datetime");
        $(document).off("click.native-datetime");
        current_picker_state = undefined;
    }
}

export function close_all(): void {
    close_picker();
}