import $ from "jquery";
import assert from "minimalistic-assert";
import * as tippy from "tippy.js";

import render_filter_topics from "../templates/filter_topics.hbs";
import render_go_to_channel_feed_tooltip from "../templates/go_to_channel_feed_tooltip.hbs";
import render_go_to_channel_list_of_topics_tooltip from "../templates/go_to_channel_list_of_topics_tooltip.hbs";
import render_show_inactive_or_muted_channels from "../templates/show_inactive_or_muted_channels.hbs";
import render_stream_list_section_container from "../templates/stream_list_section_container.hbs";
import render_stream_privacy from "../templates/stream_privacy.hbs";
import render_stream_sidebar_row from "../templates/stream_sidebar_row.hbs";
import render_subscribe_to_more_streams from "../templates/subscribe_to_more_streams.hbs";

import * as blueslip from "./blueslip.ts";
import * as browser_history from "./browser_history.ts";
import * as channel_folders from "./channel_folders.ts";
import * as compose_actions from "./compose_actions.ts";
import type {Filter} from "./filter.ts";
import * as hash_util from "./hash_util.ts";
import * as left_sidebar_navigation_area from "./left_sidebar_navigation_area.ts";
import * as narrow_state from "./narrow_state.ts";
import * as pm_list from "./pm_list.ts";
import * as popovers from "./popovers.ts";
import * as scroll_util from "./scroll_util.ts";
import {web_channel_default_view_values} from "./settings_config.ts";
import * as settings_data from "./settings_data.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_list_sort from "./stream_list_sort.ts";
import type {StreamListSection} from "./stream_list_sort.ts";
import * as stream_topic_history from "./stream_topic_history.ts";
import * as stream_topic_history_util from "./stream_topic_history_util.ts";
import * as sub_store from "./sub_store.ts";
import type {StreamSubscription} from "./sub_store.ts";
import {LONG_HOVER_DELAY} from "./tippyjs.ts";
import * as topic_list from "./topic_list.ts";
import * as topic_list_data from "./topic_list_data.ts";
import * as ui_util from "./ui_util.ts";
import * as unread from "./unread.ts";
import type {FullUnreadCountsData, StreamCountInfo} from "./unread.ts";
import {user_settings} from "./user_settings.ts";
import * as user_topics from "./user_topics.ts";

let pending_stream_list_rerender = false;
let zoomed_in = false;
let update_inbox_channel_view_callback: (channel_id: number) => void;

export function set_update_inbox_channel_view_callback(value: (channel_id: number) => void): void {
    update_inbox_channel_view_callback = value;
}

let has_scrolled = false;

const collapsed_sections = new Set<string>();
const sections_showing_inactive_or_muted = new Set<string>();

export function is_zoomed_in(): boolean {
    return zoomed_in;
}

function zoom_in(): void {
    const stream_id = topic_list.active_stream_id();

    popovers.hide_all();
    pm_list.close();
    topic_list.zoom_in();
    zoom_in_topics({
        stream_id,
    });

    zoomed_in = true;
}

export function set_pending_stream_list_rerender(value: boolean): void {
    pending_stream_list_rerender = value;
}

export function zoom_out(): void {
    if (pending_stream_list_rerender) {
        update_streams_sidebar(true);
    }
    const $stream_li = topic_list.get_stream_li();

    popovers.hide_all();
    topic_list.zoom_out();
    zoom_out_topics();

    if ($stream_li) {
        scroll_stream_into_view($stream_li);
    }

    zoomed_in = false;
}

export function clear_topics(): void {
    const $stream_li = topic_list.get_stream_li();

    topic_list.close();

    if (zoomed_in) {
        zoom_out_topics();

        if ($stream_li) {
            scroll_stream_into_view($stream_li);
        }
    }

    zoomed_in = false;
}

export let update_count_in_dom = (
    $stream_li: JQuery,
    stream_counts: StreamCountInfo,
    stream_has_any_unread_mention_messages: boolean,
    stream_has_any_unmuted_unread_mention: boolean,
    stream_has_only_muted_unread_mention: boolean,
): void => {
    // The subscription_block properly excludes the topic list,
    // and it also has sensitive margins related to whether the
    // count is there or not.
    const $subscription_block = $stream_li.find(".subscription_block");

    ui_util.update_unread_mention_info_in_dom(
        $subscription_block,
        stream_has_any_unread_mention_messages,
    );

    if (stream_has_any_unmuted_unread_mention) {
        $subscription_block.addClass("has-unmuted-mentions");
        $subscription_block.removeClass("has-only-muted-mentions");
    } else {
        $subscription_block.removeClass("has-unmuted-mentions");
        if (!stream_counts.stream_is_muted && stream_has_only_muted_unread_mention) {
            $subscription_block.addClass("has-only-muted-mentions");
        } else {
            $subscription_block.removeClass("has-only-muted-mentions");
        }
    }

    // Here we set the count and compute the values of two classes:
    // .stream-with-count is used for the layout CSS to know whether
    // to leave space for the unread count, and has-unmuted-unreads is
    // used in muted streams to set the fading correctly to indicate
    // those are unread
    if (stream_counts.unmuted_count > 0 && !stream_counts.stream_is_muted) {
        // Normal stream, has unmuted unreads; display normally.
        ui_util.update_unread_count_in_dom($subscription_block, stream_counts.unmuted_count);
        $subscription_block.addClass("stream-with-count");
        $subscription_block.removeClass("has-unmuted-unreads");
        $subscription_block.removeClass("has-only-muted-unreads");
    } else if (stream_counts.unmuted_count > 0 && stream_counts.stream_is_muted) {
        // Muted stream, has unmuted unreads.
        ui_util.update_unread_count_in_dom($subscription_block, stream_counts.unmuted_count);
        $subscription_block.addClass("stream-with-count");
        $subscription_block.addClass("has-unmuted-unreads");
        $subscription_block.removeClass("has-only-muted-unreads");
    } else if (stream_counts.muted_count > 0 && stream_counts.stream_is_muted) {
        // Muted stream, only muted unreads.
        ui_util.update_unread_count_in_dom($subscription_block, stream_counts.muted_count);
        $subscription_block.addClass("stream-with-count");
        $subscription_block.removeClass("has-unmuted-unreads");
        $subscription_block.removeClass("has-only-muted-unreads");
    } else if (
        stream_counts.muted_count > 0 &&
        !stream_counts.stream_is_muted &&
        stream_has_only_muted_unread_mention
    ) {
        // Normal stream, only muted unreads, including a mention:
        // Display the mention, faded, and a faded unread count too,
        // so that we don't weirdly show the mention indication
        // without an unread count.
        ui_util.update_unread_count_in_dom($subscription_block, stream_counts.muted_count);
        $subscription_block.removeClass("has-unmuted-unreads");
        $subscription_block.addClass("stream-with-count");
        $subscription_block.addClass("has-only-muted-unreads");
    } else if (stream_counts.muted_count > 0 && !stream_counts.stream_is_muted) {
        // Normal stream, only muted unreads: display nothing. The
        // current thinking is displaying those counts with muted
        // styling would be more distracting than helpful.
        ui_util.update_unread_count_in_dom($subscription_block, 0);
        $subscription_block.removeClass("has-unmuted-unreads");
        $subscription_block.removeClass("stream-with-count");
    } else {
        // No unreads: display nothing.
        ui_util.update_unread_count_in_dom($subscription_block, 0);
        $subscription_block.removeClass("has-unmuted-unreads");
        $subscription_block.removeClass("has-only-muted-unreads");
        $subscription_block.removeClass("stream-with-count");
    }

    toggle_hide_unread_counts(
        $subscription_block,
        stream_counts.stream_is_muted,
        stream_counts.unmuted_count,
    );
};

