"use strict";

const {strict: assert} = require("assert");

const {mock_esm, set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

const channel_settings_ui = mock_esm("../../static/js/channel_settings_ui");
const stream_data = zrequire("stream_data");
const stream_settings_ui = zrequire("stream_settings_ui");

run_test("channel_name_input_width", ({override, override_rewire}) => {
    // Set up test environment
    const $input = $("<input>").addClass("modal_text_input");
    const $container = $("<div>").append($input);
    $("body").append($container);

    // Test initial width
    const initial_width = $input.width();
    assert.ok(initial_width > 0, "Input should have initial width");

    // Test width with short text
    $input.val("short name");
    $input.trigger("input");
    const short_width = $input.width();
    assert.ok(short_width >= initial_width, "Short name should maintain minimum width");

    // Test width with long text
    const long_name = "a".repeat(100); // Create a very long channel name
    $input.val(long_name);
    $input.trigger("input");
    const long_width = $input.width();
    assert.ok(long_width > short_width, "Long name should expand input width");

    // Test width with empty input
    $input.val("");
    $input.trigger("input");
    const empty_width = $input.width();
    assert.ok(empty_width >= initial_width, "Empty input should maintain minimum width");

    // Clean up
    $container.remove();
}); 