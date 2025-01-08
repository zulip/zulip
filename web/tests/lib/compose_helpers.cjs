"use strict";

const assert = require("node:assert/strict");

const {noop} = require("./test.cjs");
const $ = require("./zjquery.cjs");

class FakeComposeBox {
    constructor() {
        // Simulate DOM relationships
        // stub_message_row($("textarea#compose-textarea"));
        $("#send_message_form").set_find_results(
            ".message-textarea",
            $("textarea#compose-textarea"),
        );
        $("#send_message_form").set_find_results(
            ".message-limit-indicator",
            $.create("limit-indicator-stub"),
        );

        const $message_row_stub = $.create("message_row_stub");
        $("textarea#compose-textarea").closest = (selector) => {
            assert.equal(selector, ".message_row");
            $message_row_stub.length = 0;
            return $message_row_stub;
        };

        this.reset();
    }

    reset() {
        $("#compose_banners .user_not_subscribed").length = 0;

        $("textarea#compose-textarea").toggleClass = noop;
        $("textarea#compose-textarea").set_height(50);
        $("#compose .preview_message_area").css = noop;
        $("textarea#compose-textarea").val("default message");
        $("textarea#compose-textarea").trigger("blur");
        $(".compose-submit-button .loader").show();
    }

    show_message_preview() {
        $("#compose .undo_markdown_preview").show();
        $("#compose .preview_message_area").show();
        $("#compose .markdown_preview").hide();
        $("#compose").addClass("preview_mode");
    }

    hide_message_preview() {
        $("#compose .markdown_preview").show();
        $("#compose .undo_markdown_preview").hide();
        $("#compose .preview_message_area").hide();
        $("#compose").removeClass("preview_mode");
    }

    textarea_val() {
        return $("textarea#compose-textarea").val();
    }

    preview_content_html() {
        return $("#compose .preview_content").html();
    }

    compose_spinner_selector() {
        return ".compose-submit-button .loader";
    }

    markdown_spinner_selector() {
        return "#compose .markdown_preview_spinner";
    }

    set_topic_val(topic_name) {
        $("input#stream_message_recipient_topic").val(topic_name);
    }

    set_textarea_val(val) {
        $("textarea#compose-textarea").val(val);
    }

    blur_textarea() {
        $("textarea#compose-textarea").trigger("blur");
    }

    show_submit_button_spinner() {
        $(".compose-submit-button .loader").show();
    }

    set_textarea_toggle_class_function(f) {
        $("textarea#compose-textarea").toggleClass = f;
    }

    is_recipient_not_subscribed_banner_visible() {
        return $("#compose_banners .recipient_not_subscribed").visible();
    }

    is_textarea_focused() {
        return $("textarea#compose-textarea").is_focused();
    }

    is_submit_button_spinner_visible() {
        return $(this.compose_spinner_selector()).visible();
    }

    trigger_submit_handler_on_compose_form(event) {
        $("#compose form").get_on_handler("submit")(event);
    }

    click_on_markdown_preview_icon(event) {
        $("#compose").get_on_handler("click", ".markdown_preview")(event);
    }

    click_on_undo_markdown_preview_icon(event) {
        $("#compose").get_on_handler("click", ".undo_markdown_preview")(event);
    }

    click_on_upload_attachment_icon(event) {
        $("#compose").get_on_handler("click", ".compose_upload_file")(event);
    }

    set_click_handler_for_upload_file_input_element(f) {
        $("#compose .file_input").on("click", f);
    }

    assert_preview_mode_is_off() {
        assert.ok(!$("#compose .undo_markdown_preview").visible());
        assert.ok(!$("#compose .preview_message_area").visible());
        assert.ok($("#compose .markdown_preview").visible());
        assert.ok(!$("#compose").hasClass("preview_mode"));
    }

    assert_preview_mode_is_on() {
        assert.ok(!$("#compose .markdown_preview").visible());
        assert.ok($("#compose .undo_markdown_preview").visible());
        assert.ok($("#compose .preview_message_area").visible());
        assert.ok($("#compose").hasClass("preview_mode"));
    }
}

module.exports = {FakeComposeBox};
