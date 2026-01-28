import {formatISO} from "date-fns";
import $ from "jquery";

import {$t} from "./i18n.ts";

// Keep a reference to the current picker state
let current_picker_state:
    | {
          container: JQuery;
          input: JQuery<HTMLInputElement>;
          callback: (time: string) => void;
      }
    | undefined;

// For backwards compatibility
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
    const opts = options ?? {};

    // Close any existing picker first
    if (current_picker_state) {
        close_picker();
    }

    const default_date = new Date(default_timestamp);
    const min_date = opts.minDate ? new Date(opts.minDate) : undefined;

    // Format date for datetime-local input (YYYY-MM-DDTHH:mm)
    const format_datetime_local = (date: Date): string => {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, "0");
        const day = String(date.getDate()).padStart(2, "0");
        const hours = String(date.getHours()).padStart(2, "0");
        const minutes = String(date.getMinutes()).padStart(2, "0");
        return `${year}-${month}-${day}T${hours}:${minutes}`;
    };

    // Create the native datetime-local picker
    const $datetime_input = $<HTMLInputElement>("<input>")
        .attr("type", "datetime-local")
        .attr("id", "native-datetime-picker")
        .val(format_datetime_local(default_date))
        .css({
            width: "100%",
            padding: "10px",
            "font-size": "14px",
            border: "1px solid var(--color-border, hsl(0deg 0% 80%))",
            "border-radius": "4px",
            "box-sizing": "border-box",
            "margin-bottom": "12px",
        });

    if (min_date) {
        $datetime_input.attr("min", format_datetime_local(min_date));
    }

    // Create container
    const $container = $("<div>").attr("id", "native-datetime-container").css({
        position: "absolute",
        "z-index": "1000",
        background: "var(--color-background-modal, hsl(0deg 0% 100%))",
        padding: "16px",
        "border-radius": "6px",
        "box-shadow": "0 4px 20px rgba(0, 0, 0, 0.15)",
        border: "1px solid var(--color-border, hsl(0deg 0% 87%))",
        "min-width": "300px",
    });

    // Create confirm button
    const $confirm_button = $("<button>")
        .attr("type", "button")
        .text($t({defaultMessage: "Confirm"}))
        .css({
            padding: "10px 16px",
            background: "hsl(213deg 100% 50%)",
            color: "hsl(0deg 0% 100%)",
            border: "none",
            "border-radius": "4px",
            cursor: "pointer",
            width: "100%",
            "font-weight": "600",
            "font-size": "14px",
        })
        .on("mouseenter", function () {
            $(this).css("background", "hsl(213deg 100% 45%)");
        })
        .on("mouseleave", function () {
            $(this).css("background", "hsl(213deg 100% 50%)");
        });

    $container.append($datetime_input).append($confirm_button);
    $("body").append($container);

    // Position the container
    const position_picker = (): void => {
        const element_rect = element.getBoundingClientRect();
        const container_height = $container.outerHeight() ?? 0;
        const container_width = $container.outerWidth() ?? 0;

        let top = element_rect.bottom + 5;
        let left = element_rect.left;

        // Center if element has no position
        if (element_rect.top === 0 && element_rect.left === 0) {
            top = (window.innerHeight - container_height) / 2;
            left = (window.innerWidth - container_width) / 2;
        } else {
            // Position below element, adjust if off-screen
            if (top + container_height > window.innerHeight) {
                top = element_rect.top - container_height - 5;
            }
            if (left + container_width > window.innerWidth) {
                left = window.innerWidth - container_width - 10;
            }
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

    setTimeout(() => {
        position_picker();
    }, 10);

    // Open the native picker immediately
    setTimeout(() => {
        const input_element = $datetime_input[0];
        if (input_element instanceof HTMLInputElement && input_element.showPicker) {
            try {
                input_element.showPicker();
            } catch {
                // showPicker() may fail in some contexts, just continue
            }
        }
    }, 100);

    // Handle confirm button click
    $confirm_button.on("click", () => {
        const datetime_value = $datetime_input.val();

        // Reset any error styling
        $datetime_input.css("border-color", "var(--color-border, hsl(0deg 0% 80%))");

        if (typeof datetime_value !== "string" || !datetime_value) {
            $datetime_input.css("border-color", "hsl(3deg 90% 63%)");
            return;
        }

        const selected_date = new Date(datetime_value);

        // Validate date
        if (Number.isNaN(selected_date.getTime())) {
            $datetime_input.css("border-color", "hsl(3deg 90% 63%)");
            return;
        }

        // Check minimum date
        if (min_date && selected_date < min_date) {
            $datetime_input.css("border-color", "hsl(3deg 90% 63%)");
            return;
        }

        const iso_time = formatISO(selected_date);
        callback(iso_time);
        close_picker();
    });

    // Handle Enter key
    $datetime_input.on("keydown", (e) => {
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
        input: $datetime_input,
        callback,
    };

    // Focus the input
    setTimeout(() => {
        $datetime_input.trigger("focus");
    }, 0);

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
