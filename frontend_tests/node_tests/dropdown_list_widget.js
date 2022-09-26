"use strict";

const {strict: assert} = require("assert");

const {$t} = require("../zjsunit/i18n");
const {mock_esm, zrequire, set_global} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const blueslip = require("../zjsunit/zblueslip");
const $ = require("../zjsunit/zjquery");

const noop = () => {};
mock_esm("../../static/js/list_widget", {
    create: () => ({init: noop}),
});

mock_esm("tippy.js", {
    default: (arg) => {
        arg._tippy = {setContent: noop, placement: noop, destroy: noop};
        return arg._tippy;
    },
});

set_global("document", {});
const {DropdownListWidget, MultiSelectDropdownListWidget} = zrequire("dropdown_list_widget");

// For DropdownListWidget
const setup_dropdown_zjquery_data = (name) => {
    const $input_group = $(".input_group");
    const $reset_button = $(".dropdown_list_reset_button");
    $input_group.set_find_results(".dropdown_list_reset_button", $reset_button);
    $(`#${CSS.escape(name)}_widget #${CSS.escape(name)}_name`).closest = () => $input_group;
    const $widget = $(`#${CSS.escape(name)}_widget #${CSS.escape(name)}_name`);
    return {$reset_button, $widget};
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

    const {$reset_button, $widget} = setup_dropdown_zjquery_data(opts.widget_name);

    const widget = new DropdownListWidget(opts);
    widget.setup();

    assert.equal(widget.value(), "one");
    assert.equal(updated_value, undefined); // We haven't 'updated' the widget yet.
    assert.ok($reset_button.visible());

    widget.update("two");
    assert.equal($widget.text(), "rendered: two");
    assert.equal(widget.value(), "two");
    assert.equal(updated_value, "two");
    assert.ok($reset_button.visible());

    widget.update(null);
    assert.equal($widget.text(), "translated: not set");
    assert.equal(widget.value(), "");
    assert.equal(updated_value, null);
    assert.ok(!$reset_button.visible());

    widget.update("four");
    assert.equal($widget.text(), "translated: not set");
    assert.equal(widget.value(), "four");
    assert.equal(updated_value, "four");
    assert.ok(!$reset_button.visible());
});

run_test("no_default_value", () => {
    const opts = {
        widget_name: "my_setting",
        data: ["one", "two", "three"].map((x) => ({name: x, value: x})),
        default_text: $t({defaultMessage: "not set"}),
        render_text: /* istanbul ignore next */ (text) => `rendered: ${text}`,
        null_value: "null-value",
    };

    blueslip.expect(
        "warn",
        "dropdown-list-widget: Called without a default value; using null value",
    );
    setup_dropdown_zjquery_data(opts.widget_name);
    const widget = new DropdownListWidget(opts);
    widget.setup();
    assert.equal(widget.value(), "null-value");
});

// For MultiSelectDropdownListWidget
const setup_multiselect_dropdown_zjquery_data = function (name) {
    $(`#${CSS.escape(name)}_widget`)[0] = {};
    return setup_dropdown_zjquery_data(name);
};

run_test("basic MDLW functions", () => {
    let updated_value;
    const opts = {
        widget_name: "my_setting",
        data: ["one", "two", "three", "four"].map((x) => ({name: x, value: x})),
        value: ["one"],
        limit: 2,
        on_update: (val) => {
            updated_value = val;
        },
        default_text: $t({defaultMessage: "not set"}),
    };

    const {$reset_button, $widget} = setup_multiselect_dropdown_zjquery_data(opts.widget_name);
    const widget = new MultiSelectDropdownListWidget(opts);
    widget.setup();

    function set_dropdown_variables(widget, value) {
        widget.data_selected = value;
        widget.checked_items = value;
    }

    assert.deepEqual(widget.value(), ["one"]);
    assert.equal(updated_value, undefined);
    assert.equal($widget.text(), "one");
    assert.ok($reset_button.visible());

    set_dropdown_variables(widget, ["one", "two"]);
    widget.update(widget.data_selected);

    assert.equal($widget.text(), "one,two");
    assert.deepEqual(widget.value(), ["one", "two"]);
    assert.deepEqual(updated_value, ["one", "two"]);
    assert.ok($reset_button.visible());

    set_dropdown_variables(widget, ["one", "two", "three"]);
    widget.update(widget.data_selected);

    assert.equal($widget.text(), "translated: 3 selected");
    assert.deepEqual(widget.value(), ["one", "two", "three"]);
    assert.deepEqual(updated_value, ["one", "two", "three"]);
    assert.ok($reset_button.visible());

    set_dropdown_variables(widget, null);
    widget.update(widget.data_selected);

    assert.equal($widget.text(), "translated: not set");
    assert.equal(widget.value(), null);
    assert.equal(updated_value, null);
    assert.ok(!$reset_button.visible());

    set_dropdown_variables(widget, ["one"]);
    widget.update(widget.data_selected);

    assert.equal($widget.text(), "one");
    assert.deepEqual(widget.value(), ["one"]);
    assert.deepEqual(updated_value, ["one"]);
    assert.ok($reset_button.visible());
});

run_test("MDLW no_default_value", () => {
    const opts = {
        widget_name: "my_setting",
        data: ["one", "two", "three", "four"].map((x) => ({name: x, value: x})),
        limit: 2,
        null_value: "null-value",
        default_text: $t({defaultMessage: "not set"}),
    };

    blueslip.expect(
        "warn",
        "dropdown-list-widget: Called without a default value; using null value",
    );

    setup_multiselect_dropdown_zjquery_data(opts.widget_name);
    const widget = new MultiSelectDropdownListWidget(opts);
    widget.setup();

    assert.equal(widget.value(), "null-value");
});

run_test("MDLW no_limit_set", () => {
    const opts = {
        widget_name: "my_setting",
        data: ["one", "two", "three", "four"].map((x) => ({name: x, value: x})),
        value: ["one"],
        default_text: $t({defaultMessage: "not set"}),
    };

    blueslip.expect(
        "warn",
        "Multiselect dropdown-list-widget: Called without limit value; using 2 as the limit",
    );

    function set_dropdown_variables(widget, value) {
        widget.data_selected = value;
        widget.checked_items = value;
    }

    const {$widget} = setup_multiselect_dropdown_zjquery_data(opts.widget_name);
    const widget = new MultiSelectDropdownListWidget(opts);
    widget.setup();

    set_dropdown_variables(widget, ["one", "two", "three"]);
    widget.update(widget.data_selected);

    // limit is set to 2 (Default value).
    assert.equal($widget.text(), "translated: 3 selected");

    set_dropdown_variables(widget, ["one"]);
    widget.update(widget.data_selected);

    assert.equal($widget.text(), "one");
});
