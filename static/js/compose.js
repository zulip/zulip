"use strict";

const Handlebars = require("handlebars/runtime");

const render_compose_all_everyone = require("../templates/compose_all_everyone.hbs");
const render_compose_announce = require("../templates/compose_announce.hbs");
const render_compose_invite_users = require("../templates/compose_invite_users.hbs");
const render_compose_not_subscribed = require("../templates/compose_not_subscribed.hbs");
const render_compose_private_stream_alert = require("../templates/compose_private_stream_alert.hbs");

const people = require("./people");
const rendered_markdown = require("./rendered_markdown");
const util = require("./util");

// Docs: https://zulip.readthedocs.io/en/latest/subsystems/sending-messages.html

/* Track the state of the @all warning. The user must acknowledge that they are spamming the entire
   stream before the warning will go away. If they try to send before explicitly dismissing the
   warning, they will get an error message too.

   undefined: no @all/@everyone in message;
   false: user typed @all/@everyone;
   true: user clicked YES */

let user_acknowledged_all_everyone;
let user_acknowledged_announce;
let wildcard_mention;
let uppy;

exports.wildcard_mention_large_stream_threshold = 15;
exports.announce_warn_threshold = 60;

exports.uploads_domain = document.location.protocol + "//" + document.location.host;
exports.uploads_path = "/user_uploads";
exports.uploads_re = new RegExp(
    "\\]\\(" + exports.uploads_domain + "(" + exports.uploads_path + "[^\\)]+)\\)",
    "g",
);

function make_uploads_relative(content) {
    // Rewrite uploads in Markdown links back to domain-relative form
    return content.replace(exports.uploads_re, "]($1)");
}

function show_all_everyone_warnings(stream_id) {
    const stream_count = stream_data.get_subscriber_count(stream_id) || 0;

    const all_everyone_template = render_compose_all_everyone({
        count: stream_count,
        mention: wildcard_mention,
    });
    const error_area_all_everyone = $("#compose-all-everyone");

    // only show one error for any number of @all or @everyone mentions
    if (!error_area_all_everyone.is(":visible")) {
        error_area_all_everyone.append(all_everyone_template);
    }

    error_area_all_everyone.show();
    user_acknowledged_all_everyone = false;
}

exports.compute_show_video_chat_button = function () {
    const available_providers = page_params.realm_available_video_chat_providers;
    if (page_params.realm_video_chat_provider === available_providers.disabled.id) {
        return false;
    }

    if (
        page_params.realm_video_chat_provider === available_providers.jitsi_meet.id &&
        !page_params.jitsi_server_url
    ) {
        return false;
    }

    return true;
};

exports.update_video_chat_button_display = function () {
    const show_video_chat_button = exports.compute_show_video_chat_button();
    $("#below-compose-content .video_link").toggle(show_video_chat_button);
    $(".message-edit-feature-group .video_link").toggle(show_video_chat_button);
};

exports.clear_all_everyone_warnings = function () {
    $("#compose-all-everyone").hide();
    $("#compose-all-everyone").empty();
    $("#compose-send-status").hide();
};

function show_sending_indicator(whats_happening) {
    $("#sending-indicator").text(whats_happening);
    $("#sending-indicator").show();
}

function show_announce_warnings(stream_id) {
    const stream_count = stream_data.get_subscriber_count(stream_id) || 0;

    const announce_template = render_compose_announce({count: stream_count});
    const error_area_announce = $("#compose-announce");

    if (!error_area_announce.is(":visible")) {
        error_area_announce.append(announce_template);
    }

    error_area_announce.show();
    user_acknowledged_announce = false;
}

exports.clear_announce_warnings = function () {
    $("#compose-announce").hide();
    $("#compose-announce").empty();
    $("#compose-send-status").hide();
};

exports.clear_invites = function () {
    $("#compose_invite_users").hide();
    $("#compose_invite_users").empty();
};

exports.clear_private_stream_alert = function () {
    $("#compose_private_stream_alert").hide();
    $("#compose_private_stream_alert").empty();
};

exports.reset_user_acknowledged_all_everyone_flag = function () {
    user_acknowledged_all_everyone = undefined;
};

exports.reset_user_acknowledged_announce_flag = function () {
    user_acknowledged_announce = undefined;
};

exports.clear_preview_area = function () {
    $("#compose-textarea").show();
    $("#undo_markdown_preview").hide();
    $("#preview_message_area").hide();
    $("#preview_content").empty();
    $("#markdown_preview").show();
};

function update_stream_button(btn_text, title) {
    $("#left_bar_compose_stream_button_big").text(btn_text);
    $("#left_bar_compose_stream_button_big").prop("title", title);
}