export function rewire_update_count_in_dom(value: typeof update_count_in_dom): void {
    update_count_in_dom = value;
}

class StreamSidebar {
    rows = new Map<number, StreamSidebarRow>(); // stream id -> row widget

    set_row(stream_id: number, widget: StreamSidebarRow): void {
        this.rows.set(stream_id, widget);
    }

    get_row(stream_id: number): StreamSidebarRow | undefined {
        return this.rows.get(stream_id);
    }

    has_row_for(stream_id: number): boolean {
        return this.rows.has(stream_id);
    }

    remove_row(stream_id: number): void {
        // This only removes the row from our data structure.
        // Our caller should use build_stream_list() to re-draw
        // the sidebar, so that we don't have to deal with edge
        // cases like removing the last pinned stream (and removing
        // the divider).

        this.rows.delete(stream_id);
    }
}
export const stream_sidebar = new StreamSidebar();

export function add_sidebar_row(sub: StreamSubscription): void {
    create_sidebar_row(sub);
    update_streams_sidebar();
}

export function remove_sidebar_row(stream_id: number): void {
    stream_sidebar.remove_row(stream_id);
    const force_rerender = stream_id === topic_list.active_stream_id();
    update_streams_sidebar(force_rerender);
}

export function create_initial_sidebar_rows(force_rerender = false): void {
    // This code is slightly opaque, but it ends up building
    // up list items and attaching them to the "sub" data
    // structures that are kept in stream_data.js.
    let subs = stream_data.subscribed_subs();
    subs = subs.filter((sub) => !sub.is_archived);

    for (const sub of subs) {
        create_sidebar_row(sub, force_rerender);
    }
}

export let stream_list_section_container_html = function (
    section: StreamListSection,
    can_create_streams: boolean,
): string {
    return render_stream_list_section_container({
        id: section.id,
        section_title: section.section_title,
        plus_icon_url: can_create_streams ? get_section_channel_plus_icon_url(section) : undefined,
    });
};

export function rewire_stream_list_section_container_html(
    value: typeof stream_list_section_container_html,
): void {
    stream_list_section_container_html = value;
}

function get_section_channel_plus_icon_url(section: StreamListSection): string | undefined {
    if (section.folder_id !== null) {
        return `#channels/folders/${section.folder_id}/new`;
    } else if (section.id === "normal-streams") {
        return "#channels/new";
    }
    return undefined;
}

export function update_unread_counts_visibility(): void {
    const hidden = !user_settings.web_left_sidebar_unreads_count_summary;
    $(".top_left_row, #left-sidebar-navigation-list-condensed").toggleClass(
        "hide-unread-messages-count",
        hidden,
    );
    // Note: Channel folder count visibilities are handled in
    // `update_section_unread_count`, since they depend on unread counts.
}

function maybe_change_channel_folders_option_visibility(): void {
    const $channel_folders_sidebar_option = $(
        "#left-sidebar-search .channel-folders-sidebar-menu-icon",
    );
    if (channel_folders.user_has_folders()) {
        $channel_folders_sidebar_option.show();
    } else {
        $channel_folders_sidebar_option.hide();
    }
}

