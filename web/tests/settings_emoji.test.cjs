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
    ) => {
        assert.equal(get_file_input()[0], $("#emoji_file_input")[0]);
        assert.equal($file_name_field[0], $("#emoji-file-name")[0]);
        assert.equal($input_error[0], $("#emoji_file_input_error")[0]);
        assert.equal($clear_button[0], $("#emoji_image_clear_button")[0]);
        assert.equal($upload_button[0], $("#emoji_upload_button")[0]);
        build_widget_stub = true;
    };
    settings_emoji.add_custom_emoji_post_render();
    assert.ok(build_widget_stub);
});

run_test("pad_image_to_square fallback", async () => {
    const dummy_file = {name: "test.png", type: "image/png"};
    const dummy_image = {naturalWidth: 200, naturalHeight: 100};
    const result = await settings_emoji.pad_image_to_square(dummy_image, dummy_file);
    assert.equal(result, dummy_file);
});

run_test("aspect_ratio_toggle_and_clear", () => {
    upload_widget.build_widget = () => {};
    settings_emoji.add_custom_emoji_post_render();

    const $clear_button = $("#emoji_image_clear_button");
    const $toggle_button = $("#emoji_aspect_ratio_toggle_button");

    assert.equal(settings_emoji.get_current_aspect_ratio_mode(), "pad");

    $clear_button.trigger("click");
    assert.ok(!$toggle_button.visible());
    assert.equal(settings_emoji.get_current_aspect_ratio_mode(), "pad");
});

run_test("aspect_ratio_toggle_with_non_square_image", () => {
    upload_widget.build_widget = () => {};
    settings_emoji.add_custom_emoji_post_render();

    const $toggle_button = $("#emoji_aspect_ratio_toggle_button");
    const $toggle_button_label = $("#emoji_aspect_ratio_toggle_button .action-button-label");
    const $preview_image = $("#emoji_preview_image");

    let img_onload;
    class MockImage {
        naturalWidth = 0;
        naturalHeight = 0;

        set src(_val) {
            this.naturalWidth = 300;
            this.naturalHeight = 100;
            if (img_onload) {
                img_onload();
            }
        }

        addEventListener(event, fn) {
            if (event === "load") {
                img_onload = fn;
            }
        }
    }

    const original_Image = global.Image;
    const original_URL = global.URL;
    global.Image = MockImage;
    global.URL = {
        createObjectURL() {
            return "blob:http://localhost/dummy";
        },
        revokeObjectURL() {},
    };

    const dummy_file = new Blob(["dummy"], {type: "image/png"});
    dummy_file.name = "wide.png";
    $("#emoji_file_input")[0].files = [dummy_file];
    $("#emoji_file_input").trigger("change");

    assert.ok($toggle_button.visible());
    assert.equal(settings_emoji.get_current_aspect_ratio_mode(), "pad");
    assert.equal($toggle_button_label.text(), "translated: Crop to square");
    assert.ok($preview_image.hasClass("preview-pad"));

    // Toggle to crop mode
    $toggle_button.trigger("click");
    assert.equal(settings_emoji.get_current_aspect_ratio_mode(), "crop");
    assert.equal($toggle_button_label.text(), "translated: Pad to square");
    assert.ok($preview_image.hasClass("preview-crop"));

    // Toggle back to pad mode
    $toggle_button.trigger("click");
    assert.equal(settings_emoji.get_current_aspect_ratio_mode(), "pad");
    assert.equal($toggle_button_label.text(), "translated: Crop to square");
    assert.ok($preview_image.hasClass("preview-pad"));

    global.Image = original_Image;
    global.URL = original_URL;
});
