"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");

const upload_widget = mock_esm("../src/upload_widget");
const settings_emoji = zrequire("settings_emoji");

run_test("add_custom_emoji_post_render", () => {
    let build_widget_stub = false;
    upload_widget.build_widget = (
        get_file_input,
        file_name_field,
        input_error,
        clear_button,
        upload_button,
    ) => {
        assert.deepEqual(get_file_input(), $("#emoji_file_input"));
        assert.deepEqual(file_name_field, $("#emoji-file-name"));
        assert.deepEqual(input_error, $("#emoji_file_input_error"));
        assert.deepEqual(clear_button, $("#emoji_image_clear_button"));
        assert.deepEqual(upload_button, $("#emoji_upload_button"));
        build_widget_stub = true;
    };
    settings_emoji.add_custom_emoji_post_render();
    assert.ok(build_widget_stub);
});