export function build_stream_list(force_rerender: boolean): void {
    // The stream list in the left sidebar contains 3 sections:
    // pinned, normal, and dormant streams, with headings above them
    // as appropriate.
    //
    // Within the first two sections, muted streams are sorted to the
    // bottom; we skip that for dormant streams to simplify discovery.
    //
    // The main logic to build the list is in stream_list_sort.ts
    const streams = stream_data.subscribed_stream_ids();
    const stream_groups = stream_list_sort.sort_groups(
        streams,
        ui_util.get_left_sidebar_search_term(),
    );

    if (stream_groups.same_as_before && !force_rerender) {
        return;
    }

    maybe_change_channel_folders_option_visibility();

    function add_sidebar_li(stream_id: number, $list: JQuery, inactive_or_muted = false): void {
        const sidebar_row = stream_sidebar.get_row(stream_id);
        assert(sidebar_row !== undefined);
        sidebar_row.update_whether_active();
        const $li = sidebar_row.get_li();
        if (inactive_or_muted) {
            $li.addClass("inactive-or-muted-in-channel-folder");
        }
        $list.append($li);
    }

    clear_topics();
    $("#stream_filters").empty();
    const can_create_streams =
        settings_data.user_can_create_private_streams() ||
        settings_data.user_can_create_public_streams() ||
        settings_data.user_can_create_web_public_streams();
    for (const section of stream_groups.sections) {
        $("#stream_filters").append(
            $(stream_list_section_container_html(section, can_create_streams)),
        );
        const is_empty =
            section.streams.length === 0 &&
            section.muted_streams.length === 0 &&
            section.inactive_streams.length === 0;
        $(`#stream-list-${section.id}-container`).toggleClass("no-display", is_empty);

        for (const stream_id of section.streams) {
            add_sidebar_li(stream_id, $(`#stream-list-${section.id}`));
        }
        const muted_and_inactive_streams = [...section.muted_streams, ...section.inactive_streams];
        if (section.id !== "pinned-streams" && muted_and_inactive_streams.length > 0) {
            $(`#stream-list-${section.id}`).append(
                $(
                    render_show_inactive_or_muted_channels({
                        inactive_or_muted_count: muted_and_inactive_streams.length,
                    }),
                ),
            );
        }
        for (const stream_id of muted_and_inactive_streams) {
            add_sidebar_li(
                stream_id,
                $(`#stream-list-${section.id}`),
                section.id !== "pinned-streams",
            );
        }
    }

    // Rerendering can moving channels between folders and change heading unread counts.
    const counts = unread.get_counts();
    left_sidebar_navigation_area.update_dom_with_unread_counts(counts, false);
    update_dom_with_unread_counts(counts);
    update_stream_section_mention_indicators();
    update_unread_counts_visibility();
    set_sections_states();
    // Show inactive channels when user starts typing.
    $("#streams_list").toggleClass("is_searching", ui_util.get_left_sidebar_search_term() !== "");
}

export function mention_counts_by_section(): Map<
    string,
    {
        has_mentions: boolean;
        has_unmuted_mentions: boolean;
    }
> {
    const mentions_map = new Map<
        string,
        {
            has_mentions: boolean;
            has_unmuted_mentions: boolean;
        }
    >();
    const streams_with_mentions = unread.get_channels_with_unread_mentions();
    const streams_with_unmuted_mentions = unread.get_channels_with_unmuted_mentions();
    for (const stream_id of streams_with_mentions) {
        const section_id = stream_list_sort.current_section_id_for_stream(stream_id);
        if (section_id === undefined) {
            continue;
        }
        if (!mentions_map.has(section_id)) {
            mentions_map.set(section_id, {
                has_mentions: false,
                has_unmuted_mentions: false,
            });
        }
        mentions_map.get(section_id)!.has_mentions = true;
    }
    for (const stream_id of streams_with_unmuted_mentions) {
        const section_id = stream_list_sort.current_section_id_for_stream(stream_id);
        if (section_id === undefined) {
            continue;
        }
        mentions_map.get(section_id)!.has_unmuted_mentions = true;
    }

    return mentions_map;
}

export let update_stream_section_mention_indicators = function (): void {
    const mentions = mention_counts_by_section();
    for (const section of stream_list_sort.section_ids()) {
        const $header = $(`#stream-list-${section}-container .stream-list-subsection-header`);
        const mentions_for_section = mentions.get(section) ?? {
            has_mentions: false,
            has_unmuted_mentions: false,
        };
        ui_util.update_unread_mention_info_in_dom($header, mentions_for_section.has_mentions);

        $header.toggleClass(
            "has-only-muted-mentions",
            mentions_for_section.has_mentions && !mentions_for_section.has_unmuted_mentions,
        );
    }
};

export function rewire_update_stream_section_mention_indicators(
    value: typeof update_stream_section_mention_indicators,
): void {
    update_stream_section_mention_indicators = value;
}

/* When viewing a channel in a collapsed folder, we show that active
   highlighted channel in the left sidebar even though the folder is
   collapsed. If there's an active highlighted topic within the
   channel, we show it too. If there's no highlighted topic within the
   channel, then we should treat this like an empty topic list and remove
   the left bracket. */
export let maybe_hide_topic_bracket = function (section_id: string): void {
    const $container = $(`#stream-list-${section_id}-container`);
    const is_collapsed = collapsed_sections.has(section_id);
    const $highlighted_topic = $container.find(".topic-list-item.active-sub-filter");
    $container.toggleClass("hide-topic-bracket", is_collapsed && $highlighted_topic.length === 0);
};

export function rewire_maybe_hide_topic_bracket(value: typeof maybe_hide_topic_bracket): void {
    maybe_hide_topic_bracket = value;
}

function toggle_section_collapse($container: JQuery): void {
    $container.toggleClass("collapsed");
    const is_collapsed = $container.hasClass("collapsed");
    $container
        .find(".stream-list-section-toggle")
        .toggleClass("rotate-icon-down", !is_collapsed)
        .toggleClass("rotate-icon-right", is_collapsed);

    const section_id = $container.attr("data-section-id")!;
    if (is_collapsed) {
        collapsed_sections.add(section_id);
    } else {
        collapsed_sections.delete(section_id);
    }
    maybe_hide_topic_bracket(section_id);
}

function set_sections_states(): void {
    if (ui_util.get_left_sidebar_search_term() === "") {
        // Restore the collapsed state of sections.
        for (const section_id of collapsed_sections) {
            const $container = $(`#stream-list-${section_id}-container`);
            $container.toggleClass("collapsed", true);
            $container
                .find(".stream-list-section-toggle")
                .toggleClass("rotate-icon-down", false)
                .toggleClass("rotate-icon-right", true);
        }
    }
    for (const section_id of sections_showing_inactive_or_muted) {
        $(`#stream-list-${section_id}-container`).toggleClass("showing-inactive-or-muted", true);
    }
}

export function get_stream_li(stream_id: number): JQuery | undefined {
    const row = stream_sidebar.get_row(stream_id);
    if (!row) {
        // Not all streams are in the sidebar, so we don't report
        // an error here, and it's up for the caller to error if
        // they expected otherwise.
        return undefined;
    }

    const $li = row.get_li();
    if (!$li) {
        blueslip.error("Cannot find li", {stream_id});
        return undefined;
    }

    if ($li.length > 1) {
        blueslip.error("stream_li has too many elements", {stream_id});
        return undefined;
    }

    return $li;
}