function update_conversation_button(btn_text, title) {
    $("#left_bar_compose_private_button_big").text(btn_text);
    $("#left_bar_compose_private_button_big").prop("title", title);
}

exports.update_closed_compose_buttons_for_private = function () {
    const text_stream = i18n.t("New stream message");
    const title_stream = text_stream + " (c)";
    const text_conversation = i18n.t("New private message");
    const title_conversation = text_conversation + " (x)";
    update_stream_button(text_stream, title_stream);
    update_conversation_button(text_conversation, title_conversation);
};

exports.update_closed_compose_buttons_for_stream = function () {
    const text_stream = i18n.t("New topic");
    const title_stream = text_stream + " (c)";
    const text_conversation = i18n.t("New private message");
    const title_conversation = text_conversation + " (x)";
    update_stream_button(text_stream, title_stream);
    update_conversation_button(text_conversation, title_conversation);
};

function update_fade() {
    if (!compose_state.composing()) {
        return;
    }

    const msg_type = compose_state.get_message_type();
    compose_fade.set_focused_recipient(msg_type);
    compose_fade.update_all();
}

exports.abort_xhr = function () {
    $("#compose-send-button").prop("disabled", false);
    uppy.cancelAll();
};

exports.zoom_token_callbacks = new Map();
exports.zoom_xhrs = new Map();

exports.abort_zoom = function (edit_message_id) {
    const key = edit_message_id || "";
    exports.zoom_token_callbacks.delete(key);
    if (exports.zoom_xhrs.has(key)) {
        exports.zoom_xhrs.get(key).abort();
    }
};

exports.empty_topic_placeholder = function () {
    return i18n.t("(no topic)");
};

function create_message_object() {
    // Topics are optional, and we provide a placeholder if one isn't given.
    let topic = compose_state.topic();
    if (topic === "") {
        topic = exports.empty_topic_placeholder();
    }

    const content = make_uploads_relative(compose_state.message_content());

    // Changes here must also be kept in sync with echo.try_deliver_locally
    const message = {
        type: compose_state.get_message_type(),
        content,
        sender_id: page_params.user_id,
        queue_id: page_params.queue_id,
        stream: "",
    };
    message.topic = "";

    if (message.type === "private") {
        // TODO: this should be collapsed with the code in composebox_typeahead.js
        const recipient = compose_state.private_message_recipient();
        const emails = util.extract_pm_recipients(recipient);
        message.to = emails;
        message.reply_to = recipient;
        message.private_message_recipient = recipient;
        message.to_user_ids = people.email_list_to_user_ids_string(emails);

        // Note: The `undefined` case is for situations like the
        // is_zephyr_mirror_realm case where users may be
        // automatically created when you try to send a private
        // message to their email address.
        if (message.to_user_ids !== undefined) {
            message.to = people.user_ids_string_to_ids_array(message.to_user_ids);
        }
    } else {
        const stream_name = compose_state.stream_name();
        message.stream = stream_name;
        const sub = stream_data.get_sub(stream_name);
        if (sub) {
            message.stream_id = sub.stream_id;
            message.to = sub.stream_id;
        } else {
            // We should be validating streams in calling code.  We'll
            // try to fall back to stream_name here just in case the
            // user started composing to the old stream name and
            // manually entered the stream name, and it got past
            // validation. We should try to kill this code off eventually.
            blueslip.error("Trying to send message with bad stream name: " + stream_name);
            message.to = stream_name;
        }
        message.topic = topic;
    }
    return message;
}

exports.create_message_object = create_message_object;

function compose_error(error_text, bad_input) {
    $("#compose-send-status")
        .removeClass(common.status_classes)
        .addClass("alert-error")
        .stop(true)
        .fadeTo(0, 1);
    $("#compose-error-msg").html(error_text);
    $("#compose-send-button").prop("disabled", false);
    $("#sending-indicator").hide();
    if (bad_input !== undefined) {
        bad_input.trigger("focus").trigger("select");
    }
}

exports.compose_error = compose_error;

function nonexistent_stream_reply_error() {
    $("#nonexistent_stream_reply_error").show();
    $("#compose-reply-error-msg").html("There are no messages to reply to yet.");
    setTimeout(() => {
        $("#nonexistent_stream_reply_error").hide();
    }, 5000);
}

function compose_not_subscribed_error(error_text, bad_input) {
    $("#compose-send-status")
        .removeClass(common.status_classes)
        .addClass("home-error-bar")
        .stop(true)
        .fadeTo(0, 1);
    $("#compose-error-msg").html(error_text);
    $("#compose-send-button").prop("disabled", false);
    $("#sending-indicator").hide();
    $(".compose-send-status-close").hide();
    if (bad_input !== undefined) {
        bad_input.trigger("focus").trigger("select");
    }
}

