import $ from "jquery";

// Interface to maintain compatibility with existing code
export interface DatePickerInstance {
    isOpen: boolean;
    close(): void;
    destroy(): void;
}

export let flatpickr_instance: DatePickerInstance | null = null;

export function is_open(): boolean {
    return Boolean(flatpickr_instance?.isOpen);
}

// Convert Date object to datetime-local format (YYYY-MM-DDTHH:mm)
function to_datetime_local(date: Date): string {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    const hours = String(date.getHours()).padStart(2, "0");
    const minutes = String(date.getMinutes()).padStart(2, "0");
    return `${year}-${month}-${day}T${hours}:${minutes}`;
}

// Convert datetime-local value to ISO string
function from_datetime_local(value: string): string {
    return new Date(value).toISOString();
}

export function show_flatpickr(
    element: HTMLElement,
    callback: (time: string) => void,
    default_timestamp: Date | string | number,
    _options: Record<string, unknown> = {},
): DatePickerInstance {
    // Create native datetime-local input
    const $input = $<HTMLInputElement>("<input>")
        .attr("type", "datetime-local")
        .attr("id", "native_timestamp_picker")
        .css({
            position: "absolute",
            zIndex: 1000,
        });

    // Set default value
    let default_date: Date;
    if (default_timestamp instanceof Date) {
        default_date = default_timestamp;
    } else if (typeof default_timestamp === "string") {
        default_date = new Date(default_timestamp);
    } else if (typeof default_timestamp === "number") {
        default_date = new Date(default_timestamp);
    } else {
        default_date = new Date();
    }

    $input.val(to_datetime_local(default_date));

    // Position the input near the trigger element
    const $element = $(element);
    const offset = $element.offset();
    if (offset) {
        $input.css({
            top: offset.top + $element.outerHeight()!,
            left: offset.left,
        });
    }

    // Add to body
    $("body").append($input);

    // Handle change event
    const handle_change = (): void => {
        const value = $input.val();
        if (typeof value === "string" && value) {
            const iso_time = from_datetime_local(value);
            callback(iso_time);
            instance.close();
        }
    };

    $input.on("change", handle_change);

    // Handle keyboard events
    $input.on("keydown", (e: JQuery.KeyDownEvent) => {
        if (e.key === "Escape") {
            instance.close();
            e.preventDefault();
            e.stopPropagation();
        } else if (e.key === "Enter") {
            handle_change();
            e.preventDefault();
            e.stopPropagation();
        } else {
            // Stop propagation to prevent hotkeys from firing
            e.stopPropagation();
        }
    });

    // Handle blur event (when user clicks outside)
    $input.on("blur", () => {
        // Small delay to allow change event to fire first
        setTimeout(() => {
            instance.close();
        }, 200);
    });

    const instance: DatePickerInstance = {
        isOpen: true,
        close() {
            this.isOpen = false;
            $input.off();
            $input.remove();
            flatpickr_instance = null;
        },
        destroy() {
            this.close();
        },
    };

    flatpickr_instance = instance;

    // Focus and open the picker
    $input.trigger("focus");
    // Trigger the native picker to open (works in most browsers)
    $input[0]?.showPicker?.();

    return instance;
}

export function close_all(): void {
    if (flatpickr_instance) {
        flatpickr_instance.close();
    }
}
