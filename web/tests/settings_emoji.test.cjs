"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const upload_widget = mock_esm("../src/upload_widget");
const settings_emoji = zrequire("settings_emoji");

run_test("add_custom_emoji_post_render", () => {
    let build_widget_stub = false;
    upload_widget.build_widget = (
        get_file_input,
        $file_name_field,
        $input_error,
        $clear_button,
        $upload_button,
        _$preview_text,
        _$preview_image,
        _max_file_upload_size,
        allow_multiple,
    ) => {
        assert.equal(get_file_input()[0], $("#emoji_file_input")[0]);
        assert.equal($file_name_field[0], $("#emoji-file-name")[0]);
        assert.equal($input_error[0], $("#emoji_file_input_error")[0]);
        assert.equal($clear_button[0], $("#emoji_image_clear_button")[0]);
        assert.equal($upload_button[0], $("#emoji_upload_button")[0]);
        assert.equal(allow_multiple, true);
        build_widget_stub = true;
    };
    settings_emoji.add_custom_emoji_post_render();
    assert.ok(build_widget_stub);
});

run_test("auto_fill_emoji_name_from_filename", () => {
    upload_widget.build_widget = () => {};
    settings_emoji.add_custom_emoji_post_render();

    const $emoji_file_input = $("#emoji_file_input");
    const $emoji_name = $("#emoji_name");

    $emoji_file_input[0].files = [{name: "party-parrot.png"}];
    $emoji_name.val("");

    $emoji_file_input.trigger("input");

    assert.equal($emoji_name.val(), "party-parrot");
});

run_test("derive_name_from_filename", () => {
    assert.equal(settings_emoji.derive_name_from_filename("party-parrot.png"), "party-parrot");
    assert.equal(settings_emoji.derive_name_from_filename("thumbs up.gif"), "thumbs_up");
    assert.equal(settings_emoji.derive_name_from_filename("archive.tar.gz"), "archive.tar");
});