export function update_subscribe_to_more_streams_link(): void {
    const can_subscribe_stream_count = stream_data
        .unsubscribed_subs()
        .filter((sub) => stream_data.can_toggle_subscription(sub)).length;

    const can_create_streams =
        settings_data.user_can_create_private_streams() ||
        settings_data.user_can_create_public_streams() ||
        settings_data.user_can_create_web_public_streams();

    $("#subscribe-to-more-streams").html(
        render_subscribe_to_more_streams({
            can_subscribe_stream_count,
            can_create_streams,
            exactly_one_unsubscribed_stream: can_subscribe_stream_count === 1,
        }),
    );
}

function stream_id_for_elt($elt: JQuery): number {
    const stream_id_string = $elt.attr("data-stream-id");
    assert(stream_id_string !== undefined);
    return Number.parseInt(stream_id_string, 10);
}

export function zoom_in_topics(options: {stream_id: number | undefined}): void {
    // This only does stream-related tasks related to zooming
    // in to more topics, which is basically hiding all the
    // other streams.

    $("#streams_list").expectOne().removeClass("zoom-out").addClass("zoom-in");

    $("#stream_filters li.narrow-filter").each(function () {
        const $elt = $(this);
        const stream_id = options.stream_id;

        if (stream_id_for_elt($elt) === stream_id) {
            $elt.toggleClass("hide", false);
            // Add search box for topics list.
            $elt.children("div.bottom_left_row").append($(render_filter_topics()));
            topic_list.setup_topic_search_typeahead();
        } else {
            $elt.toggleClass("hide", true);
        }
    });
}

export function zoom_out_topics(): void {
    $("#streams_list").expectOne().removeClass("zoom-in").addClass("zoom-out");
    $("#stream_filters li.narrow-filter").toggleClass("hide", false);
    // Remove search box for topics list from DOM.
    $(".filter-topics").remove();
}

export function set_in_home_view(stream_id: number, in_home: boolean): void {
    const $li = get_stream_li(stream_id);
    if (!$li) {
        blueslip.error("passed in bad stream id", {stream_id});
        return;
    }

    if (in_home) {
        $li.removeClass("out_of_home_view");
    } else {
        $li.addClass("out_of_home_view");
    }
}

function build_stream_sidebar_li(sub: StreamSubscription): JQuery {
    const name = sub.name;
    const is_muted = stream_data.is_muted(sub.stream_id);
    const can_post_messages = stream_data.can_post_messages_in_stream(sub);
    const url = hash_util.channel_url_by_user_setting(sub.stream_id);
    const args = {
        name,
        id: sub.stream_id,
        url,
        is_muted,
        invite_only: sub.invite_only,
        is_web_public: sub.is_web_public,
        color: sub.color,
        pin_to_top: sub.pin_to_top,
        can_post_messages,
        is_empty_topic_only_channel: stream_data.is_empty_topic_only_channel(sub.stream_id),
    };
    const $list_item = $(render_stream_sidebar_row(args));
    return $list_item;
}

class StreamSidebarRow {
    sub: StreamSubscription;
    $list_item: JQuery;

    constructor(sub: StreamSubscription) {
        this.sub = sub;
        this.$list_item = build_stream_sidebar_li(sub);
        this.update_unread_count();
    }

    // The `inactive_stream` class is useful for identifying these
    // channels to node tests, even if the design doesn't currently
    // style these channels differently.
    update_whether_active(): void {
        if (stream_list_sort.has_recent_activity(this.sub)) {
            this.$list_item.removeClass("inactive_stream");
        } else {
            this.$list_item.addClass("inactive_stream");
        }
    }

    get_li(): JQuery {
        return this.$list_item;
    }

    remove(): void {
        this.$list_item.remove();
    }

    update_unread_count(): void {
        const count = unread.unread_count_info_for_stream(this.sub.stream_id);
        const stream_has_any_unread_mention_messages = unread.stream_has_any_unread_mentions(
            this.sub.stream_id,
        );
        const stream_has_any_unmuted_unread_mention = unread.stream_has_any_unmuted_mentions(
            this.sub.stream_id,
        );
        const stream_has_only_muted_unread_mentions =
            !this.sub.is_muted &&
            stream_has_any_unread_mention_messages &&
            !stream_has_any_unmuted_unread_mention;
        update_count_in_dom(
            this.$list_item,
            count,
            stream_has_any_unread_mention_messages,
            stream_has_any_unmuted_unread_mention,
            stream_has_only_muted_unread_mentions,
        );
    }
}

function build_stream_sidebar_row(sub: StreamSubscription): void {
    stream_sidebar.set_row(sub.stream_id, new StreamSidebarRow(sub));
}

export function create_sidebar_row(sub: StreamSubscription, force_rerender = false): void {
    if (!force_rerender && stream_sidebar.has_row_for(sub.stream_id)) {
        // already exists
        blueslip.warn("Dup try to build sidebar row for stream", {stream_id: sub.stream_id});
        return;
    }
    build_stream_sidebar_row(sub);
}

export function redraw_stream_privacy(sub: StreamSubscription): void {
    const $li = get_stream_li(sub.stream_id);
    if (!$li) {
        // We don't want to raise error here, if we can't find stream in subscription
        // stream list. Cause we allow org admin to update stream privacy
        // even if they don't subscribe to public stream.
        return;
    }

    const $div = $li.find(".stream-privacy");

    const args = {
        invite_only: sub.invite_only,
        is_web_public: sub.is_web_public,
    };

    const html = render_stream_privacy(args);
    $div.html(html);
}