exports.nonexistent_stream_reply_error = nonexistent_stream_reply_error;

function clear_compose_box() {
    $("#compose-textarea").val("").trigger("focus");
    drafts.delete_draft_after_send();
    compose_ui.autosize_textarea($("#compose-textarea"));
    $("#compose-send-status").hide(0);
    $("#compose-send-button").prop("disabled", false);
    $("#sending-indicator").hide();
}

exports.clear_compose_box = clear_compose_box;

exports.send_message_success = function (local_id, message_id, locally_echoed) {
    if (!locally_echoed) {
        clear_compose_box();
    }

    echo.reify_message_id(local_id, message_id);
};

exports.send_message = function send_message(request) {
    if (request === undefined) {
        request = create_message_object();
    }

    if (request.type === "private") {
        request.to = JSON.stringify(request.to);
    } else {
        request.to = JSON.stringify([request.to]);
    }

    let local_id;
    let locally_echoed;

    const message = echo.try_deliver_locally(request);
    if (message) {
        // We are rendering this message locally with an id
        // like 92l99.01 that corresponds to a reasonable
        // approximation of the id we'll get from the server
        // in terms of sorting messages.
        local_id = message.local_id;
        locally_echoed = true;
    } else {
        // We are not rendering this message locally, but we
        // track the message's life cycle with an id like
        // loc-1, loc-2, loc-3,etc.
        locally_echoed = false;
        local_id = sent_messages.get_new_local_id();
    }

    request.local_id = local_id;

    sent_messages.start_tracking_message({
        local_id,
        locally_echoed,
    });

    request.locally_echoed = locally_echoed;

    function success(data) {
        exports.send_message_success(local_id, data.id, locally_echoed);
    }

    function error(response) {
        // If we're not local echo'ing messages, or if this message was not
        // locally echoed, show error in compose box
        if (!locally_echoed) {
            compose_error(response, $("#compose-textarea"));
            return;
        }

        echo.message_send_error(message.id, response);
    }

    transmit.send_message(request, success, error);
    server_events.assert_get_events_running(
        "Restarting get_events because it was not running during send",
    );

    if (locally_echoed) {
        clear_compose_box();
    }
};

exports.enter_with_preview_open = function () {
    if (page_params.enter_sends) {
        // If enter_sends is enabled, we attempt to send the message
        exports.finish();
    } else {
        // Otherwise, we return to the compose box and focus it
        $("#compose-textarea").trigger("focus");
    }
};

exports.finish = function () {
    exports.clear_preview_area();
    exports.clear_invites();
    exports.clear_private_stream_alert();
    notifications.clear_compose_notifications();

    const message_content = compose_state.message_content();

    // Skip normal validation for zcommands, since they aren't
    // actual messages with recipients; users only send them
    // from the compose box for convenience sake.
    if (zcommand.process(message_content)) {
        exports.do_post_send_tasks();
        clear_compose_box();
        return undefined;
    }

    if (!exports.validate()) {
        return false;
    }

    if (reminder.is_deferred_delivery(message_content)) {
        reminder.schedule_message();
    } else {
        exports.send_message();
    }
    exports.do_post_send_tasks();
    return true;
};

exports.do_post_send_tasks = function () {
    exports.clear_preview_area();
    // TODO: Do we want to fire the event even if the send failed due
    // to a server-side error?
    $(document).trigger($.Event("compose_finished.zulip"));
};

exports.update_email = function (user_id, new_email) {
    let reply_to = compose_state.private_message_recipient();

    if (!reply_to) {
        return;
    }

    reply_to = people.update_email_in_reply_to(reply_to, user_id, new_email);

    compose_state.private_message_recipient(reply_to);
};

exports.get_invalid_recipient_emails = function () {
    const private_recipients = util.extract_pm_recipients(
        compose_state.private_message_recipient(),
    );
    const invalid_recipients = private_recipients.filter(
        (email) => !people.is_valid_email_for_compose(email),
    );

    return invalid_recipients;
};

function check_unsubscribed_stream_for_send(stream_name, autosubscribe) {
    let result;
    if (!autosubscribe) {
        return "not-subscribed";
    }

    // In the rare circumstance of the autosubscribe option, we
    // *Synchronously* try to subscribe to the stream before sending
    // the message.  This is deprecated and we hope to remove it; see
    // #4650.
    channel.post({
        url: "/json/subscriptions/exists",
        data: {stream: stream_name, autosubscribe: true},
        async: false,
        success(data) {
            if (data.subscribed) {
                result = "subscribed";
            } else {
                result = "not-subscribed";
            }
        },
        error(xhr) {
            if (xhr.status === 404) {
                result = "does-not-exist";
            } else {
                result = "error";
            }
        },
    });
    return result;
}

