"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

// Mock flatpickr
mock_esm("flatpickr", {
    default(element, options) {
        element.fp_options = options;
        element.last_set_date = undefined;
        element.trigger_change = undefined;
        element.was_cleared = false;
        return {
            element,
            config: {
                dateFormat: "Y-m-d",
            },
        };
    },
});

const custom_profile_fields_ui = zrequire("custom_profile_fields_ui");

// Test case for initialize_custom_date_type_fields focusing on invalid keyboard input
run_test("initialize_custom_date_type_fields_keyboard_validation", () => {
    const $container = $.create("#test_container");
    const $date_picker = $.create(".datepicker");
    const $label = $.create(".settings-field-label");
    const $remove_date = $.create(".remove_date");

    $date_picker.set = (key, value) => {
        $date_picker[`_${key}`] = value;
    };
    $date_picker.get = (key) => $date_picker[`_${key}`];

    $date_picker.set("last_set_date", undefined);
    $date_picker.set("trigger_change", undefined);
    $date_picker.set("was_cleared", false);

    $date_picker.set_last_set_date = (date) => {
        $date_picker.set("last_set_date", date);
    };

    $container.set_find_results(".custom_user_field .datepicker", $date_picker);
    $container.set_find_results(".custom_user_field label.settings-field-label", $label);
    $container.set_find_results(".custom_user_field input.datepicker", $date_picker);
    $container.set_find_results(".custom_user_field .remove_date", $remove_date);

    $date_picker.length = 1;
    $label.length = 1;
    $remove_date.length = 1;

    $date_picker.each = (callback) => {
        callback(0, $date_picker);
        return $date_picker;
    };

    custom_profile_fields_ui.initialize_custom_date_type_fields("#test_container");

    // Create mock flatpickr instance for testing onClose
    const mockInstance = {
        parseDate() {
            return null;
        },
        setDate(date, triggerChange) {
            $date_picker.set_last_set_date(date);
            $date_picker.set("trigger_change", triggerChange);
        },
        formatDate(date) {
            return date.toISOString().split("T")[0]; // Simple YYYY-MM-DD formatting
        },
        config: {dateFormat: "Y-m-d"},
    };
    // Simulate onReady behavior
    const validDate = new Date("2023-05-15");
    $date_picker.data("lastValidDate", validDate);

    // Simulate onChange with a valid date
    $date_picker.fp_options.onChange([validDate], "2023-05-15", mockInstance);

    // Verify onChange handler stored the valid date
    assert.strictEqual(
        $date_picker.data("lastValidDate"),
        validDate,
        "onChange should save the last valid date",
    );
    // Simulate onClose after typing an invalid date string
    $date_picker.fp_options.onClose([], "bananas", mockInstance);

    // Verify last valid date was restored
    assert.strictEqual(
        $date_picker.get("last_set_date"),
        validDate,
        "Should restore the last valid date when invalid input is entered",
    );
    assert.strictEqual(
        $date_picker.get("trigger_change"),
        true,
        "Should trigger change event after restoring valid date",
    );
});
