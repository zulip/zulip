"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const blueslip = require("../zjsunit/zblueslip");
const $ = require("../zjsunit/zjquery");

const input_pill = zrequire("input_pill");
const pill_typeahead = zrequire("pill_typeahead");
const noop = function () {};

run_test("set_up", () => {
    // Test set_up without any type
    let input_pill_typeahead_called = false;
    const fake_input = $.create(".input");
    fake_input.typeahead = (config) => {
        assert.equal(config.items, 5);
        assert.ok(config.fixed);
        assert.ok(config.dropup);
        assert.ok(config.stopAdvance);

        // Working of functions that are part of config
        // is tested separately based on the widgets that
        // try to use it. Here we just check if config
        // passed to the typeahead is in the right format.
        assert.equal(typeof config.source, "function");
        assert.equal(typeof config.highlighter, "function");
        assert.equal(typeof config.matcher, "function");
        assert.equal(typeof config.sorter, "function");
        assert.equal(typeof config.updater, "function");

        // input_pill_typeahead_called is set true if
        // no exception occurs in pill_typeahead.set_up.
        input_pill_typeahead_called = true;
    };

    const container = $.create(".pill-container");
    container.find = () => fake_input;

    const pill_widget = input_pill.create({
        container,
        create_item_from_text: noop,
        get_text_from_item: noop,
    });

    // call set_up with only user type in opts.
    pill_typeahead.set_up(fake_input, pill_widget, {user: true});
    assert.ok(input_pill_typeahead_called);

    // call set_up with only stream type in opts.
    input_pill_typeahead_called = false;
    pill_typeahead.set_up(fake_input, pill_widget, {stream: true});
    assert.ok(input_pill_typeahead_called);

    // call set_up with only user_group type in opts.
    input_pill_typeahead_called = false;
    pill_typeahead.set_up(fake_input, pill_widget, {user_group: true});
    assert.ok(input_pill_typeahead_called);

    // call set_up with combination two types in opts.
    input_pill_typeahead_called = false;
    pill_typeahead.set_up(fake_input, pill_widget, {user_group: true, stream: true});
    assert.ok(input_pill_typeahead_called);

    // call set_up with all three types in opts.
    input_pill_typeahead_called = false;
    pill_typeahead.set_up(fake_input, pill_widget, {user_group: true, stream: true, user: true});
    assert.ok(input_pill_typeahead_called);

    // call set_up without specifying type in opts.
    input_pill_typeahead_called = false;
    blueslip.expect("error", "Unspecified possible item types");
    pill_typeahead.set_up(fake_input, pill_widget, {});
    assert.ok(!input_pill_typeahead_called);
});