function validate_stream_message_mentions(stream_id) {
    const stream_count = stream_data.get_subscriber_count(stream_id) || 0;

    // check if wildcard_mention has any mention and henceforth execute the warning message.
    if (
        wildcard_mention !== null &&
        stream_count > exports.wildcard_mention_large_stream_threshold
    ) {
        if (
            user_acknowledged_all_everyone === undefined ||
            user_acknowledged_all_everyone === false
        ) {
            // user has not seen a warning message yet if undefined
            show_all_everyone_warnings(stream_id);

            $("#compose-send-button").prop("disabled", false);
            $("#sending-indicator").hide();
            return false;
        }
    } else {
        // the message no longer contains @all or @everyone
        exports.clear_all_everyone_warnings();
    }
    // at this point, the user has either acknowledged the warning or removed @all / @everyone
    user_acknowledged_all_everyone = undefined;

    return true;
}

function validate_stream_message_announce(sub) {
    const stream_count = stream_data.get_subscriber_count(sub.stream_id) || 0;

    if (sub.name === "announce" && stream_count > exports.announce_warn_threshold) {
        if (user_acknowledged_announce === undefined || user_acknowledged_announce === false) {
            // user has not seen a warning message yet if undefined
            show_announce_warnings(sub.stream_id);

            $("#compose-send-button").prop("disabled", false);
            $("#sending-indicator").hide();
            return false;
        }
    } else {
        exports.clear_announce_warnings();
    }
    // at this point, the user has acknowledged the warning
    user_acknowledged_announce = undefined;

    return true;
}

function validate_stream_message_post_policy(sub) {
    if (page_params.is_admin) {
        return true;
    }

    const stream_post_permission_type = stream_data.stream_post_policy_values;
    const stream_post_policy = sub.stream_post_policy;

    if (stream_post_policy === stream_post_permission_type.admins.code) {
        compose_error(i18n.t("Only organization admins are allowed to post to this stream."));
        return false;
    }

    if (page_params.is_guest && stream_post_policy !== stream_post_permission_type.everyone.code) {
        compose_error(i18n.t("Guests are not allowed to post to this stream."));
        return false;
    }

    const person = people.get_by_user_id(page_params.user_id);
    const current_datetime = new Date(Date.now());
    const person_date_joined = new Date(person.date_joined);
    const days = (current_datetime - person_date_joined) / 1000 / 86400;
    let error_text;
    if (
        stream_post_policy === stream_post_permission_type.non_new_members.code &&
        days < page_params.realm_waiting_period_threshold
    ) {
        error_text = i18n.t(
            "New members are not allowed to post to this stream.<br>Permission will be granted in __days__ days.",
            {days},
        );
        compose_error(error_text);
        return false;
    }
    return true;
}

exports.validation_error = function (error_type, stream_name) {
    let response;

    const context = {};
    context.stream_name = Handlebars.Utils.escapeExpression(stream_name);

    switch (error_type) {
        case "does-not-exist":
            response = i18n.t(
                "<p>The stream <b>__stream_name__</b> does not exist.</p><p>Manage your subscriptions <a href='#streams/all'>on your Streams page</a>.</p>",
                context,
            );
            compose_error(response, $("#stream_message_recipient_stream"));
            return false;
        case "error":
            compose_error(
                i18n.t("Error checking subscription"),
                $("#stream_message_recipient_stream"),
            );
            return false;
        case "not-subscribed": {
            const sub = stream_data.get_sub(stream_name);
            const new_row = render_compose_not_subscribed({
                should_display_sub_button: sub.should_display_subscription_button,
            });
            compose_not_subscribed_error(new_row, $("#stream_message_recipient_stream"));
            return false;
        }
    }
    return true;
};

exports.validate_stream_message_address_info = function (stream_name) {
    if (stream_data.is_subscribed(stream_name)) {
        return true;
    }
    const autosubscribe = page_params.narrow_stream !== undefined;
    const error_type = check_unsubscribed_stream_for_send(stream_name, autosubscribe);
    return exports.validation_error(error_type, stream_name);
};

