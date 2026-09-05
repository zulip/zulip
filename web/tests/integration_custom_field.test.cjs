"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const integration_custom_field = zrequire("integration_custom_field");

run_test("create_item_from_custom_field_name", () => {
    function test_create_item(field_name, current_items, expected_item) {
        const item = integration_custom_field.create_item_from_custom_field_name(
            field_name,
            current_items,
        );
        assert.deepEqual(item, expected_item);
    }

    test_create_item("foo", [], {type: "custom_field", value: "foo"});
    test_create_item("  foo  ", [], {type: "custom_field", value: "foo"});
    test_create_item("", [], undefined);
    test_create_item("   ", [], undefined);
    test_create_item(
        "foo",
        [{type: "custom_field", value: "Foo"}],
        undefined,
    );
    test_create_item(
        "Bar",
        [{type: "custom_field", value: "Foo"}],
        {type: "custom_field", value: "Bar"},
    );
});

run_test("get_custom_field_name_from_item", () => {
    const item = {type: "custom_field", value: "foo"};
    assert.equal(integration_custom_field.get_custom_field_name_from_item(item), "foo");
});

run_test("add_default_custom_fields", () => {
    const appended_items = [];
    const custom_field_pill_widget = {
        appendValidatedData(item, suppress_events, skip_focus) {
            appended_items.push({item, suppress_events, skip_focus});
        },
    };

    integration_custom_field.add_default_custom_fields(custom_field_pill_widget, ["severity", "priority"]);

    assert.deepEqual(appended_items, [
        {
            item: {type: "custom_field", value: "severity"},
            suppress_events: true,
            skip_focus: true,
        },
        {
            item: {type: "custom_field", value: "priority"},
            suppress_events: true,
            skip_focus: true,
        },
    ]);
});

run_test("get_additional_custom_fields", () => {
    const widget = {
        items: () => [
            {type: "custom_field", value: "severity"},
            {type: "custom_field", value: "Priority"},
            {type: "custom_field", value: "team"},
        ],
    };

    const additional_custom_fields = integration_custom_field.get_additional_custom_fields(widget, [
        "severity",
        "priority",
    ]);

    assert.equal(additional_custom_fields, "team");
});
