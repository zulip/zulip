"use strict";

const {strict: assert} = require("assert");

const {mock_esm, set_global, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");
const {page_params} = require("./lib/zpage_params");

const compose_state = zrequire("compose_state");
const rows = zrequire("rows");

set_global("navigator", {
    userAgent: "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Trident/5.0)",
});

let uppy_stub;
mock_esm("@uppy/core", {
    Uppy: function Uppy(options) {
        return uppy_stub.call(this, options);
    },
});

mock_esm("@uppy/xhr-upload", {default: class XHRUpload {}});

const compose_actions = mock_esm("../src/compose_actions");
mock_esm("../src/csrf", {csrf_token: "csrf_token"});

const compose_ui = zrequire("compose_ui");
const upload = zrequire("upload");
const message_lists = zrequire("message_lists");
function test(label, f) {
    run_test(label, (helpers) => {
        page_params.max_file_upload_size_mib = 25;
        return f(helpers);
    });
}

test("feature_check", ({override}) => {
    const $upload_button = $.create("upload-button-stub");
    $upload_button.addClass("notdisplayed");
    upload.feature_check($upload_button);
    assert.ok($upload_button.hasClass("notdisplayed"));

    override(window, "XMLHttpRequest", () => ({upload: true}));
    upload.feature_check($upload_button);
    assert.ok(!$upload_button.hasClass("notdisplayed"));
});

test("get_item", () => {
    assert.equal(upload.get_item("textarea", {mode: "compose"}), $("#compose-textarea"));
    assert.equal(
        upload.get_item("upload_banner_message", {mode: "compose"}, "id_1"),
        $("#compose_banners .upload_banner.file_id_1 .upload_msg"),
    );
    assert.equal(
        upload.get_item("upload_banner_cancel_button", {mode: "compose"}, "id_2"),
        $("#compose_banners .upload_banner.file_id_2 .upload_banner_cancel_button"),
    );
    assert.equal(
        upload.get_item("upload_banner_hide_button", {mode: "compose"}, "id_2"),
        $("#compose_banners .upload_banner.file_id_2 .main-view-banner-close-button"),
    );
    assert.equal(
        upload.get_item("file_input_identifier", {mode: "compose"}),
        "#compose .file_input",
    );
    assert.equal(upload.get_item("source", {mode: "compose"}), "compose-file-input");
    assert.equal(upload.get_item("drag_drop_container", {mode: "compose"}), $("#compose"));
    assert.equal(
        upload.get_item("markdown_preview_hide_button", {mode: "compose"}),
        $("#compose .undo_markdown_preview"),
    );

    assert.equal(
        upload.get_item("textarea", {mode: "edit", row: 1}),
        $(`#edit_form_${CSS.escape(1)} .message_edit_content`),
    );

    $(`#edit_form_${CSS.escape(2)}`).set_find_results(
        ".message_edit_save",
        $(".message_edit_save"),
    );
    assert.equal(upload.get_item("send_button", {mode: "edit", row: 2}), $(".message_edit_save"));

    assert.equal(
        upload.get_item("upload_banner_identifier", {mode: "edit", row: 11}, "id_3"),
        `#edit_form_${CSS.escape(11)} .upload_banner.file_id_3`,
    );
    assert.equal(
        upload.get_item("upload_banner", {mode: "edit", row: 75}, "id_60"),
        $(`#edit_form_${CSS.escape(75)} .upload_banner.file_id_60`),
    );

    $(`#edit_form_${CSS.escape(2)} .upload_banner`).set_find_results(
        ".upload_banner_cancel_button",
        $(".upload_banner_cancel_button"),
    );
    assert.equal(
        upload.get_item("upload_banner_cancel_button", {mode: "edit", row: 2}, "id_34"),
        $(`#edit_form_${CSS.escape(2)} .upload_banner.file_id_34 .upload_banner_cancel_button`),
    );

    $(`#edit_form_${CSS.escape(2)} .upload_banner`).set_find_results(
        ".main-view-banner-close-button",
        $(".main-view-banner-close-button"),
    );
    assert.equal(
        upload.get_item("upload_banner_hide_button", {mode: "edit", row: 2}, "id_34"),
        $(`#edit_form_${CSS.escape(2)} .upload_banner.file_id_34 .main-view-banner-close-button`),
    );

    $(`#edit_form_${CSS.escape(22)} .upload_banner.file_id_234`).set_find_results(
        ".upload_msg",
        $(".upload_msg"),
    );
    assert.equal(
        upload.get_item("upload_banner_message", {mode: "edit", row: 22}, "id_234"),
        $(`#edit_form_${CSS.escape(22)} .upload_banner.file_id_234 .upload_msg`),
    );

    assert.equal(
        upload.get_item("file_input_identifier", {mode: "edit", row: 123}),
        `#edit_form_${CSS.escape(123)} .file_input`,
    );
    assert.equal(upload.get_item("source", {mode: "edit", row: 123}), "message-edit-file-input");
    assert.equal(
        upload.get_item("drag_drop_container", {mode: "edit", row: 1}),
        $(`#zfilt${CSS.escape(1)} .message_edit_form`),
    );
    assert.equal(
        upload.get_item("markdown_preview_hide_button", {mode: "edit", row: 65}),
        $(`#edit_form_${CSS.escape(65)} .undo_markdown_preview`),
    );

    assert.throws(
        () => {
            upload.get_item("textarea");
        },
        {
            name: "Error",
            message: "Missing config",
        },
    );
    assert.throws(
        () => {
            upload.get_item("textarea", {mode: "edit"});
        },
        {
            name: "Error",
            message: "Missing row in config",
        },
    );
    assert.throws(
        () => {
            upload.get_item("textarea", {mode: "blah"});
        },
        {
            name: "Error",
            message: "Invalid upload mode!",
        },
    );
    assert.throws(
        () => {
            upload.get_item("invalid", {mode: "compose"});
        },
        {
            name: "Error",
            message: 'Invalid key name for mode "compose"',
        },
    );
    assert.throws(
        () => {
            upload.get_item("invalid", {mode: "edit", row: 20});
        },
        {
            name: "Error",
            message: 'Invalid key name for mode "edit"',
        },
    );
});

test("show_error_message", ({mock_template}) => {
    $("#compose_banners .upload_banner .moving_bar").css = () => {};
    $("#compose_banners .upload_banner").length = 0;

    let banner_shown = false;
    mock_template("compose_banner/upload_banner.hbs", false, (data) => {
        assert.equal(data.banner_type, "error");
        assert.equal(data.banner_text, "Error message");
        banner_shown = true;
    });

    $("#compose-send-button").prop("disabled", true);

    upload.show_error_message({mode: "compose"}, "Error message");
    assert.equal($("#compose-send-button").prop("disabled"), false);
    assert.ok(banner_shown);

    mock_template("compose_banner/upload_banner.hbs", false, (data) => {
        assert.equal(data.banner_type, "error");
        assert.equal(data.banner_text, "translated: An unknown error occurred.");
        banner_shown = true;
    });
    upload.show_error_message({mode: "compose"});
});

test("upload_files", async ({mock_template, override_rewire}) => {
    $("#compose_banners .upload_banner").remove = () => {};
    $("#compose_banners .upload_banner .moving_bar").css = () => {};
    $("#compose_banners .upload_banner").length = 0;

    let files = [
        {
            name: "budapest.png",
            type: "image/png",
        },
    ];
    let uppy_add_file_called = false;
    let remove_file_called = false;
    const uppy = {
        addFile(params) {
            uppy_add_file_called = true;
            assert.equal(params.source, "compose-file-input");
            assert.equal(params.name, "budapest.png");
            assert.equal(params.type, "image/png");
            assert.equal(params.data, files[0]);
            return "id_123";
        },
        removeFile() {
            remove_file_called = true;
        },
    };
    let hide_upload_banner_called = false;
    override_rewire(upload, "hide_upload_banner", (_uppy, config) => {
        hide_upload_banner_called = true;
        assert.equal(config.mode, "compose");
    });
    const config = {mode: "compose"};
    $("#compose-send-button").prop("disabled", false);
    await upload.upload_files(uppy, config, []);
    assert.ok(!$("#compose-send-button").prop("disabled"));

    let banner_shown = false;
    mock_template("compose_banner/upload_banner.hbs", false, (data) => {
        assert.equal(data.banner_type, "error");
        assert.equal(
            data.banner_text,
            "translated: File and image uploads have been disabled for this organization.",
        );
        banner_shown = true;
    });
    page_params.max_file_upload_size_mib = 0;
    $("#compose_banners .upload_banner .upload_msg").text("");
    await upload.upload_files(uppy, config, files);
    assert.ok(banner_shown);

    page_params.max_file_upload_size_mib = 25;
    let on_click_close_button_callback;

    $("#compose_banners .upload_banner.file_id_123 .upload_banner_cancel_button").one = (
        event,
        callback,
    ) => {
        assert.equal(event, "click");
        on_click_close_button_callback = callback;
    };
    let compose_ui_insert_syntax_and_focus_called = false;
    override_rewire(compose_ui, "insert_syntax_and_focus", () => {
        compose_ui_insert_syntax_and_focus_called = true;
    });
    let compose_ui_autosize_textarea_called = false;
    override_rewire(compose_ui, "autosize_textarea", () => {
        compose_ui_autosize_textarea_called = true;
    });
    let markdown_preview_hide_button_clicked = false;
    $("#compose .undo_markdown_preview").on("click", () => {
        markdown_preview_hide_button_clicked = true;
    });
    $("#compose-send-button").prop("disabled", false);
    $("#compose_banners .upload_banner").remove();
    $("#compose .undo_markdown_preview").show();

    banner_shown = false;
    mock_template("compose_banner/upload_banner.hbs", false, () => {
        banner_shown = true;
    });
    await upload.upload_files(uppy, config, files);
    assert.ok($("#compose-send-button").prop("disabled"));
    assert.ok(banner_shown);
    assert.ok(compose_ui_insert_syntax_and_focus_called);
    assert.ok(compose_ui_autosize_textarea_called);
    assert.ok(markdown_preview_hide_button_clicked);
    assert.ok(uppy_add_file_called);

    banner_shown = false;
    files = [
        {
            name: "budapest.png",
            type: "image/png",
        },
        {
            name: "prague.png",
            type: "image/png",
        },
    ];
    let add_file_counter = 0;
    uppy.addFile = (file) => {
        add_file_counter += 1;
        if (file.name === "budapest.png") {
            throw new Error("some error");
        }
        return `id_${add_file_counter}`;
    };
    await upload.upload_files(uppy, config, files);
    assert.ok(banner_shown);
    assert.equal(add_file_counter, 2);

    hide_upload_banner_called = false;
    let compose_ui_replace_syntax_called = false;

    override_rewire(compose_ui, "replace_syntax", (old_syntax, new_syntax, textarea) => {
        compose_ui_replace_syntax_called = true;
        assert.equal(old_syntax, "[translated: Uploading budapest.png…]()");
        assert.equal(new_syntax, "");
        assert.equal(textarea, $("#compose-textarea"));
    });
    on_click_close_button_callback();
    assert.ok(remove_file_called);
    assert.ok(hide_upload_banner_called);
    assert.ok(compose_ui_autosize_textarea_called);
    assert.ok(compose_ui_replace_syntax_called);
    hide_upload_banner_called = false;
    compose_ui_replace_syntax_called = false;
    remove_file_called = false;
    $("#compose-textarea").val("user modified text");

    on_click_close_button_callback();
    assert.ok(remove_file_called);
    assert.ok(hide_upload_banner_called);
    assert.ok(compose_ui_autosize_textarea_called);
    assert.ok(compose_ui_replace_syntax_called);
    assert.equal($("#compose-textarea").val(), "user modified text");
});

test("uppy_config", () => {
    let uppy_stub_called = false;
    let uppy_set_meta_called = false;
    let uppy_used_xhrupload = false;

    uppy_stub = function (config) {
        uppy_stub_called = true;
        assert.equal(config.debug, false);
        assert.equal(config.autoProceed, true);
        assert.equal(config.restrictions.maxFileSize, 25 * 1024 * 1024);
        assert.equal(Object.keys(config.locale.strings).length, 2);
        assert.ok("exceedsSize" in config.locale.strings);

        return {
            setMeta(params) {
                uppy_set_meta_called = true;
                assert.equal(params.csrfmiddlewaretoken, "csrf_token");
            },
            use(func, params) {
                const func_name = func.name;
                if (func_name === "XHRUpload") {
                    uppy_used_xhrupload = true;
                    assert.equal(params.endpoint, "/json/user_uploads");
                    assert.equal(params.formData, true);
                    assert.equal(params.fieldName, "file");
                    assert.equal(params.limit, 5);
                    assert.equal(Object.keys(params.locale.strings).length, 1);
                    assert.ok("timedOut" in params.locale.strings);
                } else {
                    /* istanbul ignore next */
                    assert.fail(`Missing tests for ${func_name}`);
                }
            },
            on() {},
        };
    };
    upload.setup_upload({mode: "compose"});

    assert.equal(uppy_stub_called, true);
    assert.equal(uppy_set_meta_called, true);
    assert.equal(uppy_used_xhrupload, true);
});

test("file_input", ({override_rewire}) => {
    upload.setup_upload({mode: "compose"});

    const change_handler = $("body").get_on_handler("change", "#compose .file_input");
    const files = ["file1", "file2"];
    const event = {
        target: {
            files,
            value: "C:\\fakepath\\portland.png",
        },
    };
    let upload_files_called = false;
    override_rewire(upload, "upload_files", (_uppy, config, files) => {
        assert.equal(config.mode, "compose");
        assert.equal(files, files);
        upload_files_called = true;
    });
    change_handler(event);
    assert.ok(upload_files_called);
});

test("file_drop", ({override, override_rewire}) => {
    upload.setup_upload({mode: "compose"});

    let prevent_default_counter = 0;
    const drag_event = {
        preventDefault() {
            prevent_default_counter += 1;
        },
    };
    const dragover_handler = $("#compose").get_on_handler("dragover");
    dragover_handler(drag_event);
    assert.equal(prevent_default_counter, 1);

    const dragenter_handler = $("#compose").get_on_handler("dragenter");
    dragenter_handler(drag_event);
    assert.equal(prevent_default_counter, 2);

    let stop_propagation_counter = 0;
    const files = ["file1", "file2"];
    const drop_event = {
        preventDefault() {
            prevent_default_counter += 1;
        },
        stopPropagation() {
            stop_propagation_counter += 1;
        },
        originalEvent: {
            dataTransfer: {
                files,
            },
        },
    };
    const drop_handler = $("#compose").get_on_handler("drop");
    let upload_files_called = false;
    override_rewire(upload, "upload_files", () => {
        upload_files_called = true;
    });
    let compose_actions_start_called = false;
    override(compose_actions, "respond_to_message", () => {
        compose_actions_start_called = true;
    });
    drop_handler(drop_event);
    assert.ok(compose_actions_start_called);
    assert.equal(prevent_default_counter, 3);
    assert.equal(stop_propagation_counter, 1);
    assert.equal(upload_files_called, true);
});

test("copy_paste", ({override, override_rewire}) => {
    upload.setup_upload({mode: "compose"});

    const paste_handler = $("#compose").get_on_handler("paste");
    let get_as_file_called = false;
    let event = {
        originalEvent: {
            clipboardData: {
                items: [
                    {
                        kind: "file",
                        getAsFile() {
                            get_as_file_called = true;
                        },
                    },
                    {
                        kind: "notfile",
                    },
                ],
            },
        },
        preventDefault() {},
    };
    let upload_files_called = false;
    override_rewire(upload, "upload_files", () => {
        upload_files_called = true;
    });
    let compose_actions_start_called = false;
    override(compose_actions, "respond_to_message", () => {
        compose_actions_start_called = true;
    });

    paste_handler(event);
    assert.ok(get_as_file_called);
    assert.ok(upload_files_called);
    assert.ok(compose_actions_start_called);
    upload_files_called = false;
    event = {
        originalEvent: {},
    };
    paste_handler(event);
    assert.equal(upload_files_called, false);
});

test("uppy_events", ({override_rewire, mock_template}) => {
    $("#compose_banners .upload_banner .moving_bar").css = () => {};
    $("#compose_banners .upload_banner").length = 0;
    override_rewire(compose_ui, "smart_insert_inline", () => {});

    const callbacks = {};
    let state = {};

    uppy_stub = function () {
        return {
            setMeta() {},
            use() {},
            on(event_name, callback) {
                callbacks[event_name] = callback;
            },
            removeFile() {},
            getState: () => ({
                info: [
                    {
                        type: state.type,
                        details: state.details,
                        message: state.message,
                    },
                ],
            }),
        };
    };
    upload.setup_upload({mode: "compose"});
    assert.equal(Object.keys(callbacks).length, 5);

    const on_upload_success_callback = callbacks["upload-success"];
    const file = {
        name: "copenhagen.png",
        id: "123",
    };
    let response = {
        body: {
            uri: "/user_uploads/4/cb/rue1c-MlMUjDAUdkRrEM4BTJ/copenhagen.png",
        },
    };

    let compose_ui_replace_syntax_called = false;
    override_rewire(compose_ui, "replace_syntax", (old_syntax, new_syntax, textarea) => {
        compose_ui_replace_syntax_called = true;
        assert.equal(old_syntax, "[translated: Uploading copenhagen.png…]()");
        assert.equal(
            new_syntax,
            "[copenhagen.png](/user_uploads/4/cb/rue1c-MlMUjDAUdkRrEM4BTJ/copenhagen.png)",
        );
        assert.equal(textarea, $("#compose-textarea"));
    });
    let compose_ui_autosize_textarea_called = false;
    override_rewire(compose_ui, "autosize_textarea", () => {
        compose_ui_autosize_textarea_called = true;
    });
    on_upload_success_callback(file, response);

    assert.ok(compose_ui_replace_syntax_called);
    assert.ok(compose_ui_autosize_textarea_called);

    response = {
        body: {
            uri: undefined,
        },
    };
    compose_ui_replace_syntax_called = false;
    compose_ui_autosize_textarea_called = false;
    on_upload_success_callback(file, response);
    assert.equal(compose_ui_replace_syntax_called, false);
    assert.equal(compose_ui_autosize_textarea_called, false);

    mock_template("compose_banner/upload_banner.hbs", false, (data) => {
        assert.equal(data.banner_type, "error");
        assert.equal(data.banner_text, "Some error message");
    });
    state = {
        type: "error",
        details: "Some error",
        message: "Some error message",
    };
    const on_info_visible_callback = callbacks["info-visible"];
    $("#compose_banners .upload_banner .upload_msg").text("");
    compose_ui_replace_syntax_called = false;
    const on_restriction_failed_callback = callbacks["restriction-failed"];
    on_info_visible_callback();
    override_rewire(compose_ui, "replace_syntax", (old_syntax, new_syntax, textarea) => {
        compose_ui_replace_syntax_called = true;
        assert.equal(old_syntax, "[translated: Uploading copenhagen.png…]()");
        assert.equal(new_syntax, "");
        assert.equal(textarea, $("#compose-textarea"));
    });
    on_restriction_failed_callback(file, null, null);
    assert.ok(compose_ui_replace_syntax_called);
    compose_ui_replace_syntax_called = false;
    $("#compose-textarea").val("user modified text");
    on_restriction_failed_callback(file, null, null);
    assert.ok(compose_ui_replace_syntax_called);
    assert.equal($("#compose-textarea").val(), "user modified text");

    state = {
        type: "error",
        message: "No Internet connection",
    };
    on_info_visible_callback();

    state = {
        type: "error",
        details: "Upload Error",
    };
    on_info_visible_callback();

    const on_upload_error_callback = callbacks["upload-error"];
    $("#compose_banners .upload_banner .upload_msg").text("");
    compose_ui_replace_syntax_called = false;
    response = {
        body: {
            msg: "Response message",
        },
    };
    on_upload_error_callback(file, null, response);
    assert.ok(compose_ui_replace_syntax_called);

    compose_ui_replace_syntax_called = false;
    on_upload_error_callback(file, null, null);
    assert.ok(compose_ui_replace_syntax_called);

    $("#compose_banners .upload_banner .upload_msg").text("");
    $("#compose-textarea").val("user modified text");
    on_upload_error_callback(file, null);
    assert.ok(compose_ui_replace_syntax_called);
    assert.equal($("#compose-textarea").val(), "user modified text");
});

test("main_file_drop_compose_mode", ({override_rewire}) => {
    uppy_stub = function () {
        return {
            setMeta() {},
            use() {},
            cancelAll() {},
            on() {},
            getFiles() {},
            removeFile() {},
        };
    };
    upload.setup_upload({mode: "compose"});
    upload.initialize();

    let prevent_default_counter = 0;
    const drag_event = {
        preventDefault() {
            prevent_default_counter += 1;
        },
    };

    // dragover event test
    const dragover_handler = $(".app-main").get_on_handler("dragover");
    dragover_handler(drag_event);
    assert.equal(prevent_default_counter, 1);

    // dragenter event test
    const dragenter_handler = $(".app-main").get_on_handler("dragenter");
    dragenter_handler(drag_event);
    assert.equal(prevent_default_counter, 2);

    const files = ["file1", "file2"];
    const drop_event = {
        target: "target",
        preventDefault() {
            prevent_default_counter += 1;
        },
        originalEvent: {
            dataTransfer: {
                files,
            },
        },
    };

    $(".message_edit_form form").last = () => ({length: 0});

    const drop_handler = $(".app-main").get_on_handler("drop");

    // Test drop on compose box
    let upload_files_called = false;
    override_rewire(upload, "upload_files", () => {
        upload_files_called = true;
    });
    compose_state.composing = () => true;
    drop_handler(drop_event);
    assert.equal(upload_files_called, true);
    assert.equal(prevent_default_counter, 3);

    // Test reply to message if no edit and compose box open
    upload_files_called = false;
    compose_state.composing = () => false;
    const msg = {
        type: "stream",
        stream: "Denmark",
        topic: "python",
        sender_full_name: "Bob Roberts",
        sender_id: 40,
    };
    let compose_actions_start_called = false;
    let compose_actions_respond_to_message_called = false;
    override_rewire(message_lists, "current", {
        selected_message() {
            return msg;
        },
    });
    compose_actions.start = () => {
        compose_actions_start_called = true;
    };
    compose_actions.respond_to_message = () => {
        compose_actions_respond_to_message_called = true;
    };
    drop_handler(drop_event);
    assert.equal(upload_files_called, true);
    assert.equal(compose_actions_start_called, false);
    assert.equal(compose_actions_respond_to_message_called, true);

    // Test drop on Recent Conversations view
    compose_actions_respond_to_message_called = false;
    override_rewire(message_lists, "current", {
        selected_message() {
            return undefined;
        },
    });
    upload_files_called = false;
    drop_handler(drop_event);
    assert.equal(upload_files_called, true);
    assert.equal(compose_actions_start_called, true);
    assert.equal(compose_actions_respond_to_message_called, false);
});

test("main_file_drop_edit_mode", ({override_rewire}) => {
    uppy_stub = function () {
        return {
            setMeta() {},
            use() {},
            cancelAll() {},
            on() {},
            getFiles() {},
            removeFile() {},
        };
    };

    upload.setup_upload({mode: "edit", row: 40});
    upload.initialize();
    compose_state.composing = () => false;
    let prevent_default_counter = 0;
    const drag_event = {
        preventDefault() {
            prevent_default_counter += 1;
        },
    };
    const $drag_drop_container = $(`#zfilt${CSS.escape(40)} .message_edit_form`);

    // Dragover event test
    const dragover_handler = $(".app-main").get_on_handler("dragover");
    dragover_handler(drag_event);
    assert.equal(prevent_default_counter, 1);
    // Dragenter event test
    const dragenter_handler = $(".app-main").get_on_handler("dragenter");
    dragenter_handler(drag_event);
    assert.equal(prevent_default_counter, 2);

    const files = ["file1", "file2"];
    const drop_event = {
        target: "target",
        preventDefault() {
            prevent_default_counter += 1;
        },
        originalEvent: {
            dataTransfer: {
                files,
            },
        },
    };
    const drop_handler = $(".app-main").get_on_handler("drop");
    let upload_files_called = false;
    let dropped_row_id = -1;
    override_rewire(upload, "upload_files", (_, config) => {
        dropped_row_id = config.row;
        upload_files_called = true;
    });
    $(".message_edit_form form").last = () => ({length: 1});
    rows.get_message_id = () => 40;

    // Edit box which registered the event handler no longer exists.
    $drag_drop_container.closest = (element) => {
        assert.equal(element, "html");
        return {length: 0};
    };

    drop_handler(drop_event);
    assert.equal(upload_files_called, false);

    $drag_drop_container.closest = (element) => {
        assert.equal(element, "html");
        return {length: 1};
    };

    // Drag and dropped in one of the edit boxes. The event would be taken care of by
    // drag_drop_container event handlers.

    rows.get_message_id = () => 40;
    // Edit box open
    $(".message_edit_form form").last = () => ({length: 1});
    drop_handler(drop_event);
    assert.equal(upload_files_called, true);
    assert.equal(dropped_row_id, 40);
});
