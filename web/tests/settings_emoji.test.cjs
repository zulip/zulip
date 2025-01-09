"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {SideEffect} = require("./lib/side_effect.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const upload_widget = mock_esm("../src/upload_widget");
const settings_emoji = zrequire("settings_emoji");

run_test("add_custom_emoji_post_render", () => {
    const side_effect = new SideEffect("build_widget gets called");

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
        side_effect.has_happened();
    };

    side_effect.should_happen_during(() => {
        settings_emoji.add_custom_emoji_post_render();
    });
});