function set_stream_unread_count(
    stream_id: number,
    count: StreamCountInfo,
    stream_has_any_unread_mention_messages: boolean,
    stream_has_any_unmuted_unread_mention: boolean,
    stream_has_only_muted_unread_mentions: boolean,
): void {
    const $stream_li = get_stream_li(stream_id);
    if (!$stream_li) {
        // This can happen for legitimate reasons, but we warn
        // just in case.
        blueslip.warn("stream id no longer in sidebar: " + stream_id);
        return;
    }
    update_count_in_dom(
        $stream_li,
        count,
        stream_has_any_unread_mention_messages,
        stream_has_any_unmuted_unread_mention,
        stream_has_only_muted_unread_mentions,
    );
}

export let update_streams_sidebar = (force_rerender = false): void => {
    if (!force_rerender && is_zoomed_in()) {
        // We do our best to update topics that are displayed
        // in case user zoomed in. Streams list will be updated,
        // once the user zooms out. This avoids user being zoomed out
        // when a new message causes streams to re-arrange.
        const filter = narrow_state.filter();
        assert(filter !== undefined);
        update_stream_sidebar_for_narrow(filter);
        set_pending_stream_list_rerender(true);
        return;
    }
    set_pending_stream_list_rerender(false);

    build_stream_list(force_rerender);

    const filter = narrow_state.filter();
    if (!filter) {
        return;
    }

    update_stream_sidebar_for_narrow(filter);
};

export function rewire_update_streams_sidebar(value: typeof update_streams_sidebar): void {
    update_streams_sidebar = value;
}

type SectionUnreadCount = {
    // These both include inactive unreads as well.
    unmuted: number;
    muted: number;
    // These are used for the count on the inactive/muted channel toggle.
    inactive_unmuted: number;
    inactive_muted: number;
    // e.g. followed topics in a muted channel, which count towards
    // the unmuted count in the inactive/muted channels toggle.
    muted_channel_unmuted: number;
    // Doesn't include muted topics in unmuted channels, which shouldn't
    // contribute to the count for the inactive/muted channel toggle.
    muted_channel_muted: number;
};

export let update_dom_with_unread_counts = function (counts: FullUnreadCountsData): void {
    // (1) Stream unread counts
    // counts.stream_count maps streams to counts
    for (const [stream_id, count] of counts.stream_count) {
        const stream_has_any_unread_mention_messages =
            counts.streams_with_mentions.includes(stream_id);
        const stream_has_any_unmuted_unread_mention =
            counts.streams_with_unmuted_mentions.includes(stream_id);
        const sub = sub_store.get(stream_id);
        assert(sub !== undefined);
        const stream_has_only_muted_unread_mentions =
            !sub.is_muted &&
            stream_has_any_unread_mention_messages &&
            !stream_has_any_unmuted_unread_mention;
        set_stream_unread_count(
            stream_id,
            count,
            stream_has_any_unread_mention_messages,
            stream_has_any_unmuted_unread_mention,
            stream_has_only_muted_unread_mentions,
        );
    }
    update_stream_section_mention_indicators();

    // (2) Unread counts in stream headers and collapse/uncollapse
    // toggles for muted and inactive channels.
    const pinned_unread_counts: SectionUnreadCount = {
        unmuted: 0,
        muted: 0,
        // Not used for the pinned section, but included here to make typing easier
        inactive_unmuted: 0,
        inactive_muted: 0,
        muted_channel_unmuted: 0,
        muted_channel_muted: 0,
    };
    const folder_unread_counts = new Map<number, SectionUnreadCount>();
    const normal_section_unread_counts: SectionUnreadCount = {
        unmuted: 0,
        muted: 0,
        inactive_unmuted: 0,
        inactive_muted: 0,
        muted_channel_unmuted: 0,
        muted_channel_muted: 0,
    };

    for (const [stream_id, stream_count_info] of counts.stream_count.entries()) {
        const sub = sub_store.get(stream_id);
        assert(sub);
        if (sub.pin_to_top) {
            pinned_unread_counts.unmuted += stream_count_info.unmuted_count;
            pinned_unread_counts.muted += stream_count_info.muted_count;
        } else if (sub.folder_id !== null) {
            if (!folder_unread_counts.has(sub.folder_id)) {
                folder_unread_counts.set(sub.folder_id, {
                    unmuted: 0,
                    muted: 0,
                    inactive_unmuted: 0,
                    inactive_muted: 0,
                    muted_channel_unmuted: 0,
                    muted_channel_muted: 0,
                });
            }

            const unread_counts = folder_unread_counts.get(sub.folder_id)!;
            unread_counts.unmuted += stream_count_info.unmuted_count;
            unread_counts.muted += stream_count_info.muted_count;
            if (sub.is_muted) {
                unread_counts.muted_channel_unmuted += stream_count_info.unmuted_count;
                unread_counts.muted_channel_muted += stream_count_info.muted_count;
            }
            if (!stream_list_sort.has_recent_activity(sub)) {
                unread_counts.inactive_unmuted += stream_count_info.unmuted_count;
                unread_counts.inactive_muted += stream_count_info.muted_count;
            }
        } else {
            normal_section_unread_counts.unmuted += stream_count_info.unmuted_count;
            normal_section_unread_counts.muted += stream_count_info.muted_count;
            if (sub.is_muted) {
                normal_section_unread_counts.muted_channel_unmuted +=
                    stream_count_info.unmuted_count;
                normal_section_unread_counts.muted_channel_muted += stream_count_info.muted_count;
            }
            if (!stream_list_sort.has_recent_activity(sub)) {
                normal_section_unread_counts.inactive_unmuted += stream_count_info.unmuted_count;
                normal_section_unread_counts.inactive_muted += stream_count_info.muted_count;
            }
        }
    }

    function update_section_unread_count(
        $header: JQuery,
        unmuted_count: number,
        muted_count: number,
    ): void {
        const show_muted_count = unmuted_count === 0 && muted_count > 0;
        if (show_muted_count) {
            ui_util.update_unread_count_in_dom($header, muted_count);
        } else {
            ui_util.update_unread_count_in_dom($header, unmuted_count);
        }
        $header.toggleClass("has-only-muted-unreads", show_muted_count);
        $header.toggleClass(
            "hide_unread_counts",
            settings_data.should_mask_unread_count(show_muted_count, unmuted_count),
        );
    }

    update_section_unread_count(
        $("#stream-list-pinned-streams-container .stream-list-subsection-header"),
        pinned_unread_counts.unmuted,
        pinned_unread_counts.muted,
    );

    update_section_unread_count(
        $("#stream-list-normal-streams-container .stream-list-subsection-header"),
        normal_section_unread_counts.unmuted,
        normal_section_unread_counts.muted,
    );
    update_section_unread_count(
        $("#stream-list-normal-streams-container .show-inactive-or-muted-channels"),
        normal_section_unread_counts.inactive_unmuted +
            normal_section_unread_counts.muted_channel_unmuted,
        normal_section_unread_counts.inactive_muted +
            normal_section_unread_counts.muted_channel_muted,
    );

    for (const folder_id of channel_folders.get_all_folder_ids()) {
        const unread_counts = folder_unread_counts.get(folder_id) ?? {
            unmuted: 0,
            muted: 0,
            inactive_unmuted: 0,
            inactive_muted: 0,
            muted_channel_unmuted: 0,
            muted_channel_muted: 0,
        };
        update_section_unread_count(
            $(`#stream-list-${folder_id}-container .stream-list-subsection-header`),
            unread_counts.unmuted,
            unread_counts.muted,
        );
        update_section_unread_count(
            $(`#stream-list-${folder_id}-container .show-inactive-or-muted-channels`),
            unread_counts.inactive_unmuted + unread_counts.muted_channel_unmuted,
            unread_counts.inactive_muted + unread_counts.muted_channel_muted,
        );
    }
};

