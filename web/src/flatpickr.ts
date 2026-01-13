import {formatISO, parseISO} from "date-fns";
import $ from "jquery";

import {$t} from "./i18n.ts";
import {user_settings} from "./user_settings.ts";

// This module now uses native browser date/time picker instead of flatpickr library.
// The API is kept similar for compatibility with existing code.

let picker_open = false;
let $current_picker: JQuery | null = null;

export function is_open(): boolean {
    return picker_open;
}

// For compatibility with code that references flatpickr_instance
export const flatpickr_instance: {close: () => void} | undefined = {
    close(): void {
        close_all();
    },
};

function format_datetime_local(date: Date): string {
    // Format date for datetime-local input (YYYY-MM-DDTHH:mm)
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    const hours = String(date.getHours()).padStart(2, "0");
    const minutes = String(date.getMinutes()).padStart(2, "0");
    return `${year}-${month}-${day}T${hours}:${minutes}`;
}

export function show_flatpickr(
    element: HTMLElement,
    callback: (time: string) => void,
    default_timestamp: Date | string | number,
    options: {
        minDate?: Date;
        onClose?: (selectedDates: Date[], dateStr: string, instance: unknown) => void;
        position?: string;
        ignoredFocusElements?: HTMLElement[];
    } = {},
): {close: () => void} {
    // Close any existing picker first
    close_all();

    // Convert default_timestamp to Date if needed
    let default_date: Date;
    if (default_timestamp instanceof Date) {
        default_date = default_timestamp;
    } else if (typeof default_timestamp === "string") {
        default_date = parseISO(default_timestamp);
    } else {
        default_date = new Date(default_timestamp);
    }

    // Create the native picker container
    const $picker_container = $("<div>").addClass("native-datetime-picker-container");

    // Create datetime-local input
    const $datetime_input = $<HTMLInputElement>("<input>")
        .attr("type", "datetime-local")
        .addClass("native-datetime-picker-input")
        .val(format_datetime_local(default_date));

    // Set min date if specified
    if (options.minDate) {
        $datetime_input.attr("min", format_datetime_local(options.minDate));
    }

    // Handle 24-hour time format preference (note: browser may not fully respect this)
    if (user_settings.twenty_four_hour_time) {
        // Most browsers will use system locale, but we set step for minute precision
        $datetime_input.attr("step", "60"); // 1 minute increments
    }

    // Create confirm button
    const $confirm_button = $("<button>")
        .addClass("native-datetime-confirm-btn")
        .text($t({defaultMessage: "Confirm"}));

    $picker_container.append($datetime_input, $confirm_button);
    $("body").append($picker_container);

    // Position the picker near the element
    const element_rect = element.getBoundingClientRect();
    const picker_top = element_rect.bottom + window.scrollY + 5;
    const picker_left = element_rect.left + window.scrollX;

    $picker_container.css({
        top: `${picker_top}px`,
        left: `${picker_left}px`,
    });

    // Adjust position if picker goes off-screen
    const picker_rect = $picker_container[0]!.getBoundingClientRect();
    if (picker_rect.right > window.innerWidth) {
        $picker_container.css("left", `${window.innerWidth - picker_rect.width - 10}px`);
    }
    if (picker_rect.bottom > window.innerHeight) {
        $picker_container.css(
            "top",
            `${element_rect.top + window.scrollY - picker_rect.height - 5}px`,
        );
    }

    picker_open = true;
    $current_picker = $picker_container;

    // Focus the input and try to open the native picker
    $datetime_input.trigger("focus");

    // Handle confirm button click
    $confirm_button.on("click", () => {
        const value = $datetime_input.val();
        if (value) {
            const selected_date = new Date(value);
            const iso_string = formatISO(selected_date);
            callback(iso_string);
        }
        close_all();
    });

    // Handle Enter key
    $datetime_input.on("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            $confirm_button.trigger("click");
        } else if (e.key === "Escape") {
            e.preventDefault();
            close_all();
        }
        // Stop propagation to prevent hotkeys from triggering
        e.stopPropagation();
    });

    // Handle click outside to close
    const close_on_outside_click = (e: MouseEvent): void => {
        const target = e.target;
        if (!(target instanceof Element)) {
            return;
        }
        const $target = $(target);
        if (
            $target.closest(".native-datetime-picker-container").length === 0 &&
            !options.ignoredFocusElements?.some((el) => el === target || el.contains(target))
        ) {
            // Call onClose callback if provided
            if (options.onClose) {
                const value = $datetime_input.val();
                const selected_dates = value ? [new Date(value)] : [];
                options.onClose(selected_dates, value ?? "", null);
            }
            close_all();
        }
    };

    // Delay adding the click listener to prevent immediate close
    setTimeout(() => {
        document.addEventListener("click", close_on_outside_click);
        $picker_container.data("close_handler", close_on_outside_click);
    }, 0);

    return {
        close: close_all,
    };
}

export function close_all(): void {
    if ($current_picker) {
        // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
        const close_handler = $current_picker.data("close_handler") as
            | ((e: MouseEvent) => void)
            | undefined;
        if (close_handler) {
            document.removeEventListener("click", close_handler);
        }
        $current_picker.remove();
        $current_picker = null;
    }
    picker_open = false;
}
