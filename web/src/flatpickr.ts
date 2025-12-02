import {formatISO, parseISO} from "date-fns";
import $ from "jquery";
import assert from "minimalistic-assert";

import {$t} from "./i18n.ts";
import {user_settings} from "./user_settings.ts";

export let native_picker_instance: {
    element: HTMLInputElement;
    container: HTMLDivElement;
    isOpen: boolean;
} | undefined;

export function is_open(): boolean {
    return Boolean(native_picker_instance?.isOpen);
}

function format_datetime_for_input(date: Date): string {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    const hours = String(date.getHours()).padStart(2, "0");
    const minutes = String(date.getMinutes()).padStart(2, "0");
    return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function create_native_picker_html(default_timestamp: Date | string): string {
    const date = typeof default_timestamp === "string" ? parseISO(default_timestamp) : default_timestamp;
    const formatted_value = format_datetime_for_input(date);
    
    return `
        <div class="native-datetime-picker">
            <input type="datetime-local" 
                   class="native-datetime-input" 
                   value="${formatted_value}"
                   step="60">
            <div class="native-datetime-actions">
                <button type="button" class="native-datetime-confirm">${$t({defaultMessage: "Confirm"})}</button>
            </div>
        </div>
    `;
}

export function show_flatpickr(
    element: HTMLElement,
    callback: (time: string) => void,
    default_timestamp: Date | string,
    options: {position?: string; ignoredFocusElements?: HTMLElement[]} = {},
): typeof native_picker_instance {
    const $container = $(create_native_picker_html(default_timestamp));
    const container_element = $container[0];
    assert(container_element instanceof HTMLDivElement);
    
    const $input = $container.find<HTMLInputElement>(".native-datetime-input");
    const input_element = $input[0];
    assert(input_element instanceof HTMLInputElement);

    native_picker_instance = {
        element: input_element,
        container: container_element,
        isOpen: true,
    };

    $("body").append($container);

    const position_picker = (): void => {
        const trigger_rect = element.getBoundingClientRect();
        const picker_height = container_element.offsetHeight;
        const picker_width = container_element.offsetWidth;
        const viewport_height = window.innerHeight;
        const viewport_width = window.innerWidth;

        let top = trigger_rect.bottom + 5;
        let left = trigger_rect.left;

        if (top + picker_height > viewport_height) {
            top = trigger_rect.top - picker_height - 5;
        }

        if (left + picker_width > viewport_width) {
            left = viewport_width - picker_width - 10;
        }

        if (left < 10) {
            left = 10;
        }

        container_element.style.position = "fixed";
        container_element.style.top = `${top}px`;
        container_element.style.left = `${left}px`;
        container_element.style.zIndex = "105";
    };

    position_picker();

    const handle_confirm = (): void => {
        const value = input_element.value;
        if (value) {
            const date = new Date(value);
            const iso_string = formatISO(date);
            callback(iso_string);
        }
        close_picker();
    };

    const close_picker = (): void => {
        if (native_picker_instance) {
            native_picker_instance.isOpen = false;
            $container.remove();
            native_picker_instance = undefined;
        }
    };

    $container.on("click", ".native-datetime-confirm", (e) => {
        e.preventDefault();
        e.stopPropagation();
        handle_confirm();
    });

    $container.on("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            e.stopPropagation();
            handle_confirm();
        }

        if (e.key === "Escape") {
            e.preventDefault();
            e.stopPropagation();
            close_picker();
        }

        if (e.key === "Tab") {
            const $confirm_button = $container.find(".native-datetime-confirm");
            if (e.target === input_element && !e.shiftKey) {
                e.preventDefault();
                $confirm_button.trigger("focus");
            } else if (e.target === $confirm_button[0] && e.shiftKey) {
                e.preventDefault();
                input_element.focus();
            }
        }

        e.stopPropagation();
    });

    $(document).on("click.native-picker", (e) => {
        if (!$(e.target).closest(".native-datetime-picker").length && 
            e.target !== element &&
            !options.ignoredFocusElements?.includes(e.target as HTMLElement)) {
            close_picker();
        }
    });

    input_element.focus();

    return native_picker_instance;
}

export function close_all(): void {
    if (native_picker_instance) {
        native_picker_instance.isOpen = false;
        $(native_picker_instance.container).remove();
        native_picker_instance = undefined;
    }
    $(document).off("click.native-picker");
}
