"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
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

const channel = mock_esm("../src/channel", {
    post: noop,
    patch: noop,
    del: noop,
});
const loading = mock_esm("../src/loading", {
    make_indicator() {},
    destroy_indicator() {},
});

const {update_custom_profile_field} = zrequire("settings_account");

run_test("update_custom_profile_field", ({override}) => {
    const field_valid = {id: 5, value: "2024-03-25"};
    const field_invalid = {id: 5, value: "March 25, 2024"};
    const field_other = {id: 6, value: "Some value"};

    const mock_method = (options) => {
        mock_method.last_call = options;
    };

    override(channel, "post", mock_method);

    // Mock spinner element with expectOne method
    const $spinner_element = $.create(".custom-field-status");
    $spinner_element.length = 1; // Ensure length is set
    $spinner_element.fadeTo = () => {}; // Add fadeTo stub

    // Override loading module with stubs that do nothing
    override(loading, "make_indicator", () => {});

    // Valid date case
    update_custom_profile_field(field_valid, channel.post);

    // Parse the stringified data to compare for post requests
    const parsedPostData = JSON.parse(mock_method.last_call.data.data);

    assert.deepStrictEqual(parsedPostData, [field_valid], "Valid date should be sent correctly");

    // Verify that the method was actually called for valid date
    assert.ok(mock_method.last_call !== undefined, "Method should be called for a valid date");

    // Verify the correct URL is used
    assert.strictEqual(
        mock_method.last_call.url,
        "/json/users/me/profile_data",
        "Correct URL should be used for profile data update",
    );

    // Invalid date case (should not send request)
    mock_method.last_call = undefined;
    update_custom_profile_field(field_invalid, channel.post);
    assert.strictEqual(
        mock_method.last_call,
        undefined,
        "Invalid date should prevent request from being sent",
    );

    // Other field (non-date) should be sent normally
    update_custom_profile_field(field_other, channel.post);
    const parsedOtherData = JSON.parse(mock_method.last_call.data.data);
    assert.deepStrictEqual(
        parsedOtherData,
        [field_other],
        "Non-date field should be sent correctly",
    );
});