function validate_stream_message() {
    const stream_name = compose_state.stream_name();
    if (stream_name === "") {
        compose_error(i18n.t("Please specify a stream"), $("#stream_message_recipient_stream"));
        return false;
    }

    if (page_params.realm_mandatory_topics) {
        const topic = compose_state.topic();
        if (topic === "") {
            compose_error(i18n.t("Please specify a topic"), $("#stream_message_recipient_topic"));
            return false;
        }
    }

    const sub = stream_data.get_sub(stream_name);
    if (!sub) {
        return exports.validation_error("does-not-exist", stream_name);
    }

    if (!validate_stream_message_post_policy(sub)) {
        return false;
    }

    /* Note: This is a global and thus accessible in the functions
       below; it's important that we update this state here before
       proceeding with further validation. */
    wildcard_mention = util.find_wildcard_mentions(compose_state.message_content());

    // If both `@all` is mentioned and it's in `#announce`, just validate
    // for `@all`. Users shouldn't have to hit "yes" more than once.
    if (wildcard_mention !== null && stream_name === "announce") {
        if (
            !exports.validate_stream_message_address_info(stream_name) ||
            !validate_stream_message_mentions(sub.stream_id)
        ) {
            return false;
        }
        // If either criteria isn't met, just do the normal validation.
    } else {
        if (
            !exports.validate_stream_message_address_info(stream_name) ||
            !validate_stream_message_mentions(sub.stream_id) ||
            !validate_stream_message_announce(sub)
        ) {
            return false;
        }
    }

    return true;
}

// The function checks whether the recipients are users of the realm or cross realm users (bots
// for now)
function validate_private_message() {
    if (page_params.realm_private_message_policy === 2) {
        // Frontend check for for PRIVATE_MESSAGE_POLICY_DISABLED
        const user_ids = compose_pm_pill.get_user_ids();
        if (user_ids.length !== 1 || !people.get_by_user_id(user_ids[0]).is_bot) {
            // Unless we're composing to a bot
            compose_error(
                i18n.t("Private messages are disabled in this organization."),
                $("#private_message_recipient"),
            );
            return false;
        }
    }

    if (compose_state.private_message_recipient().length === 0) {
        compose_error(
            i18n.t("Please specify at least one valid recipient"),
            $("#private_message_recipient"),
        );
        return false;
    } else if (page_params.realm_is_zephyr_mirror_realm) {
        // For Zephyr mirroring realms, the frontend doesn't know which users exist
        return true;
    }

    const invalid_recipients = exports.get_invalid_recipient_emails();

    let context = {};
    if (invalid_recipients.length === 1) {
        context = {recipient: invalid_recipients.join()};
        compose_error(
            i18n.t("The recipient __recipient__ is not valid", context),
            $("#private_message_recipient"),
        );
        return false;
    } else if (invalid_recipients.length > 1) {
        context = {recipients: invalid_recipients.join()};
        compose_error(
            i18n.t("The recipients __recipients__ are not valid", context),
            $("#private_message_recipient"),
        );
        return false;
    }
    return true;
}

exports.validate = function () {
    $("#compose-send-button").prop("disabled", true).trigger("blur");
    const message_content = compose_state.message_content();
    if (reminder.is_deferred_delivery(message_content)) {
        show_sending_indicator(i18n.t("Scheduling..."));
    } else {
        show_sending_indicator(i18n.t("Sending..."));
    }

    if (/^\s*$/.test(message_content)) {
        compose_error(i18n.t("You have nothing to send!"), $("#compose-textarea"));
        return false;
    }

    if ($("#zephyr-mirror-error").is(":visible")) {
        compose_error(i18n.t("You need to be running Zephyr mirroring in order to send messages!"));
        return false;
    }

    if (compose_state.get_message_type() === "private") {
        return validate_private_message();
    }
    return validate_stream_message();
};

exports.handle_keydown = function (event, textarea) {
    const code = event.keyCode || event.which;
    const isBold = code === 66;
    const isItalic = code === 73 && !event.shiftKey;
    const isLink = code === 76 && event.shiftKey;

    // detect Cmd and Ctrl key
    const isCmdOrCtrl = common.has_mac_keyboard() ? event.metaKey : event.ctrlKey;

    if ((isBold || isItalic || isLink) && isCmdOrCtrl) {
        const range = textarea.range();
        function wrap_text_with_markdown(prefix, suffix) {
            if (!document.execCommand("insertText", false, prefix + range.text + suffix)) {
                textarea.range(range.start, range.end).range(prefix + range.text + suffix);
            }
            event.preventDefault();
        }

        if (isBold) {
            // Ctrl + B: Convert selected text to bold text
            wrap_text_with_markdown("**", "**");
            if (!range.length) {
                textarea.caret(textarea.caret() - 2);
            }
        }
        if (isItalic) {
            // Ctrl + I: Convert selected text to italic text
            wrap_text_with_markdown("*", "*");
            if (!range.length) {
                textarea.caret(textarea.caret() - 1);
            }
        }
        if (isLink) {
            // Ctrl + L: Insert a link to selected text
            wrap_text_with_markdown("[", "](url)");
            const position = textarea.caret();
            const txt = textarea[0];

            // Include selected text in between [] parentheses and insert '(url)'
            // where "url" should be automatically selected.
            // Position of cursor depends on whether browser supports exec
            // command or not. So set cursor position accordingly.
            if (range.length > 0) {
                if (document.queryCommandEnabled("insertText")) {
                    txt.selectionStart = position - 4;
                    txt.selectionEnd = position - 1;
                } else {
                    txt.selectionStart = position + range.length + 3;
                    txt.selectionEnd = position + range.length + 6;
                }
            } else {
                textarea.caret(textarea.caret() - 6);
            }
        }

        compose_ui.autosize_textarea(textarea);
        return;
    }
};