export function rewire_update_dom_with_unread_counts(
    value: typeof update_dom_with_unread_counts,
): void {
    update_dom_with_unread_counts = value;
}

function toggle_hide_unread_counts(
    $subscription_block: JQuery,
    sub_muted: boolean,
    unmuted_unread_counts: number,
): void {
    const hide_count = settings_data.should_mask_unread_count(sub_muted, unmuted_unread_counts);

    $subscription_block.toggleClass("hide_unread_counts", hide_count);
}

export function rename_stream(sub: StreamSubscription): void {
    // The sub object is expected to already have the updated name
    build_stream_sidebar_row(sub);
    update_streams_sidebar(true); // big hammer
}

export function refresh_pinned_or_unpinned_stream(sub: StreamSubscription): void {
    // Pinned/unpinned streams require re-ordering.
    // We use kind of brute force now, which is probably fine.
    build_stream_sidebar_row(sub);
    update_streams_sidebar();
    const section_id = stream_list_sort.current_section_id_for_stream(sub.stream_id);
    if (section_id !== undefined) {
        maybe_hide_topic_bracket(section_id);
    }

    // Only scroll pinned topics into view.  If we're unpinning
    // a topic, we may be literally trying to get it out of
    // our sight.
    if (sub.pin_to_top) {
        const $stream_li = get_stream_li(sub.stream_id);
        if (!$stream_li) {
            blueslip.error("passed in bad stream id", {stream_id: sub.stream_id});
            return;
        }
        scroll_stream_into_view($stream_li);
    }
}

export function refresh_muted_or_unmuted_stream(sub: StreamSubscription): void {
    build_stream_sidebar_row(sub);
    // If a stream is inactive, it'll stay in the same inactive list in its
    // StreamListSection (so `same_as_before` will be true), so we need to
    // force the rerender to change its faded/unfaded appearance.
    const force_rerender = !stream_list_sort.has_recent_activity(sub);
    update_streams_sidebar(force_rerender);
}

export function get_sidebar_stream_topic_info(filter: Filter): {
    stream_id: number | undefined;
    topic_selected: boolean;
} {
    const result: {
        stream_id: number | undefined;
        topic_selected: boolean;
    } = {
        stream_id: undefined,
        topic_selected: false,
    };

    const op_stream = filter.operands("channel");
    if (op_stream[0] === undefined) {
        return result;
    }

    const stream_id = Number.parseInt(op_stream[0], 10);

    if (!stream_id) {
        return result;
    }

    if (!stream_data.is_subscribed(stream_id) || stream_data.is_stream_archived_by_id(stream_id)) {
        return result;
    }

    result.stream_id = stream_id;

    const op_topic = filter.operands("topic");
    result.topic_selected = op_topic.length === 1;

    return result;
}

function deselect_stream_items(): void {
    $("ul#stream_filters li").removeClass("active-filter stream-expanded");
}

export function update_stream_sidebar_for_narrow(filter: Filter): JQuery | undefined {
    const info = get_sidebar_stream_topic_info(filter);

    deselect_stream_items();

    const stream_id = info.stream_id;

    if (!stream_id) {
        clear_topics();
        return undefined;
    }

    const $stream_li = get_stream_li(stream_id);

    if (!$stream_li) {
        // This is a sanity check.  When we narrow to a subscribed
        // stream, there will always be a stream list item
        // corresponding to that stream in our sidebar.  This error
        // stopped appearing from March 2018 until at least
        // April 2020, so if it appears again, something regressed.
        blueslip.error("No stream_li for subscribed stream", {stream_id});
        clear_topics();
        return undefined;
    }

    if (!info.topic_selected) {
        $stream_li.addClass("active-filter");
    }

    // Always add 'stream-expanded' class irrespective of whether
    // topic is selected or not. This is required for proper styling
    // masked unread counts.
    $stream_li.addClass("stream-expanded");

    if (stream_id !== topic_list.active_stream_id()) {
        clear_topics();
    }

    // We want to update channel view for inbox for the same reasons
    // we want to the topics list here.
    update_inbox_channel_view_callback(stream_id);
    topic_list.rebuild_left_sidebar($stream_li, stream_id);
    topic_list.topic_state_typeahead?.lookup(true);
    return $stream_li;
}

export function handle_narrow_activated(
    filter: Filter,
    change_hash: boolean,
    show_more_topics: boolean,
): void {
    const $stream_li = update_stream_sidebar_for_narrow(filter);
    if ($stream_li) {
        scroll_stream_into_view($stream_li);
        if (!change_hash) {
            if (!is_zoomed_in() && show_more_topics) {
                zoom_in();
            } else if (is_zoomed_in() && !show_more_topics) {
                zoom_out();
            }
        }
    }

    if (is_zoomed_in()) {
        topic_list.left_sidebar_scroll_zoomed_in_topic_into_view();
    }
}

