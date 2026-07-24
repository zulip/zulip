import $ from "jquery";
import assert from "minimalistic-assert";

import render_message_view_header from "../templates/message_view_header.hbs";

import * as buddy_data from "./buddy_data.ts";
import type {Filter} from "./filter.ts";
import * as hash_util from "./hash_util.ts";
import {$t} from "./i18n.ts";
import * as inbox_util from "./inbox_util.ts";
import * as muted_users from "./muted_users.ts";
import * as narrow_state from "./narrow_state.ts";
import {page_params} from "./page_params.ts";
import * as peer_data from "./peer_data.ts";
import * as people from "./people.ts";
import * as recent_view_util from "./recent_view_util.ts";
import * as rendered_markdown from "./rendered_markdown.ts";
import * as search from "./search.ts";
import {current_user} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import type {StreamSubscription} from "./sub_store.ts";
import * as util from "./util.ts";

// Cap on the number of names listed in the "+N" overflow tooltip,
// matching recent_view_ui's participant overflow tooltip.
const MAX_DM_OVERFLOW_TOOLTIP_NAMES = 10;

type DmAvatar = {
    user_id: number;
    avatar_url: string;
    name: string;
    is_muted: boolean;
    user_circle_class: string;
};

type DmAvatarsContext = {
    is_dm_narrow: true;
    is_one_on_one_dm: boolean;
    dm_users: DmAvatar[];
};

type MessageViewHeaderContext = {
    title?: string | undefined;
    title_html?: string | undefined;
    description?: string;
    link?: string;
    is_spectator?: boolean;
    sub_count?: string | number;
    formatted_sub_count?: string;
    rendered_narrow_description?: string;
    is_admin?: boolean;
    stream?: StreamSubscription;
    stream_settings_link?: string;
    is_dm_narrow?: boolean;
    is_one_on_one_dm?: boolean;
    dm_users?: DmAvatar[];
} & (
    | {
          zulip_icon: string;
      }
    | {
          icon: string | undefined;
      }
);

export function get_dm_avatars_context(user_ids: number[]): DmAvatarsContext {
    // Order avatars by display name so they match the participant order
    // shown in the message recipient header bar (see
    // message_store.get_pm_full_names, which sorts the same way). We
    // render an avatar for every participant; how many actually fit is
    // decided responsively at layout time (see relayout_dm_avatars).
    const strcmp = util.make_strcmp();
    const sorted_user_ids = user_ids.toSorted((a, b) =>
        strcmp(people.get_display_full_name(a), people.get_display_full_name(b)),
    );

    const dm_users = sorted_user_ids.map((user_id) => {
        const person = people.get_by_user_id(user_id);
        return {
            user_id,
            avatar_url: people.small_avatar_url_for_person(person),
            name: people.get_display_full_name(user_id),
            is_muted: muted_users.is_user_muted(user_id),
            user_circle_class: buddy_data.get_user_circle_class(
                user_id,
                !people.is_active_user_or_system_bot(user_id),
            ),
        };
    });

    return {
        is_dm_narrow: true,
        is_one_on_one_dm: user_ids.length === 1,
        dm_users,
    };
}

