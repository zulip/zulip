import ClipboardJS from "clipboard";
import {isValid, parseISO} from "date-fns";
import $ from "jquery";

import copy_code_button from "../templates/copy_code_button.hbs";
import render_markdown_timestamp from "../templates/markdown_timestamp.hbs";
import view_code_in_playground from "../templates/view_code_in_playground.hbs";

import * as blueslip from "./blueslip";
import {$t, $t_html} from "./i18n";
import * as people from "./people";
import * as realm_playground from "./realm_playground";
import * as rtl from "./rtl";
import * as stream_data from "./stream_data";
import * as sub_store from "./sub_store";
import * as timerender from "./timerender";
import {show_copied_confirmation} from "./tippyjs";
import * as user_groups from "./user_groups";
import {user_settings} from "./user_settings";

/*
    rendered_markdown

    This module provides a single function 'update_elements' to
    update any renamed users/streams/groups etc. and other
    dynamic parts of our rendered messages.

    Use this module wherever some Markdown rendered content
    is being displayed.
*/

export function get_user_id_for_mention_button(elem) {
    const user_id_string = $(elem).attr("data-user-id");
    // Handle legacy Markdown that was rendered before we cut
    // over to using data-user-id.
    const email = $(elem).attr("data-user-email");

    if (user_id_string === "*" || email === "*") {
        return "*";
    }

    if (user_id_string) {
        return Number.parseInt(user_id_string, 10);
    }

    if (email) {
        // Will return undefined if there's no match
        const user = people.get_by_email(email);
        if (user) {
            return user.user_id;
        }
    }
    return undefined;
}

function get_user_group_id_for_mention_button(elem) {
    const user_group_id = $(elem).attr("data-user-group-id");

    if (user_group_id) {
        return Number.parseInt(user_group_id, 10);
    }

    return undefined;
}

// Helper function to update a mentioned user's name.
export function set_name_in_mention_element(element, name) {
    if ($(element).hasClass("silent")) {
        $(element).text(name);
    } else {
        $(element).text("@" + name);
    }
}