exports.handle_keyup = function (event, textarea) {
    // Set the rtl class if the text has an rtl direction, remove it otherwise
    rtl.set_rtl_class_for_textarea(textarea);
};

exports.needs_subscribe_warning = function (user_id, stream_id) {
    // This returns true if all of these conditions are met:
    //  * the user is valid
    //  * the user is not already subscribed to the stream
    //  * the user has no back-door way to see stream messages
    //    (i.e. bots on public/private streams)
    //
    //  You can think of this as roughly answering "is there an
    //  actionable way to subscribe the user and do they actually
    //  need it?".
    //
    //  We expect the caller to already have verified that we're
    //  sending to a valid stream and trying to mention the user.

    const user = people.get_by_user_id(user_id);

    if (!user) {
        return false;
    }

    if (user.is_bot) {
        // Bots may receive messages on public/private streams even if they are
        // not subscribed.
        return false;
    }

    if (stream_data.is_user_subscribed(stream_id, user_id)) {
        // If our user is already subscribed
        return false;
    }

    return true;
};

function insert_video_call_url(url, target_textarea) {
    const link_text = i18n.t("Click to join video call");
    compose_ui.insert_syntax_and_focus(`[${link_text}](${url})`, target_textarea);
}

exports.render_and_show_preview = function (preview_spinner, preview_content_box, content) {
    function show_preview(rendered_content, raw_content) {
        // content is passed to check for status messages ("/me ...")
        // and will be undefined in case of errors
        let rendered_preview_html;
        if (raw_content !== undefined && markdown.is_status_message(raw_content)) {
            // Handle previews of /me messages
            rendered_preview_html =
                "<p><strong>" +
                page_params.full_name +
                "</strong>" +
                rendered_content.slice("<p>/me".length);
        } else {
            rendered_preview_html = rendered_content;
        }

        preview_content_box.html(util.clean_user_content_links(rendered_preview_html));
        rendered_markdown.update_elements(preview_content_box);
    }

    if (content.length === 0) {
        show_preview(i18n.t("Nothing to preview"));
    } else {
        if (markdown.contains_backend_only_syntax(content)) {
            const spinner = preview_spinner.expectOne();
            loading.make_indicator(spinner);
        } else {
            // For messages that don't appear to contain syntax that
            // is only supported by our backend Markdown processor, we
            // render using the frontend Markdown processor (but still
            // render server-side to ensure the preview is accurate;
            // if the `markdown.contains_backend_only_syntax` logic is
            // wrong, users will see a brief flicker of the locally
            // echoed frontend rendering before receiving the
            // authoritative backend rendering from the server).
            const message_obj = {
                raw_content: content,
            };
            markdown.apply_markdown(message_obj);
        }
        channel.post({
            url: "/json/messages/render",
            idempotent: true,
            data: {content},
            success(response_data) {
                if (markdown.contains_backend_only_syntax(content)) {
                    loading.destroy_indicator(preview_spinner);
                }
                show_preview(response_data.rendered, content);
            },
            error() {
                if (markdown.contains_backend_only_syntax(content)) {
                    loading.destroy_indicator(preview_spinner);
                }
                show_preview(i18n.t("Failed to generate preview"));
            },
        });
    }
};

exports.warn_if_private_stream_is_linked = function (linked_stream) {
    // For PMs, we currently don't warn about links to private
    // streams, since you are specifically sharing the existence of
    // the private stream with someone.  One could imagine changing
    // this policy if user feedback suggested it was useful.
    if (compose_state.get_message_type() !== "stream") {
        return;
    }

    const compose_stream = stream_data.get_sub(compose_state.stream_name());
    if (compose_stream === undefined) {
        // We have an invalid stream name, don't warn about this here as
        // we show an error to the user when they try to send the message.
        return;
    }

    // If the stream we're linking to is not invite-only, then it's
    // public, and there is no need to warn about it, since all
    // members can already see all the public streams.
    //
    // Theoretically, we could still do a warning if there are any
    // guest users subscribed to the stream we're posting to; we may
    // change this policy if user feedback suggests it'd be an
    // improvement.
    if (!linked_stream.invite_only) {
        return;
    }

    if (stream_data.is_subscriber_subset(compose_stream, linked_stream)) {
        // Don't warn if subscribers list of current compose_stream is
        // a subset of linked_stream's subscribers list, because
        // everyone will be subscribed to the linked stream and so
        // knows it exists.
        return;
    }

    const stream_name = linked_stream.name;

    const warning_area = $("#compose_private_stream_alert");
    const context = {stream_name};
    const new_row = render_compose_private_stream_alert(context);

    warning_area.append(new_row);
    warning_area.show();
};

