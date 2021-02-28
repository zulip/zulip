"use strict";

const {strict: assert} = require("assert");

const rewiremock = require("rewiremock/node");

const {zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

const upload_widget = {__esModule: true};
rewiremock("../../static/js/upload_widget").with(upload_widget);
rewiremock.enable();
const settings_emoji = zrequire("settings_emoji");

run_test("build_emoji_upload_widget", () => {
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
    settings_emoji.build_emoji_upload_widget();
    assert(build_widget_stub);
});
rewiremock.disable();
