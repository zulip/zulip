"use strict";

zrequire("ui_report");
set_global("csrf_token", "csrf_token");
set_global("$", global.make_zjquery());

const ImageUploadWidget = zrequire("image_upload_widget");
const _page_params = {
    is_admin: true,
    zulip_plan_is_not_limited: true,
    avatar_source: "G",
};
let form_data;
const _ui_report = {
    success(msg, elem) {
        elem.val(msg);
    },

    error(msg, xhr, elem) {
        elem.val(msg);
    },
};

const _FormData = function () {
    return form_data;
};

const _channel = {};

set_global("channel", _channel);
set_global("page_params", _page_params);
set_global("ui_report", _ui_report);
set_global("FormData", _FormData);

run_test("image_upload_widget", () => {
    function test_complete_upload(spinner, upload_text, delete_button, error_field) {
        assert.equal(error_field.is(":visible"), false);
        assert.equal(spinner.is(":visible"), false);
        assert.equal(upload_text.is(":visible"), true);
        assert.equal(delete_button.is(":visible"), true);
    }

    function test_image_upload(widget) {
        form_data = {
            append(field, val) {
                form_data[field] = val;
            },
        };
        const image_upload_widget = new ImageUploadWidget(widget);

        const file_input = [{files: ["image1.png", "image2.png"]}];
        let posted;
        const url = image_upload_widget.url;
        const spinner = $(`#${widget} .upload-spinner-background`);
        const upload_text = $(`#${widget}  .image-upload-text`);
        const delete_button = $(`#${widget}  .image-delete-button`);
        const error_field = $(`#${widget}  .image_file_input_error`);

        channel.post = function (req) {
            posted = true;
            assert.equal(req.url, url);
            assert.equal(req.data.csrfmiddlewaretoken, "csrf_token");
            assert.equal(req.cache, false);
            assert.equal(req.processData, false);
            assert.equal(req.contentType, false);
            assert.equal(req.data["file-0"], "image1.png");
            assert.equal(req.data["file-1"], "image2.png");
            req.success();
            req.error();
        };

        image_upload_widget.upload_image(file_input);
        test_complete_upload(spinner, upload_text, delete_button, error_field);
        assert(posted);
    }

    test_image_upload("user-avatar-upload-widget");
    test_image_upload("realm-icon-upload-widget");
    test_image_upload("realm-day-logo-upload-widget");
    test_image_upload("realm-night-logo-upload-widget");
});
