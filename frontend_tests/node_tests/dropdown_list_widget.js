"use strict";

const {strict: assert} = require("assert");

const {$t} = require("../zjsunit/i18n");
const {mock_esm, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const blueslip = require("../zjsunit/zblueslip");
const $ = require("../zjsunit/zjquery");

const noop = () => {};
mock_esm("../../static/js/list_widget", {
    create: () => ({init: noop}),
});

const {DropdownListWidget, MultiSelectDropdownListWidget} = zrequire("dropdown_list_widget");

// For DropdownListWidget
const setup_dropdown_zjquery_data = (name) => {
    const input_group = $(".input_group");
    const reset_button = $(".dropdown_list_reset_button");
    input_group.set_find_results(".dropdown_list_reset_button:enabled", reset_button);
    $(`#${CSS.escape(name)}_widget #${CSS.escape(name)}_name`).closest = () => input_group;
    const $widget = $(`#${CSS.escape(name)}_widget #${CSS.escape(name)}_name`);
    return {reset_button, $widget};
};

run_test("basic_functions", () => {
    let updated_value;
    const opts = {
        widget_name: "my_setting",
        data: ["one", "two", "three"].map((x) => ({name: x, value: x})),
        value: "one",
        on_update: (val) => {
            updated_value = val;
        },
        default_text: $t({defaultMessage: "not set"}),
        render_text: (text) => `rendered: ${text}`,
    };

    const {reset_button, $widget} = setup_dropdown_zjquery_data(opts.widget_name);

    const widget = new DropdownListWidget(opts);

    assert.equal(widget.value(), "one");
    assert.equal(updated_value, undefined); // We haven't 'updated' the widget yet.
    assert.ok(reset_button.visible());

    widget.update("two");
    assert.equal($widget.text(), "rendered: two");
    assert.equal(widget.value(), "two");
    assert.equal(updated_value, "two");
    assert.ok(reset_button.visible());

    widget.update(null);
    assert.equal($widget.text(), "translated: not set");
    assert.equal(widget.value(), "");
    assert.equal(updated_value, null);
    assert.ok(!reset_button.visible());

    widget.update("four");
    assert.equal($widget.text(), "translated: not set");
    assert.equal(widget.value(), "four");
    assert.equal(updated_value, "four");
    assert.ok(!reset_button.visible());
});

run_test("no_default_value", () => {
    const opts = {
        widget_name: "my_setting",
        data: ["one", "two", "three"].map((x) => ({name: x, value: x})),
        default_text: $t({defaultMessage: "not set"}),
        render_text: (text) => `rendered: ${text}`,
        null_value: "null-value",
    };

    blueslip.expect(
        "warn",
        "dropdown-list-widget: Called without a default value; using null value",
    );
    setup_dropdown_zjquery_data(opts.widget_name);
    const widget = new DropdownListWidget(opts);
    assert.equal(widget.value(), "null-value");
});

// For MultiSelectDropdownListWidget
const setup_multiselect_dropdown_zjquery_data = function (name) {
    $(`#${CSS.escape(name)}_widget`)[0] = {};
    return setup_dropdown_zjquery_data(name);
};

run_test("basic MDLW functions", ({mock_template}) => {
    const opts = {
        widget_name: "my_setting",
        data: ["one", "two", "three", "four"].map((x) => ({name: x, value: x})),
        value: ["one"],
    };
    const {$widget} = setup_multiselect_dropdown_zjquery_data(opts.widget_name);

    mock_template("multiselect_dropdown_pills.hbs", true, (data, html) => {
        assert.deepEqual(data, {
            display_value: "one",
        });

        return html;
    });

    const widget = new MultiSelectDropdownListWidget(opts);

    function set_dropdown_variable(widget, value) {
        widget.data_selected = value;
    }

    assert.deepEqual(widget.value(), ["one"]);
    assert.equal($widget.text(), "one");

    set_dropdown_variable(widget, ["one", "two"]);
    widget.update(widget.data_selected);

    assert.deepEqual(widget.value(), ["one", "two"]);

    set_dropdown_variable(widget, ["one", "two", "three"]);
    widget.update(widget.data_selected);

    assert.deepEqual(widget.value(), ["one", "two", "three"]);

    set_dropdown_variable(widget, null);
    widget.update(widget.data_selected);

    assert.equal(widget.value(), null);

    set_dropdown_variable(widget, ["one"]);
    widget.update(widget.data_selected);

    assert.deepEqual(widget.value(), ["one"]);
});

run_test("MDLW no_default_value", () => {
    const opts = {
        widget_name: "my_setting",
        data: ["one", "two", "three", "four"].map((x) => ({name: x, value: x})),
        null_value: "null-value",
    };

    blueslip.expect(
        "warn",
        "dropdown-list-widget: Called without a default value; using null value",
    );

    setup_multiselect_dropdown_zjquery_data(opts.widget_name);
    const widget = new MultiSelectDropdownListWidget(opts);

    assert.equal(widget.value(), "null-value");
});

run_test("MDLW callback functions", ({mock_template}) => {
    function setup_callback_zjquery_data(name, value) {
        const element = $.create(".whatever");
        $(`#${CSS.escape(name)}_widget .dropdown-list-body`).set_find_results(
            `li[data-value = ${value}]`,
            element,
        );
    }

    let pill_removed;
    let pill_added;

    const opts = {
        widget_name: "my_setting",
        data: ["one", "two", "three", "four"].map((x) => ({name: x, value: x})),
        value: ["one"],
        on_pill_remove: (item) => {
            pill_removed = item;
        },
        on_pill_add: (item) => {
            pill_added = item;
        },
    };

    setup_multiselect_dropdown_zjquery_data(opts.widget_name);

    mock_template("multiselect_dropdown_pills.hbs", true, (data, html) => {
        assert.deepEqual(data, {
            display_value: "one",
        });

        return html;
    });
    const widget = new MultiSelectDropdownListWidget(opts);

    // Testing on_pill_remove callback.
    assert.equal(pill_removed, undefined);

    setup_callback_zjquery_data(opts.widget_name, widget.value().toString());
    widget.enable_list_item({
        text: () => widget.value().toString(),
    });

    assert.equal(pill_removed, "one");

    // Testing on_pill_add callback.
    assert.equal(pill_added, undefined);

    widget.disable_list_item(
        {
            length: 1, // Mocking the element to be a valid jquery element.
            addClass: noop,
        },
        "one",
    );

    assert.equal(pill_added, "one");
});
