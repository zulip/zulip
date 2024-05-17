import {formatISO} from "date-fns";
import flatpickr from "flatpickr";
import confirmDatePlugin from "flatpickr/dist/plugins/confirmDate/confirmDate";
import $ from "jquery";
import assert from "minimalistic-assert";

import {$t} from "./i18n";
import {user_settings} from "./user_settings";

export let flatpickr_instance: flatpickr.Instance;

export function is_open(): boolean {
    return Boolean(flatpickr_instance?.isOpen);
}

function is_numeric_key(key: string): boolean {
    return ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"].includes(key);
}

export function show_flatpickr(
    element: HTMLElement,
    callback: (time: string) => void,
    default_timestamp: flatpickr.Options.DateOption,
    options: flatpickr.Options.Options = {},
): flatpickr.Instance {
    const $flatpickr_input = $<HTMLInputElement>("<input>").attr("id", "#timestamp_flatpickr");

    flatpickr_instance = flatpickr($flatpickr_input[0], {
        mode: "single",
        enableTime: true,
        clickOpens: false,
        defaultDate: default_timestamp,
        plugins: [
            confirmDatePlugin({
                showAlways: true,
                confirmText: $t({defaultMessage: "Confirm"}),
                confirmIcon: "",
            }),
        ],
        positionElement: element,
        dateFormat: "Z",
        formatDate: (date) => formatISO(date),
        disableMobile: true,
        time_24hr: user_settings.twenty_four_hour_time,
        minuteIncrement: 1,
        onKeyDown(_selectedDates, _dateStr, instance, event: KeyboardEvent) {
            // See also the keydown handler below.
            //
            // TODO: Add a clear explanation of exactly how key
            // interactions are dispatched; it seems that keyboard
            // logic from this function, the built-in flatpickr
            // onKeyDown function, and the below keydown handler are
            // used, but it's not at all clear in what order they are
            // called, or what the overall control flow is.
            if (event.key === "Tab") {
                // Ensure that tab/shift_tab navigation work to
                // navigate between the elements in flatpickr itself
                // and the confirmation button at the bottom of the
                // popover.
                const elems = [
                    instance.selectedDateElem,
                    instance.hourElement,
                    instance.minuteElement,
                    ...(user_settings.twenty_four_hour_time ? [] : [instance.amPM]),
                    $(".flatpickr-confirm")[0],
                ];
                assert(event.target instanceof HTMLElement);
                const i = elems.indexOf(event.target);
                const n = elems.length;
                const remain = (i + (event.shiftKey ? -1 : 1)) % n;
                const target = elems[Math.floor(remain >= 0 ? remain : remain + n)];
                event.preventDefault();
                event.stopPropagation();
                assert(target !== undefined);
                target.focus();
            } else {
                // Prevent keypresses from propagating to our general hotkey.js
                // logic. Without this, `Up` will navigate both in the
                // flatpickr instance and in the message feed behind
                // it.
                event.stopPropagation();
            }
        },
        ...options,
    });

    const $container = $(flatpickr_instance.calendarContainer);

    $container.on("keydown", (e) => {
        // Main keyboard UI implementation.

        if (is_numeric_key(e.key)) {
            // Let users type numeric values
            return true;
        }

        if (e.key === "Backspace" || e.key === "Delete") {
            // Let backspace or delete be handled normally
            return true;
        }

        if (e.key === "Enter") {
            if (e.target.classList[0] === "flatpickr-day") {
                // use flatpickr's built-in behavior to choose the selected day.
                return true;
            }
            $container.find(".flatpickr-confirm").trigger("click");
        }

        if (e.key === "Escape") {
            flatpickr_instance.close();
            flatpickr_instance.destroy();
        }

        if (e.key === "Tab") {
            // Use flatpickr's built-in navigation between elements.
            return true;
        }

        if (["ArrowLeft", "ArrowUp", "ArrowRight", "ArrowDown"].includes(e.key)) {
            // use flatpickr's built-in navigation of the date grid.
            return true;
        }

        e.stopPropagation();
        e.preventDefault();

        return true;
    });

    $container.on("click", ".flatpickr-confirm", () => {
        const time = $flatpickr_input.val();
        assert(typeof time === "string");
        callback(time);
        flatpickr_instance.close();
        flatpickr_instance.destroy();
    });
    flatpickr_instance.open();
    assert(flatpickr_instance.selectedDateElem !== undefined);
    flatpickr_instance.selectedDateElem.focus();

    return flatpickr_instance;
}

export function close_all(): void {
    $(".flatpickr-calendar").removeClass("open");
}
