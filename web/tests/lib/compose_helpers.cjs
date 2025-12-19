"use strict";

const assert = require("node:assert/strict");

const {noop} = require("./test.cjs");
const $ = require("./zjquery.cjs");

class FakeComposeBox {
    constructor() {
        this.$send_message_form = $("#send_message_form");
        this.$content_textarea = $("textarea#compose-textarea");
        this.$preview_message_area = $("#compose .preview_message_area");

        // Simulate DOM relationships
        this.$send_message_form.set_find_results(".message-textarea", this.$content_textarea);

        this.$send_message_form.set_find_results(
            ".message-limit-indicator",
            $(".message-limit-indicator"),
        );

        const $message_row_stub = $.create("message_row_stub");
        this.$content_textarea.closest = (selector) => {
            assert.equal(selector, ".message_row");
            $message_row_stub.length = 0;
            return $message_row_stub;
        };

        this.reset();
    }

    reset() {
        $(".message-limit-indicator").html("");
        $(".message-limit-indicator").text("");

        $("#compose_banners .user_not_subscribed").length = 0;

        this.$content_textarea.toggleClass = noop;
        this.$content_textarea.set_height(50);
        this.$content_textarea.val("default message");
        this.$content_textarea.trigger("blur");

        this.$preview_message_area.css = noop;
        $(".compose-submit-button .loader").show();
    }

    show_message_preview() {
        this.$preview_message_area.show();
        $("#compose .undo_markdown_preview").show();
        $("#compose .markdown_preview").hide();
        $("#compose").addClass("preview_mode");
    }

    hide_message_preview() {
        this.$preview_message_area.hide();
        $("#compose .markdown_preview").show();
        $("#compose .undo_markdown_preview").hide();
        $("#compose").removeClass("preview_mode");
    }

    textarea_val() {
        return this.$content_textarea.val();
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
        this.$content_textarea.val(val);
    }

    blur_textarea() {
        this.$content_textarea.trigger("blur");
    }

    show_submit_button_spinner() {
        $(".compose-submit-button .loader").show();
    }

    set_textarea_toggle_class_function(f) {
        this.$content_textarea.toggleClass = f;
    }

    is_recipient_not_subscribed_banner_visible() {
        return $("#compose_banners .recipient_not_subscribed").visible();
    }

    is_textarea_focused() {
        return this.$content_textarea.is_focused();
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
        assert.ok(!this.$preview_message_area.visible());
        assert.ok(!$("#compose .undo_markdown_preview").visible());
        assert.ok($("#compose .markdown_preview").visible());
        assert.ok(!$("#compose").hasClass("preview_mode"));
    }

    assert_preview_mode_is_on() {
        assert.ok(this.$preview_message_area.visible());
        assert.ok(!$("#compose .markdown_preview").visible());
        assert.ok($("#compose .undo_markdown_preview").visible());
        assert.ok($("#compose").hasClass("preview_mode"));
    }

    assert_message_size_is_over_the_limit(desired_html) {
        // Indicator should show red colored text
        assert.equal($(".message-limit-indicator").html(), desired_html);

        assert.ok(this.$content_textarea.hasClass("textarea-over-limit"));
        assert.ok($(".message-limit-indicator").hasClass("textarea-over-limit"));
        assert.ok(!$("#compose-send-button").hasClass("disabled-message-send-controls"));
    }

    assert_message_size_is_under_the_limit(desired_html) {
        // Work around the quirk that our validation code
        // arbitrarily switches between html() and text(),
        // and zjquery doesn't unify text and html.
        if (desired_html) {
            assert.equal($(".message-limit-indicator").html(), desired_html);
        } else {
            assert.equal($(".message-limit-indicator").text(), "");
        }

        assert.ok(!this.$content_textarea.hasClass("textarea-over-limit"));
        assert.ok(!$(".message-limit-indicator").hasClass("textarea-over-limit"));
        assert.ok(!$("#compose-send-button").hasClass("disabled-message-send-controls"));
    }
}

function quote_message_template(opts) {
    const {channel_object, selected_message, fence, content} = opts;

    const {stream_id, name} = channel_object;
    const channel_name = name;
    const {sender_full_name, sender_id, id, topic} = selected_message;
    const near_url = `http://zulip.zulipdev.com/#narrow/channel/${stream_id}-${channel_name}/topic/${topic}/near/${id}`;
    return `translated: @_**${sender_full_name}|${sender_id}** [said](${near_url}):
${fence}quote
${content}
${fence}`;
}

function forward_channel_message_template(opts) {
    const {channel_object, selected_message, fence, content} = opts;

    const {stream_id, name} = channel_object;
    const channel_name = name;
    const {sender_full_name, sender_id, id, topic} = selected_message;
    const near_url = `http://zulip.zulipdev.com/#narrow/channel/${stream_id}-${channel_name}/topic/${topic}/near/${id}`;
    const with_url = `#narrow/channel/${stream_id}-${channel_name}/topic/${topic}/with/${id}`;
    const topic_link_syntax = `[#**${channel_name}>${topic}**](${with_url})`;
    return `translated: @_**${sender_full_name}|${sender_id}** [said](${near_url}) in ${topic_link_syntax}:
${fence}quote
${content}
${fence}`;
}

function forward_direct_message_template(opts) {
    const {direct_message, dm_recipient_string, fence, content} = opts;

    const {sender_full_name, sender_id, id: message_id, display_recipient} = direct_message;
    const encoding_prefix = display_recipient.length > 2 ? "group" : "dm";
    const dm_recipient_ids_string = display_recipient.map((user) => user.id).join(",");
    const near_url = `http://zulip.zulipdev.com/#narrow/dm/${dm_recipient_ids_string}-${encoding_prefix}/near/${message_id}`;

    return `translated: @_**${sender_full_name}|${sender_id}** [said](${near_url}) to ${dm_recipient_string}:
${fence}quote
${content}
${fence}`;
}

module.exports = {
    FakeComposeBox,
    quote_message_template,
    forward_channel_message_template,
    forward_direct_message_template,
};
