"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const upload_widget = mock_esm("../src/upload_widget");
const settings_emoji = zrequire("settings_emoji");

run_test("add_custom_emoji_post_render", () => {
    let build_direct_upload_widget_stub = false;
    upload_widget.build_direct_upload_widget = (
        get_file_input,
        input_error,
        upload_button,
        upload_function,
        max_file_size,
        property_name,
    ) => {
        assert.deepEqual(get_file_input(), $("#emoji_file_input"));
        assert.deepEqual(input_error, $("#emoji_file_input_error"));
        assert.deepEqual(upload_button, $("#emoji_upload_button"));
        assert.equal(typeof upload_function, "function");
        assert.equal(max_file_size, 5);
        assert.equal(property_name, "custom_emoji");
        build_direct_upload_widget_stub = true;
    };
    settings_emoji.add_custom_emoji_post_render();
    assert.ok(build_direct_upload_widget_stub);
});
