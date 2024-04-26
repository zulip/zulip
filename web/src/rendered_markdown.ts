import ClipboardJS from "clipboard";
import {isValid, parseISO} from "date-fns";
import $ from "jquery";
import assert from "minimalistic-assert";

import code_buttons_container from "../templates/code_buttons_container.hbs";
import render_markdown_timestamp from "../templates/markdown_timestamp.hbs";

import * as blueslip from "./blueslip";
import {show_copied_confirmation} from "./copied_tooltip";
import {$t} from "./i18n";
import * as message_store from "./message_store";
import type {Message} from "./message_store";
import * as people from "./people";
import * as realm_playground from "./realm_playground";
import * as rows from "./rows";
import * as rtl from "./rtl";
import * as sub_store from "./sub_store";
import * as timerender from "./timerender";
import * as user_groups from "./user_groups";
import {user_settings} from "./user_settings";
import * as util from "./util";

/*
    rendered_markdown

    This module provides a single function 'update_elements' to
    update any renamed users/streams/groups etc. and other
    dynamic parts of our rendered messages.

    Use this module wherever some Markdown rendered content
    is being displayed.
*/

export function get_user_id_for_mention_button(elem: HTMLElement): "*" | number | undefined {
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

function get_user_group_id_for_mention_button(elem: HTMLElement): number {
    const user_group_id = $(elem).attr("data-user-group-id");
    assert(user_group_id !== undefined);
    return Number.parseInt(user_group_id, 10);
}

function get_message_for_message_content($content: JQuery): Message | undefined {
    // TODO: This selector is designed to exclude drafts/scheduled
    // messages. Arguably those settings should be unconditionally
    // marked with user-mention-me, but rows.id doesn't support
    // those elements, and we should address that quirk for
    // mentions holistically.
    const $message_row = $content.closest(".message_row");
    if (!$message_row.length || $message_row.closest(".overlay-message-row").length) {
        // There's no containing message when rendering a preview.
        return undefined;
    }
    const message_id = rows.id($message_row);
    return message_store.get(message_id);
}

// Helper function to update a mentioned user's name.
export function set_name_in_mention_element(
    element: HTMLElement,
    name: string,
    user_id?: number,
): void {
    if (user_id !== undefined && people.should_add_guest_user_indicator(user_id)) {
        let display_text;
        if (!$(element).hasClass("silent")) {
            display_text = $t({defaultMessage: "@{name} (guest)"}, {name});
        } else {
            display_text = $t({defaultMessage: "{name} (guest)"}, {name});
        }
        $(element).text(display_text);
        return;
    }

    if ($(element).hasClass("silent")) {
        $(element).text(name);
    } else {
        $(element).text("@" + name);
    }
}

export const update_elements = ($content: JQuery): void => {
    // Set the rtl class if the text has an rtl direction
    if (rtl.get_direction($content.text()) === "rtl") {
        $content.addClass("rtl");
    }

    if (util.is_client_safari()) {
        // Without this video thumbnail doesn't load on Safari.
        $content.find<HTMLMediaElement>(".message_inline_video video").each(function () {
            // On Safari, one needs to manually load video elements.
            // https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/load
            this.load();
        });
    }

    // personal and stream wildcard mentions
    $content.find(".user-mention").each(function (): void {
        const user_id = get_user_id_for_mention_button(this);
        const message = get_message_for_message_content($content);
        // We give special highlights to the mention buttons
        // that refer to the current user.
        if (user_id === "*" && message && message.stream_wildcard_mentioned) {
            $(this).addClass("user-mention-me");
        }
        if (
            user_id !== undefined &&
            user_id !== "*" &&
            people.is_my_user_id(user_id) &&
            message &&
            message.mentioned_me_directly
        ) {
            $(this).addClass("user-mention-me");
        }

        if (user_id && user_id !== "*" && !$(this).find(".highlight").length) {
            // If it's a mention of a specific user, edit the mention
            // text to show the user's current name, assuming that
            // you're not searching for text inside the highlight.
            const person = people.maybe_get_user_by_id(user_id, true);
            if (person === undefined || person.is_inaccessible_user) {
                // Note that person might be undefined in some
                // unpleasant corner cases involving data import
                // or when guest users cannot access all users in
                // the organization.
                //
                // In these cases, the best we can do is leave the
                // existing name in the existing mention pill
                // HTML. Clicking on the pill will show the the
                // "Unknown user" popover.
                if (person === undefined) {
                    people.add_inaccessible_user(user_id);
                }
                return;
            }

            set_name_in_mention_element(this, person.full_name, user_id);
        }
    });

    $content.find(".topic-mention").each(function (): void {
        const message = get_message_for_message_content($content);

        if (message && message.topic_wildcard_mentioned) {
            $(this).addClass("user-mention-me");
        }
    });

    $content.find(".user-group-mention").each(function (): void {
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

    $content.find("a.stream").each(function (): void {
        const stream_id_string = $(this).attr("data-stream-id");
        assert(stream_id_string !== undefined);
        const stream_id = Number.parseInt(stream_id_string, 10);
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

    $content.find("a.stream-topic").each(function (): void {
        const stream_id_string = $(this).attr("data-stream-id");
        assert(stream_id_string !== undefined);
        const stream_id = Number.parseInt(stream_id_string, 10);
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

    $content.find("time").each(function (): void {
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

    $content.find("span.timestamp-error").each(function (): void {
        const match_array = /^Invalid time format: (.*)$/.exec($(this).text());
        assert(match_array !== null);
        const [, time_str] = match_array;
        const text = $t(
            {defaultMessage: "Invalid time format: {timestamp}"},
            {timestamp: time_str},
        );
        $(this).text(text);
    });

    $content.find("div.spoiler-header").each(function (): void {
        // If a spoiler block has no header content, it should have a default header.
        // We do this client side to allow for i18n by the client.
        if ($(this).html().trim().length === 0) {
            $(this).append($("<p>").text($t({defaultMessage: "Spoiler"})));
        }

        // Add the expand/collapse button to spoiler blocks
        const toggle_button_html =
            '<span class="spoiler-button" aria-expanded="false"><span class="spoiler-arrow"></span></span>';
        $(this).append($(toggle_button_html));
    });

    // Display the view-code-in-playground and the copy-to-clipboard button inside the div.codehilite element,
    // and add a `zulip-code-block` class to it to detect it easily in `copy_and_paste.js`.
    $content.find("div.codehilite").each(function (): void {
        const $codehilite = $(this);
        const $pre = $codehilite.find("pre");
        const fenced_code_lang = $codehilite.attr("data-code-language");
        let playground_info;
        if (fenced_code_lang !== undefined) {
            playground_info = realm_playground.get_playground_info_for_languages(fenced_code_lang);
        }
        const show_playground_button =
            fenced_code_lang !== undefined && playground_info !== undefined;

        const $buttonContainer = $(code_buttons_container({show_playground_button}));
        $pre.prepend($buttonContainer);

        if (show_playground_button) {
            // If a playground is configured for this language,
            // offer to view the code in that playground.  When
            // there are multiple playgrounds, we display a
            // popover listing the options.
            let title = $t({defaultMessage: "View in playground"});
            const $view_in_playground_button = $buttonContainer.find(".code_external_link");
            if (playground_info && playground_info.length === 1) {
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
        const $copy_button = $buttonContainer.find(".copy_codeblock");
        const clipboard = new ClipboardJS($copy_button[0], {
            text(copy_element) {
                const $code = $(copy_element).parent().siblings("code");
                return $code.text();
            },
        });

        clipboard.on("success", () => {
            show_copied_confirmation($copy_button[0]);
        });
        $codehilite.addClass("zulip-code-block");
    });

    // Display emoji (including realm emoji) as text if
    // user_settings.emojiset is 'text'.
    if (user_settings.emojiset === "text") {
        $content
            .find(".emoji")
            .text(function () {
                const text = $(this).attr("title");
                return ":" + text + ":";
            })
            .contents()
            .unwrap();
    }
};