export function handle_message_view_deactivated(): void {
    deselect_stream_items();
    clear_topics();
}

export function initialize({
    show_channel_feed,
    update_inbox_channel_view,
}: {
    show_channel_feed: (stream_id: number, trigger: string) => void;
    update_inbox_channel_view: (channel_id: number) => void;
}): void {
    update_inbox_channel_view_callback = update_inbox_channel_view;
    create_initial_sidebar_rows();

    // We build the stream_list now.  It may get re-built again very shortly
    // when new messages come in, but it's fairly quick.
    build_stream_list(false);
    update_subscribe_to_more_streams_link();
    initialize_tippy_tooltips();
    set_event_handlers({show_channel_feed});

    $("#stream_filters").on("click", ".show-more-topics", (e) => {
        zoom_in();
        // We define the focus behavior for the topic list search box
        // outside of the `zoom_in` method, since we want the focus
        // to only happen when the user clicks on the "SHOW ALL TOPICS"
        // button, and not interfere with the narrow change handling.
        $("#topic_filter_query").trigger("focus");
        browser_history.update_current_history_state_data({show_more_topics: true});

        e.preventDefault();
        e.stopPropagation();
    });

    $(".show-all-streams").on("click", (e) => {
        zoom_out();
        browser_history.update_current_history_state_data({show_more_topics: false});

        e.preventDefault();
        e.stopPropagation();
    });
}

export function initialize_tippy_tooltips(): void {
    tippy.delegate("body", {
        target: "#stream_filters li .subscription_block .stream-name",
        delay: LONG_HOVER_DELAY,
        onShow(instance) {
            // check for "Go to channel feed" tooltip conditions first.
            const stream_id = stream_id_for_elt($(instance.reference).parents("li.narrow-filter"));
            const current_narrow_stream_id = narrow_state.stream_id();
            const current_topic = narrow_state.topic();
            if (current_narrow_stream_id === stream_id && current_topic !== undefined) {
                if (
                    user_settings.web_channel_default_view ===
                    web_channel_default_view_values.list_of_topics.code
                ) {
                    instance.setContent(
                        ui_util.parse_html(render_go_to_channel_list_of_topics_tooltip()),
                    );
                } else {
                    instance.setContent(ui_util.parse_html(render_go_to_channel_feed_tooltip()));
                }
                return undefined;
            }
            // Then check for truncation
            const stream_name_element = instance.reference;
            assert(stream_name_element instanceof HTMLElement);

            if (stream_name_element.offsetWidth < stream_name_element.scrollWidth) {
                const stream_name = stream_name_element.textContent ?? "";
                instance.setContent(stream_name);
                return undefined;
            }

            return false;
        },
        appendTo: () => document.body,
    });
}

export function on_sidebar_channel_click(
    stream_id: number,
    // Null is used when this is called via `Enter`, because the
    // keyboard abstraction we're using doesn't need to pass on the event.
    e: JQuery.ClickEvent | null,
    show_channel_feed: (stream_id: number, trigger: string) => void,
): void {
    clear_search();
    if (e !== null) {
        e.preventDefault();
        e.stopPropagation();
    }

    const section_for_stream = stream_list_sort.current_section_id_for_stream(stream_id);
    if (section_for_stream !== undefined && collapsed_sections.has(section_for_stream)) {
        // In the event that user clicks on the channel in the left
        // sidebar when its folder is collapsed, which is only there
        // to click on if the user was already viewing that channel,
        // we uncollapse the section to make the filtering component
        // visible.
        toggle_section_collapse($(`#stream-list-${section_for_stream}-container`));
    }

    const current_narrow_stream_id = narrow_state.stream_id();
    const current_topic = narrow_state.topic();

    if (stream_data.is_empty_topic_only_channel(stream_id)) {
        // If the channel doesn't support topics, take you
        // directly to general chat regardless of settings.
        const empty_topic_url = hash_util.by_channel_topic_permalink(stream_id, "");
        browser_history.go_to_location(empty_topic_url);
        return;
    }

    if (
        user_settings.web_channel_default_view ===
        web_channel_default_view_values.list_of_topics.code
    ) {
        browser_history.go_to_location(hash_util.by_channel_topic_list_url(stream_id));
        return;
    }

    if (current_narrow_stream_id === stream_id && current_topic !== undefined) {
        const channel_feed_url = hash_util.channel_url_by_user_setting(stream_id);
        browser_history.go_to_location(channel_feed_url);
        return;
    }

    if (
        user_settings.web_channel_default_view === web_channel_default_view_values.channel_feed.code
    ) {
        show_channel_feed(stream_id, "sidebar");
        return;
    }

    let topics = stream_topic_history.get_recent_topic_names(stream_id);

    const navigate_to_stream = (): void => {
        const topic_list_info = topic_list_data.get_list_info(
            stream_id,
            false,
            (topic_names: string[]) => topic_names,
        );
        // This initial value handles both the
        // top_topic_in_channel mode as well as the
        // top_unread_topic_in_channel fallback when there are no
        // (unmuted) unreads in the channel.
        let topic_item = topic_list_info.items[0];

        if (
            user_settings.web_channel_default_view ===
            web_channel_default_view_values.top_unread_topic_in_channel.code
        ) {
            for (const topic_list_item of topic_list_info.items) {
                if (
                    unread.topic_has_any_unread(stream_id, topic_list_item.topic_name) &&
                    !user_topics.is_topic_muted(stream_id, topic_list_item.topic_name)
                ) {
                    topic_item = topic_list_item;
                    break;
                }
            }
        }

        if (topic_item !== undefined) {
            const destination_url = hash_util.by_channel_topic_permalink(
                stream_id,
                topic_item.topic_name,
            );
            browser_history.go_to_location(destination_url);
        } else {
            show_channel_feed(stream_id, "sidebar");
            return;
        }
    };

    if (topics.length === 0) {
        stream_topic_history_util.get_server_history(stream_id, () => {
            topics = stream_topic_history.get_recent_topic_names(stream_id);
            if (topics.length === 0) {
                show_channel_feed(stream_id, "sidebar");
                return;
            }
            navigate_to_stream();
            return;
        });
    } else {
        navigate_to_stream();
        return;
    }
}