function get_message_view_header_context(filter: Filter | undefined): MessageViewHeaderContext {
    if (recent_view_util.is_visible()) {
        return {
            title: $t({defaultMessage: "Recent conversations"}),
            description: $t({defaultMessage: "Overview of ongoing conversations."}),
            zulip_icon: "recent",
            link: "/help/recent-conversations",
        };
    }

    if (inbox_util.is_visible() && !inbox_util.is_channel_view()) {
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

    if (filter.has_operator("channel")) {
        const current_stream = stream_data.get_sub_by_id_string(
            filter.terms_with_operator("channel")[0]!.operand,
        );
        if (!current_stream) {
            return {
                ...context,
                sub_count: "0",
                formatted_sub_count: "0",
                rendered_narrow_description: $t({
                    defaultMessage: "This channel does not exist or is private.",
                }),
            };
        }

        // We can now be certain that the narrow
        // involves a stream which exists and
        // the current user can access.
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

    if (filter.has_operator("dm")) {
        const user_ids = filter.terms_with_operator("dm")[0]!.operand;
        if (user_ids.length > 0) {
            return {
                ...context,
                ...get_dm_avatars_context(user_ids),
            };
        }
    }

    return context;
}

export function colorize_message_view_header(): void {
    const current_sub = narrow_state.stream_sub();
    if (!current_sub) {
        return;
    }
    $("#message_view_header .navbar-icon").css("color", current_sub.color);
}

let dm_avatars_resize_observer: ResizeObserver | undefined;

function disconnect_dm_avatars_resize_observer(): void {
    if (dm_avatars_resize_observer !== undefined) {
        dm_avatars_resize_observer.disconnect();
        dm_avatars_resize_observer = undefined;
    }
}

// Show as many DM participant avatars as fit the navbar, collapsing the
// rest into a "+N" indicator whose tooltip lists the hidden users. This
// runs on every navbar resize; see setup_dm_avatars_overflow.
function relayout_dm_avatars(): void {
    const header = $("#message_view_header")[0];
    const container = $("#message_view_header .navbar-dm-avatars")[0];
    if (!(header instanceof HTMLElement) || !(container instanceof HTMLElement)) {
        return;
    }
    const avatars = [...container.querySelectorAll<HTMLElement>(".navbar-dm-avatar")];
    const overflow = container.querySelector<HTMLElement>(".navbar-dm-avatar-overflow");
    const names_template = container.querySelector<HTMLTemplateElement>(
        "template.navbar-dm-avatar-overflow-names",
    );
    if (avatars.length === 0 || overflow === null || names_template === null) {
        return;
    }

    // Start from the natural layout so we measure true widths: every
    // avatar visible, the "+N" indicator hidden.
    for (const avatar of avatars) {
        avatar.classList.remove("hidden");
    }
    overflow.classList.add("hidden");

    const gap = Number.parseFloat(window.getComputedStyle(container).columnGap) || 0;
    const available = header.getBoundingClientRect().right - container.getBoundingClientRect().left;

    let total_width = 0;
    for (const [i, avatar] of avatars.entries()) {
        total_width += avatar.offsetWidth + (i > 0 ? gap : 0);
    }
    if (total_width <= available) {
        // Every avatar fits.
        return;
    }

    // Reserve room for the "+N" indicator, using the widest count so the
    // reservation can't be undersized, then fit as many avatars as we can.
    overflow.classList.remove("hidden");
    overflow.textContent = `+${avatars.length}`;
    const reserved = overflow.offsetWidth + gap;

    let used = 0;
    let shown = 0;
    for (const [i, avatar] of avatars.entries()) {
        const width = avatar.offsetWidth + (i > 0 ? gap : 0);
        if (used + width + reserved <= available) {
            used += width;
            shown += 1;
        } else {
            break;
        }
    }

    shown = Math.max(shown, 1);

    for (const [i, avatar] of avatars.entries()) {
        avatar.classList.toggle("hidden", i >= shown);
    }

    const hidden_avatars = avatars.slice(shown);
    overflow.textContent = `+${hidden_avatars.length}`;

    const listed = hidden_avatars.slice(0, MAX_DM_OVERFLOW_TOOLTIP_NAMES);
    const remaining = hidden_avatars.length - listed.length;
    names_template.content.replaceChildren();
    for (const avatar of listed) {
        const chip = document.createElement("span");
        chip.className = "navbar-dm-avatar-overflow-name";
        chip.textContent = avatar.dataset["fullName"] ?? "";
        names_template.content.append(chip);
    }
    if (remaining > 0) {
        const more = document.createElement("span");
        more.className = "navbar-dm-avatar-overflow-more";
        more.textContent = $t(
            {defaultMessage: "and {remaining, plural, one {1 other} other {# others}}"},
            {remaining},
        );
        names_template.content.append(more);
    }
}

function setup_dm_avatars_overflow(context: MessageViewHeaderContext): void {
    disconnect_dm_avatars_resize_observer();
    if (!context.is_dm_narrow) {
        return;
    }
    const header = $("#message_view_header")[0];
    if (!(header instanceof HTMLElement)) {
        return;
    }
    dm_avatars_resize_observer = new ResizeObserver(() => {
        relayout_dm_avatars();
    });
    dm_avatars_resize_observer.observe(header);
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
    setup_dm_avatars_overflow(context);
}

function build_message_view_header(filter: Filter | undefined): void {
    // This makes sure we don't waste time appending
    // message_view_header on a template where it's never used
    if (filter && !filter.is_common_narrow()) {
        // Leaving a DM narrow for a search view; stop watching for
        // avatar overflow.
        disconnect_dm_avatars_resize_observer();
        search.open_search_bar_and_close_narrow_description();
    } else {
        const context = get_message_view_header_context(filter);
        append_and_display_title_area(context);
        search.close_search();
    }
}

export function initialize(): void {
    render_title_area();

    const hide_stream_settings_button_width_threshold = 620;
    $("body").on("mouseenter mouseleave", ".narrow_description", function (event) {
        const $view_description_elt = $(this);
        const window_width = $(window).width()!;
        let hover_timeout;

        if (event.type === "mouseenter") {
            if (!$view_description_elt.hasClass("view-description-extended")) {
                const current_width = $view_description_elt.outerWidth();
                // Set fixed width for word-wrap to work
                $view_description_elt.css("width", current_width + "px");
            }
            hover_timeout = setTimeout(() => {
                $view_description_elt.addClass("view-description-extended");
                $(".top-navbar-container").addClass(
                    "top-navbar-container-allow-description-extension",
                );

                if (window_width <= hide_stream_settings_button_width_threshold) {
                    $(".message-header-stream-settings-button").hide();
                    // Let it expand naturally on smaller screens
                    $view_description_elt.css("width", "");
                }
            }, 250);
            $view_description_elt.data("hover_timeout", hover_timeout);
        } else if (event.type === "mouseleave") {
            // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
            hover_timeout = $view_description_elt.data("hover_timeout");
            if (typeof hover_timeout === "number") {
                // Clear any pending hover_timeout to prevent unexpected behavior
                clearTimeout(hover_timeout);
            }
            $view_description_elt.addClass("leaving-extended-view-description");

            // Wait for the reverse animation duration before cleaning up
            setTimeout(() => {
                $view_description_elt.removeClass("view-description-extended");
                $view_description_elt.removeClass("leaving-extended-view-description");
                if (window_width <= hide_stream_settings_button_width_threshold) {
                    $(".message-header-stream-settings-button").show();
                    $view_description_elt.css("width", "");
                } else {
                    // Reset to flexbox-determined width
                    $view_description_elt.css("width", "");
                }
            }, 100);
        }
    });
}

export function render_title_area(): void {
    const filter = narrow_state.filter();
    build_message_view_header(filter);
}

// This function checks if "modified_sub" which is the stream whose values
// have been updated is the same as the stream which is currently
// narrowed and rerenders if necessary
export function maybe_rerender_title_area_for_stream(modified_stream_id: number): void {
    const current_stream_id = narrow_state.stream_id();

    if (current_stream_id === modified_stream_id) {
        render_title_area();
    }
}

// The navbar title shows a user's name when narrowed to a DM that
// includes them or to messages sent by them, so we refresh it for a
// rename of such a user.
export function maybe_update_navbar_title_for_user(modified_user_id: number): void {
    const filter = narrow_state.filter();
    if (filter === undefined) {
        return;
    }
    // Only common narrows show a name in the title; others show a search
    // bar and have no title to update.
    if (!filter.is_common_narrow()) {
        return;
    }
    const narrowed_to_dm_with_user = narrow_state.pm_ids_set(filter).has(modified_user_id);
    const sender_id = filter.terms_with_operator("sender")[0]?.operand;
    const narrowed_to_messages_sent_by_user = sender_id === modified_user_id;

    if (narrowed_to_dm_with_user || narrowed_to_messages_sent_by_user) {
        // Update just the title text rather than rebuilding the whole
        // header with render_title_area(), which would close or reset a
        // search bar the user has open to refine the narrow. For these
        // narrows the title is plain text and the icon doesn't depend on
        // the renamed user. For a 1:1 DM this refreshes the name shown
        // next to the avatar; group DMs render no name here, so it's a
        // no-op for them.
        const title = filter.get_title();
        assert(title !== undefined);
        $("#message_view_header .message-header-navbar-title").text(title);
    }
}
