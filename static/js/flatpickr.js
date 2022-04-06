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
    const $flatpickr_input = $("<input>", {id: "#timestamp_flatpickr"});

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
        onKeyDown: (selectedDates, dateStr, instance, event) => {
            if (is_numeric_key(event.key)) {
                // Don't attempt to get_keydown_hotkey for numeric inputs
                // as it would return undefined.
                return;
            }

            const hotkey = get_keydown_hotkey(event);

            if (["tab", "shift_tab"].includes(hotkey.name)) {
                const elems = [
                    instance.selectedDateElem,
                    instance.hourElement,
                    instance.minuteElement,
                    instance.amPM,
                    $(".flatpickr-confirm")[0],
                ];
                const i = elems.indexOf(event.target);
                const n = elems.length;
                const remain = (i + (event.shiftKey ? -1 : 1)) % n;
                const target = elems[Math.floor(remain >= 0 ? remain : remain + n)];
                event.preventDefault();
                event.stopPropagation();
                target.focus();
            }

            event.stopPropagation();
        },
        ...options,
    });

    const $container = $($(instance.innerContainer).parent());

    $container.on("keydown", (e) => {
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
                return true; // use flatpickr default implementation
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
            return true; // use flatpickr default implementation
        }

        if (["right_arrow", "up_arrow", "left_arrow", "down_arrow"].includes(hotkey.name)) {
            return true; // use flatpickr default implementation
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
