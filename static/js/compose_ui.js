"use strict";

const autosize = require("autosize");

const people = require("./people");

exports.autosize_textarea = function () {
    autosize.update($("#compose-textarea"));
};

exports.smart_insert = function (textarea, syntax) {
    function is_space(c) {
        return c === " " || c === "\t" || c === "\n";
    }

    const pos = textarea.caret();
    const before_str = textarea.val().slice(0, pos);
    const after_str = textarea.val().slice(pos);

    if (pos > 0) {
        // If there isn't space either at the end of the content
        // before the insert or (unlikely) at the start of the syntax,
        // add one.
        if (!is_space(before_str.slice(-1)) && !is_space(syntax[0])) {
            syntax = " " + syntax;
        }
    }

    // If there isn't whitespace either at the end of the syntax or the
    // start of the content after the syntax, add one.
    if (
        !(
            (after_str.length > 0 && is_space(after_str[0])) ||
            (syntax.length > 0 && is_space(syntax.slice(-1)))
        )
    ) {
        syntax += " ";
    }

    textarea.trigger("focus");

    // We prefer to use insertText, which supports things like undo better
    // for rich-text editing features like inserting links.  But we fall
    // back to textarea.caret if the browser doesn't support insertText.
    if (!document.execCommand("insertText", false, syntax)) {
        textarea.caret(syntax);
    }

    // This should just call exports.autosize_textarea, but it's a bit
    // annoying for the unit tests, so we don't do that.
    autosize.update(textarea);
};

exports.insert_syntax_and_focus = function (syntax, textarea) {
    // Generic helper for inserting syntax into the main compose box
    // where the cursor was and focusing the area.  Mostly a thin
    // wrapper around smart_insert.
    if (textarea === undefined) {
        textarea = $("#compose-textarea");
    }
    exports.smart_insert(textarea, syntax);
};

exports.replace_syntax = function (old_syntax, new_syntax, textarea) {
    // Replaces `old_syntax` with `new_syntax` text in the compose box. Due to
    // the way that JavaScript handles string replacements, if `old_syntax` is
    // a string it will only replace the first instance. If `old_syntax` is
    // a RegExp with a global flag, it will replace all instances.

    if (textarea === undefined) {
        textarea = $("#compose-textarea");
    }

    textarea.val(
        textarea.val().replace(
            old_syntax,
            () =>
                // We need this anonymous function to avoid JavaScript's
                // replace() function treating `$`s in new_syntax as special syntax.  See
                // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/replace#Description
                // for details.
                new_syntax,
        ),
    );
};

exports.compute_placeholder_text = function (opts) {
    // Computes clear placeholder text for the compose box, depending
    // on what heading values have already been filled out.
    //
    // We return text with the stream and topic name unescaped,
    // because the caller is expected to insert this into the
    // placeholder field in a way that does HTML escaping.
    if (opts.message_type === "stream") {
        if (opts.topic) {
            return i18n.t("Message #__- stream_name__ > __- topic_name__", {
                stream_name: opts.stream,
                topic_name: opts.topic,
            });
        } else if (opts.stream) {
            return i18n.t("Message #__- stream_name__", {stream_name: opts.stream});
        }
    }

    // For Private Messages
    if (opts.private_message_recipient) {
        const recipient_list = opts.private_message_recipient.split(",");
        const recipient_names = recipient_list
            .map((recipient) => {
                const user = people.get_by_email(recipient);
                return user.full_name;
            })
            .join(", ");

        if (recipient_list.length === 1) {
            // If it's a single user, display status text if available
            const user = people.get_by_email(recipient_list[0]);
            const status = user_status.get_status_text(user.user_id);
            if (status) {
                return i18n.t("Message __- recipient_name__ (__- recipient_status__)", {
                    recipient_name: recipient_names,
                    recipient_status: status,
                });
            }
        }
        return i18n.t("Message __- recipient_names__", {recipient_names});
    }
    return i18n.t("Compose your message here");
};

window.compose_ui = exports;
