import $ from "jquery";
import assert from "minimalistic-assert";

import render_message_view_header from "../templates/message_view_header.hbs";

import type {Filter} from "./filter";
import * as hash_util from "./hash_util";
import {$t} from "./i18n";
import * as inbox_util from "./inbox_util";
import * as narrow_state from "./narrow_state";
import {page_params} from "./page_params";
import * as peer_data from "./peer_data";
import * as recent_view_util from "./recent_view_util";
import * as rendered_markdown from "./rendered_markdown";
import * as search from "./search";
import {current_user} from "./state_data";
import type {SettingsSubscription} from "./stream_settings_data";
import type {StreamSubscription} from "./sub_store";

type MessageViewHeaderContext = {
    title: string;
    description?: string;
    link?: string;
    is_spectator?: boolean;
    sub_count?: string | number;
    formatted_sub_count?: string;
    rendered_narrow_description?: string;
    is_admin?: boolean;
    stream?: StreamSubscription;
    stream_settings_link?: string;
} & (
    | {
          zulip_icon: string;
      }
    | {
          icon: string | undefined;
      }
);

function get_message_view_header_context(filter: Filter | undefined): MessageViewHeaderContext {
    if (recent_view_util.is_visible()) {
        return {
            title: $t({defaultMessage: "Recent conversations"}),
            description: $t({defaultMessage: "Overview of ongoing conversations."}),
            zulip_icon: "recent",
            link: "/help/recent-conversations",
        };
    }

    if (inbox_util.is_visible()) {
        return {
            title: $t({defaultMessage: "Inbox"}),
            description: $t({
                defaultMessage: "Overview of your conversations with unread messages.",
            }),
            zulip_icon: "inbox",
            link: "/help/inbox",
        };
    }

    // TODO: If we're not in the recent or inbox view, there should be
    // a message feed with a declared filter in the center pane. But
    // because of an initialization order bug, this function gets
    // called with a filter of `undefined` when loading the web app
    // with, say, inbox as the home view.
    //
    // TODO: Refactor this function to move the inbox/recent cases
    // into the caller, and this function can always get a Filter object.
    //
    // TODO: This ideally doesn't need a special case, we can just use
    // `filter.get_description` for it.
    if (filter === undefined || filter.is_in_home()) {
        let description;
        if (page_params.is_spectator) {
            description = $t({
                defaultMessage: "All your messages.",
            });
        } else {
            description = $t({
                defaultMessage: "All your messages except those in muted channels and topics.",
            });
        }
        return {
            title: $t({defaultMessage: "Combined feed"}),
            description,
            zulip_icon: "all-messages",
            link: "/help/combined-feed",
        };
    }

    const title = filter.get_title();
    const description = filter.get_description()?.description;
    const link = filter.get_description()?.link;
    assert(title !== undefined);
    const context = filter.add_icon_data({
        title,
        description,
        link,
        is_spectator: page_params.is_spectator,
    });

    if (filter.has_operator("channel") && !filter._sub) {
        return {
            ...context,
            sub_count: "0",
            formatted_sub_count: "0",
            rendered_narrow_description: $t({
                defaultMessage: "This channel does not exist or is private.",
            }),
        };
    }

    if (filter._sub) {
        // We can now be certain that the narrow
        // involves a stream which exists and
        // the current user can access.
        const current_stream = filter._sub;
        const sub_count = peer_data.get_subscriber_count(current_stream.stream_id);
        return {
            ...context,
            is_admin: current_user.is_admin,
            rendered_narrow_description: current_stream.rendered_description,
            sub_count,
            stream: current_stream,
            stream_settings_link: hash_util.channels_settings_edit_url(current_stream, "general"),
        };
    }

    return context;
}

export function colorize_message_view_header(): void {
    const filter = narrow_state.filter();
    if (filter === undefined || !filter._sub) {
        return;
    }
    // selecting i instead of .fa because web public streams have custom icon.
    $("#message_view_header a.stream i").css("color", filter._sub.color);
}

function append_and_display_title_area(context: MessageViewHeaderContext): void {
    const $message_view_header_elem = $("#message_view_header");
    $message_view_header_elem.html(render_message_view_header(context));
    if (context.stream_settings_link) {
        colorize_message_view_header();
    }
    $message_view_header_elem.removeClass("notdisplayed");
    const $content = $message_view_header_elem.find("span.rendered_markdown");
    if ($content) {
        // Update syntax like stream names, emojis, mentions, timestamps.
        rendered_markdown.update_elements($content);
    }
}

function build_message_view_header(filter: Filter | undefined): void {
    // This makes sure we don't waste time appending
    // message_view_header on a template where it's never used
    if (filter && !filter.is_common_narrow()) {
        search.open_search_bar_and_close_narrow_description();
    } else {
        const context = get_message_view_header_context(filter);
        append_and_display_title_area(context);
        search.close_search_bar_and_open_narrow_description();
    }
}

export function initialize(): void {
    render_title_area();
}

export function render_title_area(): void {
    const filter = narrow_state.filter();
    build_message_view_header(filter);
}

// This function checks if "modified_sub" which is the stream whose values
// have been updated is the same as the stream which is currently
// narrowed (filter._sub) and rerenders if necessary
export function maybe_rerender_title_area_for_stream(modified_sub: SettingsSubscription): void {
    const filter = narrow_state.filter();
    if (filter && filter._sub && filter._sub.stream_id === modified_sub.stream_id) {
        render_title_area();
    }
}