export function set_event_handlers({
    show_channel_feed,
}: {
    show_channel_feed: (stream_id: number, trigger: string) => void;
}): void {
    $("#stream_filters").on("click", "li .subscription_block", (e) => {
        // Left sidebar channel links have an `href` so that the
        // browser will preview the URL and you can middle-click it.
        //
        // But we want to control what the click does to follow the
        // user's default left sidebar click action, rather than
        // taking you to the channel feed.
        if (e.metaKey || e.ctrlKey || e.shiftKey) {
            return;
        }
        if (document.getSelection()?.type === "Range") {
            // To avoid the click behavior if a channel name is selected.
            e.preventDefault();
            return;
        }

        const stream_id = stream_id_for_elt($(e.target).parents("li.narrow-filter"));
        on_sidebar_channel_click(stream_id, e, show_channel_feed);
    });

    $("#stream_filters").on("click", ".channel-new-topic-button", function (this: HTMLElement, e) {
        e.stopPropagation();
        e.preventDefault();
        const stream_id = Number.parseInt(this.dataset.streamId!, 10);
        compose_actions.start({
            message_type: "stream",
            stream_id,
            topic: "",
            trigger: "clear topic button",
            keep_composebox_empty: true,
        });
    });

    function toggle_pm_header_icon(): void {
        if (pm_list.is_private_messages_collapsed()) {
            return;
        }

        const scroll_position = $(
            "#left_sidebar_scroll_container .simplebar-content-wrapper",
        ).scrollTop();
        const pm_list_height = $("#direct-messages-list").height();
        assert(scroll_position !== undefined);
        assert(pm_list_height !== undefined);
        if (scroll_position > pm_list_height) {
            $("#toggle-direct-messages-section-icon").addClass("rotate-icon-right");
            $("#toggle-direct-messages-section-icon").removeClass("rotate-icon-down");
        } else {
            $("#toggle-direct-messages-section-icon").addClass("rotate-icon-down");
            $("#toggle-direct-messages-section-icon").removeClass("rotate-icon-right");
        }
    }

    // check for user scrolls on streams list for first time
    scroll_util.get_scroll_element($("#left_sidebar_scroll_container")).on("scroll", () => {
        has_scrolled = true;
        toggle_pm_header_icon();
    });

    $("#streams_list").on(
        "click",
        ".stream-list-section-container .stream-list-subsection-header",
        function (this: HTMLElement, e: JQuery.ClickEvent) {
            e.stopPropagation();
            toggle_section_collapse($(this).closest(".stream-list-section-container"));
        },
    );

    $("#streams_list").on(
        "click",
        ".stream-list-section-container .add-stream-icon-container",
        (e) => {
            // The browser default behavior of following the href on
            // this link is correct. But we need to avoid triggering
            // the click handler for the containing row, though (which
            // would toggle the section).
            e.stopPropagation();
        },
    );

    $("#streams_list").on(
        "click",
        ".stream-list-toggle-inactive-or-muted-channels",
        function (this: HTMLElement, e: JQuery.ClickEvent) {
            e.stopPropagation();
            toggle_inactive_or_muted_channels($(this).closest(".stream-list-section-container"));
        },
    );
}

function toggle_inactive_or_muted_channels($section_container: JQuery): void {
    $section_container.toggleClass("showing-inactive-or-muted");
    const showing_inactive_or_muted = $section_container.hasClass("showing-inactive-or-muted");
    const section_id = $section_container.attr("data-section-id")!;
    if (showing_inactive_or_muted) {
        sections_showing_inactive_or_muted.add(section_id);
    } else {
        sections_showing_inactive_or_muted.delete(section_id);
    }
}

export function searching(): boolean {
    return $(".left-sidebar-search-input").expectOne().is(":focus");
}

export function clear_search(): void {
    const $filter = $(".left-sidebar-search-input").expectOne();
    if ($filter.val() !== "") {
        $filter.val("");
        $filter.trigger("input");
    }
    $filter.trigger("blur");
}

export let scroll_stream_into_view = function ($stream_li: JQuery): void {
    const $container = $("#left_sidebar_scroll_container");

    if ($stream_li.length !== 1) {
        blueslip.error("Invalid stream_li was passed in");
        return;
    }
    const stream_filter_height = $("#left-sidebar-search").outerHeight()!;
    const header_height = $stream_li
        .closest(".stream-list-section-container")
        .children(".stream-list-subsection-header")
        .outerHeight()!;
    scroll_util.scroll_element_into_container(
        $stream_li,
        $container,
        stream_filter_height + header_height,
    );
    // Note: If the stream is in a collapsed folder, we don't uncollapse
    // the folder. We do uncollapse when the user clicks on the channel,
    // but that's handled elsewhere.
};

export function rewire_scroll_stream_into_view(value: typeof scroll_stream_into_view): void {
    scroll_stream_into_view = value;
}

export function maybe_scroll_narrow_into_view(first_messages_fetch_done: boolean): void {
    // we don't want to interfere with user scrolling once the page loads
    if (has_scrolled && first_messages_fetch_done) {
        return;
    }

    const $stream_li = get_current_stream_li();
    if ($stream_li) {
        scroll_stream_into_view($stream_li);
    }
}

export function get_current_stream_li(): JQuery | undefined {
    const stream_id = topic_list.active_stream_id();

    if (!stream_id) {
        // stream_id is undefined in non-stream narrows
        return undefined;
    }

    const $stream_li = get_stream_li(stream_id);

    if (!$stream_li) {
        // This code path shouldn't ever be reached.
        blueslip.warn("No active stream_li found for defined id " + stream_id);
        return undefined;
    }

    return $stream_li;
}
