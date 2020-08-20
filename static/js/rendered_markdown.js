"use strict";

const ClipboardJS = require("clipboard");
const moment = require("moment");

const copy_code_button = require("../templates/copy_code_button.hbs");

const people = require("./people");

/*
    rendered_markdown

    This module provides a single function 'update_elements' to
    update any renamed users/streams/groups etc. and other
    dynamic parts of our rendered messages.

    Use this module wherever some Markdown rendered content
    is being displayed.
*/

function get_user_id_for_mention_button(elem) {
    const user_id_string = $(elem).attr("data-user-id");
    // Handle legacy Markdown that was rendered before we cut
    // over to using data-user-id.
    const email = $(elem).attr("data-user-email");

    if (user_id_string === "*" || email === "*") {
        return "*";
    }

    if (user_id_string) {
        return parseInt(user_id_string, 10);
    }

    if (email) {
        // Will return undefined if there's no match
        const user = people.get_by_email(email);
        if (user) {
            return user.user_id;
        }
        return;
    }
    return;
}

function get_user_group_id_for_mention_button(elem) {
    const user_group_id = $(elem).attr("data-user-group-id");

    if (user_group_id) {
        return parseInt(user_group_id, 10);
    }

    return;
}

// Helper function to update a mentioned user's name.
exports.set_name_in_mention_element = function (element, name) {
    if ($(element).hasClass("silent")) {
        $(element).text(name);
    } else {
        $(element).text("@" + name);
    }
};

exports.update_elements = (content) => {
    // Set the rtl class if the text has an rtl direction
    if (rtl.get_direction(content.text()) === "rtl") {
        content.addClass("rtl");
    }

    content.find(".user-mention").each(function () {
        const user_id = get_user_id_for_mention_button(this);
        // We give special highlights to the mention buttons
        // that refer to the current user.
        if (user_id === "*" || people.is_my_user_id(user_id)) {
            // Either a wildcard mention or us, so mark it.
            $(this).addClass("user-mention-me");
        }
        if (user_id && user_id !== "*" && !$(this).find(".highlight").length) {
            // If it's a mention of a specific user, edit the
            // mention text to show the user's current name,
            // assuming that you're not searching for text
            // inside the highlight.
            const person = people.get_by_user_id(user_id, true);
            if (person !== undefined) {
                // Note that person might be undefined in some
                // unpleasant corner cases involving data import.
                exports.set_name_in_mention_element(this, person.full_name);
            }
        }
    });

    content.find(".user-group-mention").each(function () {
        const user_group_id = get_user_group_id_for_mention_button(this);
        const user_group = user_groups.get_user_group_from_id(user_group_id, true);
        if (user_group === undefined) {
            // This is a user group the current user doesn't have
            // data on.  This can happen when user groups are
            // deleted.
            blueslip.info("Rendered unexpected user group " + user_group_id);
            return;
        }

        const my_user_id = people.my_current_user_id();
        // Mark user group you're a member of.
        if (user_groups.is_member_of(user_group_id, my_user_id)) {
            $(this).addClass("user-mention-me");
        }

        if (user_group_id && !$(this).find(".highlight").length) {
            // Edit the mention to show the current name for the
            // user group, if its not in search.
            $(this).text("@" + user_group.name);
        }
    });

    content.find("a.stream").each(function () {
        const stream_id = parseInt($(this).attr("data-stream-id"), 10);
        if (stream_id && !$(this).find(".highlight").length) {
            // Display the current name for stream if it is not
            // being displayed in search highlight.
            const stream_name = stream_data.maybe_get_stream_name(stream_id);
            if (stream_name !== undefined) {
                // If the stream has been deleted,
                // stream_data.maybe_get_stream_name might return
                // undefined.  Otherwise, display the current stream name.
                $(this).text("#" + stream_name);
            }
        }
    });

    content.find("a.stream-topic").each(function () {
        const stream_id = parseInt($(this).attr("data-stream-id"), 10);
        if (stream_id && !$(this).find(".highlight").length) {
            // Display the current name for stream if it is not
            // being displayed in search highlight.
            const text = $(this).text();
            const topic = text.split(">", 2)[1];
            const stream_name = stream_data.maybe_get_stream_name(stream_id);
            if (stream_name !== undefined) {
                // If the stream has been deleted,
                // stream_data.maybe_get_stream_name might return
                // undefined.  Otherwise, display the current stream name.
                $(this).text("#" + stream_name + " > " + topic);
            }
        }
    });

    content.find("time").each(function () {
        // Populate each timestamp span with mentioned time
        // in user's local timezone.
        const time_str = $(this).attr("datetime");
        if (time_str === undefined) {
            return;
        }

        // Moment throws a large deprecation warning when it has to
        // fallback to the Date() constructor.  This isn't really a
        // problem for us except in local echo, as the backend always
        // uses a format that ensures that is unnecessary.
        moment.suppressDeprecationWarnings = true;
        const timestamp = moment(time_str);
        if (timestamp.isValid()) {
            const text = $(this).text();
            const rendered_time = timerender.render_markdown_timestamp(timestamp, text);
            $(this).text(rendered_time.text);
            $(this).attr("title", rendered_time.title);
        } else {
            // This shouldn't happen. If it does, we're very interested in debugging it.
            blueslip.error(`Moment could not parse datetime supplied by backend: ${time_str}`);
        }
    });

    content.find("span.timestamp-error").each(function () {
        const time_str = $(this).text().replace("Invalid time format: ", "");
        const text = i18n.t("Invalid time format: __timestamp__", {timestamp: time_str});
        $(this).text(text);
    });

    content.find("div.spoiler-header").each(function () {
        // If a spoiler block has no header content, it should have a default header.
        // We do this client side to allow for i18n by the client.
        if ($(this).html().trim().length === 0) {
            $(this).append(`<p>${i18n.t("Spoiler")}</p>`);
        }

        // Add the expand/collapse button to spoiler blocks
        const toggle_button_html =
            '<span class="spoiler-button" aria-expanded="false"><span class="spoiler-arrow"></span></span>';
        $(this).prepend(toggle_button_html);
    });

    // Display the copy-to-clipboard button inside the div.codehilite element.
    content.find("div.codehilite").each(function () {
        const copy_button = $(copy_code_button());
        $(this).find("pre").prepend(copy_button);
        new ClipboardJS(copy_button[0], {
            text(copy_element) {
                return $(copy_element).siblings("code").text();
            },
        });
    });

    // Display emoji (including realm emoji) as text if
    // page_params.emojiset is 'text'.
    if (page_params.emojiset === "text") {
        content.find(".emoji").replaceWith(function () {
            const text = $(this).attr("title");
            return ":" + text + ":";
        });
    }
};