exports.warn_if_mentioning_unsubscribed_user = function (mentioned) {
    if (compose_state.get_message_type() !== "stream") {
        return;
    }

    // Disable for Zephyr mirroring realms, since we never have subscriber lists there
    if (page_params.realm_is_zephyr_mirror_realm) {
        return;
    }

    const user_id = mentioned.user_id;

    if (mentioned.is_broadcast) {
        return; // don't check if @all/@everyone/@stream
    }

    const stream_name = compose_state.stream_name();

    if (!stream_name) {
        return;
    }

    const sub = stream_data.get_sub(stream_name);

    if (!sub) {
        return;
    }

    if (exports.needs_subscribe_warning(user_id, sub.stream_id)) {
        const error_area = $("#compose_invite_users");
        const existing_invites_area = $("#compose_invite_users .compose_invite_user");

        const existing_invites = Array.from($(existing_invites_area), (user_row) =>
            Number.parseInt($(user_row).data("user-id"), 10),
        );

        if (!existing_invites.includes(user_id)) {
            const context = {
                user_id,
                stream_id: sub.stream_id,
                name: mentioned.full_name,
                can_subscribe_other_users: page_params.can_subscribe_other_users,
            };

            const new_row = render_compose_invite_users(context);
            error_area.append(new_row);
        }

        error_area.show();
    }
};