export const update_elements = ($content) => {
    // Set the rtl class if the text has an rtl direction
    if (rtl.get_direction($content.text()) === "rtl") {
        $content.addClass("rtl");
    }

    $content.find(".user-mention").each(function () {
        const user_id = get_user_id_for_mention_button(this);
        // We give special highlights to the mention buttons
        // that refer to the current user.
        if (user_id === "*" || people.is_my_user_id(user_id)) {
            const $message_header_stream = $content
                .closest(".recipient_row")
                .find(".message_header.message_header_stream");
            // If stream message
            if ($message_header_stream.length) {
                const stream_id = Number.parseInt(
                    $message_header_stream.attr("data-stream-id"),
                    10,
                );
                // Don't highlight the mention if user is not subscribed to the stream.
                if (stream_data.is_user_subscribed(stream_id, people.my_current_user_id())) {
                    // Either a wildcard mention or us, so mark it.
                    $(this).addClass("user-mention-me");
                }
            } else {
                // Always highlight wildcard mentions in direct messages.
                $(this).addClass("user-mention-me");
            }
        }
        if (user_id && user_id !== "*" && !$(this).find(".highlight").length) {
            // If it's a mention of a specific user, edit the
            // mention text to show the user's current name,
            // assuming that you're not searching for text
            // inside the highlight.
            const person = people.maybe_get_user_by_id(user_id, true);
            if (person !== undefined) {
                // Note that person might be undefined in some
                // unpleasant corner cases involving data import.
                set_name_in_mention_element(this, person.full_name);
            }
        }
    });

    $content.find(".user-group-mention").each(function () {
        const user_group_id = get_user_group_id_for_mention_button(this);
        let user_group;
        try {
            user_group = user_groups.get_user_group_from_id(user_group_id);
        } catch {
            // This is a user group the current user doesn't have
            // data on.  This can happen when user groups are
            // deleted.
            blueslip.info("Rendered unexpected user group", {user_group_id});
            return;
        }

        const my_user_id = people.my_current_user_id();
        // Mark user group you're a member of.
        if (user_groups.is_direct_member_of(my_user_id, user_group_id)) {
            $(this).addClass("user-mention-me");
        }

        if (user_group_id && !$(this).find(".highlight").length) {
            // Edit the mention to show the current name for the
            // user group, if its not in search.
            set_name_in_mention_element(this, user_group.name);
        }
    });

    $content.find("a.stream").each(function () {
        const stream_id = Number.parseInt($(this).attr("data-stream-id"), 10);
        if (stream_id && !$(this).find(".highlight").length) {
            // Display the current name for stream if it is not
            // being displayed in search highlight.
            const stream_name = sub_store.maybe_get_stream_name(stream_id);
            if (stream_name !== undefined) {
                // If the stream has been deleted,
                // sub_store.maybe_get_stream_name might return
                // undefined.  Otherwise, display the current stream name.
                $(this).text("#" + stream_name);
            }
        }
    });

    $content.find("a.stream-topic").each(function () {
        const stream_id = Number.parseInt($(this).attr("data-stream-id"), 10);
        if (stream_id && !$(this).find(".highlight").length) {
            // Display the current name for stream if it is not
            // being displayed in search highlight.
            const stream_name = sub_store.maybe_get_stream_name(stream_id);
            if (stream_name !== undefined) {
                // If the stream has been deleted,
                // sub_store.maybe_get_stream_name might return
                // undefined.  Otherwise, display the current stream name.
                const text = $(this).text();
                $(this).text("#" + stream_name + text.slice(text.indexOf(" > ")));
            }
        }
    });

    $content.find("time").each(function () {
        // Populate each timestamp span with mentioned time
        // in user's local time zone.
        const time_str = $(this).attr("datetime");
        if (time_str === undefined) {
            return;
        }

        const timestamp = parseISO(time_str);
        if (isValid(timestamp)) {
            const rendered_timestamp = render_markdown_timestamp({
                text: timerender.format_markdown_time(timestamp),
            });
            $(this).html(rendered_timestamp);
        } else {
            // This shouldn't happen. If it does, we're very interested in debugging it.
            blueslip.error("Could not parse datetime supplied by backend", {time_str});
        }
    });

    $content.find("span.timestamp-error").each(function () {
        const [, time_str] = /^Invalid time format: (.*)$/.exec($(this).text());
        const text = $t(
            {defaultMessage: "Invalid time format: {timestamp}"},
            {timestamp: time_str},
        );
        $(this).text(text);
    });

    $content.find("div.spoiler-header").each(function () {
        // If a spoiler block has no header content, it should have a default header.
        // We do this client side to allow for i18n by the client.
        if ($(this).html().trim().length === 0) {
            $(this).append(`<p>${$t_html({defaultMessage: "Spoiler"})}</p>`);
        }

        // Add the expand/collapse button to spoiler blocks
        const toggle_button_html =
            '<span class="spoiler-button" aria-expanded="false"><span class="spoiler-arrow"></span></span>';
        $(this).prepend(toggle_button_html);
    });

    // Display the view-code-in-playground and the copy-to-clipboard button inside the div.codehilite element.
    $content.find("div.codehilite").each(function () {
        const $codehilite = $(this);
        const $pre = $codehilite.find("pre");
        const fenced_code_lang = $codehilite.data("code-language");
        if (fenced_code_lang !== undefined) {
            const playground_info =
                realm_playground.get_playground_info_for_languages(fenced_code_lang);
            if (playground_info !== undefined) {
                // If a playground is configured for this language,
                // offer to view the code in that playground.  When
                // there are multiple playgrounds, we display a
                // popover listing the options.
                let title = $t({defaultMessage: "View in playground"});
                const $view_in_playground_button = $(view_code_in_playground());
                $pre.prepend($view_in_playground_button);
                if (playground_info.length === 1) {
                    title = $t(
                        {defaultMessage: "View in {playground_name}"},
                        {playground_name: playground_info[0].name},
                    );
                } else {
                    $view_in_playground_button.attr("aria-haspopup", "true");
                }
                $view_in_playground_button.attr("data-tippy-content", title);
                $view_in_playground_button.attr("aria-label", title);
            }
        }
        const $copy_button = $(copy_code_button());
        $pre.prepend($copy_button);
        const clipboard = new ClipboardJS($copy_button[0], {
            text(copy_element) {
                return $(copy_element).siblings("code").text();
            },
        });
        clipboard.on("success", () => {
            show_copied_confirmation($copy_button[0]);
        });
    });

    // Display emoji (including realm emoji) as text if
    // user_settings.emojiset is 'text'.
    if (user_settings.emojiset === "text") {
        $content.find(".emoji").replaceWith(function () {
            const text = $(this).attr("title");
            return ":" + text + ":";
        });
    }
};
