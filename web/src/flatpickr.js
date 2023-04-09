import {formatISO} from "date-fns";
import ConfirmDatePlugin from "flatpickr/dist/plugins/confirmDate/confirmDate";
import $ from "jquery";

import {get_keydown_hotkey} from "./hotkey";
import {$t} from "./i18n";
import {user_settings} from "./user_settings";

function is_numeric_key(key) {
    return ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"].includes(key);
}

export function show_flatpickr(element, callback, default_timestamp, options = {}) {
    const $flatpickr_input = $("<input>").attr("id", "#timestamp_flatpickr");

    const instance = $flatpickr_input.flatpickr({
        mode: "single",
        enableTime: true,
        clickOpens: false,
        defaultDate: default_timestamp,
        plugins: [
            new ConfirmDatePlugin({
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
        onKeyDown(selectedDates, dateStr, instance, event) {
            // See also the keydown handler below.
            //
            // TODO: Add a clear explanation of exactly how key
            // interactions are dispatched; it seems that keyboard
            // logic from this function, the built-in flatpickr
            // onKeyDown function, and the below keydown handler are
            // used, but it's not at all clear in what order they are
            // called, or what the overall control flow is.
            const hotkey = get_keydown_hotkey(event);

            if (hotkey && ["tab", "shift_tab"].includes(hotkey.name)) {
                // Ensure that tab/shift_tab navigation work to
                // navigate between the elements in flatpickr itself
                // and the confirmation button at the bottom of the
                // popover.
                let elems = [
                    instance.selectedDateElem,
                    instance.hourElement,
                    instance.minuteElement,
                    instance.amPM,
                    $(".flatpickr-confirm")[0],
                    $(".shortcut-buttons-flatpickr-button")[0],
                ];
                elems = elems.filter((e) => e !== undefined);
                const i = elems.indexOf(event.target);
                const n = elems.length;
                const remain = (i + (event.shiftKey ? -1 : 1)) % n;
                const target = elems[Math.floor(remain >= 0 ? remain : remain + n)];
                event.preventDefault();
                event.stopPropagation();
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

    const $container = $(instance.innerContainer).parent();

    $container.on("keydown", (e) => {
        // Main keyboard UI implementation.

        if (is_numeric_key(e.key)) {
            // Let users type numeric values
            return true;
        }

        const hotkey = get_keydown_hotkey(e);

        if (!hotkey) {
            return false;
        }

        if (hotkey.name === "backspace" || hotkey.name === "delete") {
            // Let backspace or delete be handled normally
            return true;
        }

        if (hotkey.name === "enter") {
            if (e.target.classList[0] === "flatpickr-day") {
                // use flatpickr's built-in behavior to choose the selected day.
                return true;
            }
            $(element).toggleClass("has_popover");
            $container.find(".flatpickr-confirm").trigger("click");
        }

        if (hotkey.name === "escape") {
            $(element).toggleClass("has_popover");
            instance.close();
            instance.destroy();
        }

        if (["tab", "shift_tab"].includes(hotkey.name)) {
            // Use flatpickr's built-in navigation between elements.
            return true;
        }

        if (["right_arrow", "up_arrow", "left_arrow", "down_arrow"].includes(hotkey.name)) {
            // use flatpickr's built-in navigation of the date grid.
            return true;
        }

        e.stopPropagation();
        e.preventDefault();

        return true;
    });

    $container.on("click", ".flatpickr-confirm", () => {
        callback($flatpickr_input.val());
        instance.close();
        instance.destroy();
    });

    instance.open();
    instance.selectedDateElem.focus();

    return instance;
}