exports.initialize = function () {
    $("#below-compose-content .video_link").toggle(exports.compute_show_video_chat_button());
    $(
        "#stream_message_recipient_stream,#stream_message_recipient_topic,#private_message_recipient",
    ).on("keyup", update_fade);
    $(
        "#stream_message_recipient_stream,#stream_message_recipient_topic,#private_message_recipient",
    ).on("change", update_fade);
    $("#compose-textarea").on("keydown", (event) => {
        exports.handle_keydown(event, $("#compose-textarea").expectOne());
    });
    $("#compose-textarea").on("keyup", (event) => {
        exports.handle_keyup(event, $("#compose-textarea").expectOne());
    });

    $("#compose form").on("submit", (e) => {
        e.preventDefault();
        exports.finish();
    });

    resize.watch_manual_resize("#compose-textarea");

    upload.feature_check($("#compose #attach_files"));

    $("#compose-all-everyone").on("click", ".compose-all-everyone-confirm", (event) => {
        event.preventDefault();

        $(event.target).parents(".compose-all-everyone").remove();
        user_acknowledged_all_everyone = true;
        exports.clear_all_everyone_warnings();
        exports.finish();
    });

    $("#compose-announce").on("click", ".compose-announce-confirm", (event) => {
        event.preventDefault();

        $(event.target).parents(".compose-announce").remove();
        user_acknowledged_announce = true;
        exports.clear_announce_warnings();
        exports.finish();
    });

    $("#compose-send-status").on("click", ".sub_unsub_button", (event) => {
        event.preventDefault();

        const stream_name = $("#stream_message_recipient_stream").val();
        if (stream_name === undefined) {
            return;
        }
        const sub = stream_data.get_sub(stream_name);
        subs.sub_or_unsub(sub);
        $("#compose-send-status").hide();
    });

    $("#compose-send-status").on("click", "#compose_not_subscribed_close", (event) => {
        event.preventDefault();

        $("#compose-send-status").hide();
    });

    $("#compose_invite_users").on("click", ".compose_invite_link", (event) => {
        event.preventDefault();

        const invite_row = $(event.target).parents(".compose_invite_user");

        const user_id = Number.parseInt($(invite_row).data("user-id"), 10);
        const stream_id = Number.parseInt($(invite_row).data("stream-id"), 10);

        function success() {
            const all_invites = $("#compose_invite_users");
            invite_row.remove();

            if (all_invites.children().length === 0) {
                all_invites.hide();
            }
        }

        function failure(error_msg) {
            exports.clear_invites();
            compose_error(error_msg, $("#compose-textarea"));
            $(event.target).prop("disabled", true);
        }

        function xhr_failure(xhr) {
            const error = JSON.parse(xhr.responseText);
            failure(error.msg);
        }

        const sub = stream_data.get_sub_by_id(stream_id);

        stream_edit.invite_user_to_stream([user_id], sub, success, xhr_failure);
    });

    $("#compose_invite_users").on("click", ".compose_invite_close", (event) => {
        const invite_row = $(event.target).parents(".compose_invite_user");
        const all_invites = $("#compose_invite_users");

        invite_row.remove();

        if (all_invites.children().length === 0) {
            all_invites.hide();
        }
    });

    $("#compose_private_stream_alert").on(
        "click",
        ".compose_private_stream_alert_close",
        (event) => {
            const stream_alert_row = $(event.target).parents(".compose_private_stream_alert");
            const stream_alert = $("#compose_private_stream_alert");

            stream_alert_row.remove();

            if (stream_alert.children().length === 0) {
                stream_alert.hide();
            }
        },
    );

    // Click event binding for "Attach files" button
    // Triggers a click on a hidden file input field

    $("#compose").on("click", "#attach_files", (e) => {
        e.preventDefault();
        $("#compose #file_input").trigger("click");
    });

    $("body").on("click", ".video_link", (e) => {
        e.preventDefault();

        let target_textarea;
        // The data-message-id attribute is only present in the video
        // call icon present in the message edit form.  If present,
        // the request is for the edit UI; otherwise, it's for the
        // compose box.
        const edit_message_id = $(e.target).attr("data-message-id");
        if (edit_message_id !== undefined) {
            target_textarea = $("#message_edit_content_" + edit_message_id);
        }

        let video_call_link;
        const video_call_id = util.random_int(100000000000000, 999999999999999);
        const available_providers = page_params.realm_available_video_chat_providers;
        const show_video_chat_button = exports.compute_show_video_chat_button();

        if (!show_video_chat_button) {
            return;
        }

        if (
            available_providers.zoom &&
            page_params.realm_video_chat_provider === available_providers.zoom.id
        ) {
            exports.abort_zoom(edit_message_id);
            const key = edit_message_id || "";

            const make_zoom_call = () => {
                exports.zoom_xhrs.set(
                    key,
                    channel.post({
                        url: "/json/calls/zoom/create",
                        success(res) {
                            exports.zoom_xhrs.delete(key);
                            insert_video_call_url(res.url, target_textarea);
                        },
                        error(xhr, status) {
                            exports.zoom_xhrs.delete(key);
                            if (
                                status === "error" &&
                                xhr.responseJSON &&
                                xhr.responseJSON.code === "INVALID_ZOOM_TOKEN"
                            ) {
                                page_params.has_zoom_token = false;
                            }
                            if (status !== "abort") {
                                ui_report.generic_embed_error(
                                    i18n.t("Failed to create video call."),
                                );
                            }
                        },
                    }),
                );
            };

            if (page_params.has_zoom_token) {
                make_zoom_call();
            } else {
                exports.zoom_token_callbacks.set(key, make_zoom_call);
                window.open(
                    window.location.protocol + "//" + window.location.host + "/calls/zoom/register",
                    "_blank",
                    "width=800,height=500,noopener,noreferrer",
                );
            }
        } else if (
            available_providers.big_blue_button &&
            page_params.realm_video_chat_provider === available_providers.big_blue_button.id
        ) {
            channel.get({
                url: "/json/calls/bigbluebutton/create",
                success(response) {
                    insert_video_call_url(response.url, target_textarea);
                },
            });
        } else {
            video_call_link = page_params.jitsi_server_url + "/" + video_call_id;
            insert_video_call_url(video_call_link, target_textarea);
        }
    });

    $("#compose").on("click", "#markdown_preview", (e) => {
        e.preventDefault();
        const content = $("#compose-textarea").val();
        $("#compose-textarea").hide();
        $("#markdown_preview").hide();
        $("#undo_markdown_preview").show();
        $("#preview_message_area").show();

        exports.render_and_show_preview(
            $("#markdown_preview_spinner"),
            $("#preview_content"),
            content,
        );
    });

    $("#compose").on("click", "#undo_markdown_preview", (e) => {
        e.preventDefault();
        exports.clear_preview_area();
    });

    uppy = upload.setup_upload({
        mode: "compose",
    });

    $("#compose-textarea").on("focus", () => {
        compose_actions.update_placeholder_text();
    });

    $("#stream_message_recipient_topic").on("focus", () => {
        compose_actions.update_placeholder_text();
    });

    if (page_params.narrow !== undefined) {
        if (page_params.narrow_topic !== undefined) {
            compose_actions.start("stream", {topic: page_params.narrow_topic});
        } else {
            compose_actions.start("stream", {});
        }
    }
};

window.compose = exports;
