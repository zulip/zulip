"use strict";

const {strict: assert} = require("assert");

const {zrequire, mock_esm} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

const user_pill = mock_esm("../../static/js/user_pill", {
    items: () => {},
});
const custom_profile_fields_ui = zrequire("custom_profile_fields_ui");

const fields_user_pills = new Map();
fields_user_pills.set(3, {});

function setup_custom_fields() {
    const $favorite_food_field = $.create("favorite_food_field");
    $favorite_food_field.val("katsu");
    $favorite_food_field.attr("data-field-id", "1");

    const $phone_number_field = $.create("phone_number_field");
    $phone_number_field.val("123-456-7890");
    $phone_number_field.attr("data-field-id", "2");

    const $bad_input_field = $.create("duplicate_flatpickr_field");
    $bad_input_field.addClass("form-control");

    return [$phone_number_field, $favorite_food_field, $bad_input_field];
}

function setup_closest_stubs(fields) {
    for (const $field of fields) {
        $field.closest = (selector) => {
            assert.strictEqual(selector, ".custom_user_field");
            return $field;
        };
    }
}

function compareFunction(a, b) {
    return a.id - b.id;
}

run_test("get_human_profile_data", () => {
    const fields = setup_custom_fields();
    setup_closest_stubs(fields);

    $("#edit-user-form .custom_user_field_value").each = (fn) => {
        for (const $elem of fields) {
            fn.call($elem);
        }
    };

    const mentor_ids = [2, 3];
    user_pill.get_user_ids = () => mentor_ids;

    const profile_data = custom_profile_fields_ui.get_human_profile_data(fields_user_pills);

    assert.deepStrictEqual(
        profile_data.sort(compareFunction),
        [
            {id: 1, value: "katsu"},
            {id: 2, value: "123-456-7890"},
            {id: 3, value: [2, 3]},
        ].sort(compareFunction),
    );
});
