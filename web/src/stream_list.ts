import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";

import render_filter_topics from "../templates/filter_topics.hbs";
import render_stream_privacy from "../templates/stream_privacy.hbs";
import render_stream_sidebar_row from "../templates/stream_sidebar_row.hbs";
import render_stream_subheader from "../templates/streams_subheader.hbs";
import render_subscribe_to_more_streams from "../templates/subscribe_to_more_streams.hbs";

import * as blueslip from "./blueslip";
import type {Filter} from "./filter";
import * as hash_util from "./hash_util";
import {$t} from "./i18n";
import * as keydown_util from "./keydown_util";
import {ListCursor} from "./list_cursor";
import * as narrow_state from "./narrow_state";
import * as pm_list from "./pm_list";
import * as popovers from "./popovers";
import * as resize from "./resize";
import * as scroll_util from "./scroll_util";
import * as settings_data from "./settings_data";
import * as sidebar_ui from "./sidebar_ui";
import * as stream_data from "./stream_data";
import * as stream_list_sort from "./stream_list_sort";
import * as sub_store from "./sub_store";
import type {StreamSubscription} from "./sub_store";
import * as topic_list from "./topic_list";
import * as ui_util from "./ui_util";
import * as unread from "./unread";
import type {FullUnreadCountsData, StreamCountInfo} from "./unread";

let pending_stream_list_rerender = false;
let zoomed_in = false;

export let stream_cursor: ListCursor<number>;

let has_scrolled = false;

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

export function update_count_in_dom(
    $stream_li: JQuery,
    stream_counts: StreamCountInfo,
    stream_has_any_unread_mention_messages: boolean,
    stream_has_any_unmuted_unread_mention: boolean,
    stream_has_only_muted_unread_mention: boolean,
): void {
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

function get_search_term(): string {
    const $search_box = $<HTMLInputElement>("input.stream-list-filter").expectOne();
    const search_term = $search_box.val();
    assert(search_term !== undefined);
    return search_term.trim();
}

export function add_sidebar_row(sub: StreamSubscription): void {
    create_sidebar_row(sub);
    update_streams_sidebar();
}

export function remove_sidebar_row(stream_id: number): void {
    stream_sidebar.remove_row(stream_id);
    const force_rerender = stream_id === topic_list.active_stream_id();
    update_streams_sidebar(force_rerender);
}

export function create_initial_sidebar_rows(): void {
    // This code is slightly opaque, but it ends up building
    // up list items and attaching them to the "sub" data
    // structures that are kept in stream_data.js.
    const subs = stream_data.subscribed_subs();

    for (const sub of subs) {
        create_sidebar_row(sub);
    }
}

export function build_stream_list(force_rerender: boolean): void {
    // The stream list in the left sidebar contains 3 sections:
    // pinned, normal, and dormant streams, with headings above them
    // as appropriate.
    //
    // Within the first two sections, muted streams are sorted to the
    // bottom; we skip that for dormant streams to simplify discovery.
    const streams = stream_data.subscribed_stream_ids();
    const $parent = $("#stream_filters");
    if (streams.length === 0) {
        $parent.empty();
        return;
    }

    // The main logic to build the list is in stream_list_sort.ts, and
    // we get five lists of streams (pinned/normal/muted_pinned/muted_normal/dormant).
    const stream_groups = stream_list_sort.sort_groups(streams, get_search_term());

    if (stream_groups.same_as_before && !force_rerender) {
        return;
    }

    const elems = [];

    function add_sidebar_li(stream_id: number): void {
        const sidebar_row = stream_sidebar.get_row(stream_id);
        assert(sidebar_row !== undefined);
        sidebar_row.update_whether_active();
        elems.push(sidebar_row.get_li());
    }

    clear_topics();
    $parent.empty();

    const any_pinned_streams =
        stream_groups.pinned_streams.length > 0 || stream_groups.muted_pinned_streams.length > 0;
    const any_normal_streams =
        stream_groups.normal_streams.length > 0 || stream_groups.muted_active_streams.length > 0;
    const any_dormant_streams = stream_groups.dormant_streams.length > 0;

    const need_section_subheaders =
        (any_pinned_streams ? 1 : 0) +
            (any_normal_streams ? 1 : 0) +
            (any_dormant_streams ? 1 : 0) >=
        2;

    if (any_pinned_streams && need_section_subheaders) {
        elems.push(
            $(
                render_stream_subheader({
                    subheader_name: $t({
                        defaultMessage: "Pinned",
                    }),
                }),
            ),
        );
    }

    for (const stream_id of stream_groups.pinned_streams) {
        add_sidebar_li(stream_id);
    }

    for (const stream_id of stream_groups.muted_pinned_streams) {
        add_sidebar_li(stream_id);
    }

    if (any_normal_streams && need_section_subheaders) {
        elems.push(
            $(
                render_stream_subheader({
                    subheader_name: $t({
                        defaultMessage: "Active",
                    }),
                }),
            ),
        );
    }

    for (const stream_id of stream_groups.normal_streams) {
        add_sidebar_li(stream_id);
    }

    for (const stream_id of stream_groups.muted_active_streams) {
        add_sidebar_li(stream_id);
    }

    if (any_dormant_streams && need_section_subheaders) {
        elems.push(
            $(
                render_stream_subheader({
                    subheader_name: $t({
                        defaultMessage: "Inactive",
                    }),
                }),
            ),
        );
    }

    for (const stream_id of stream_groups.dormant_streams) {
        add_sidebar_li(stream_id);
    }

    $parent.append(elems); // eslint-disable-line no-jquery/no-append-html
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

    // Hide stream list titles and pinned stream splitter
    $(".stream-filters-label").each(function () {
        $(this).hide();
    });
    $(".streams_subheader").each(function () {
        $(this).hide();
    });

    $("#stream_filters li.narrow-filter").each(function () {
        const $elt = $(this);
        const stream_id = options.stream_id;

        if (stream_id_for_elt($elt) === stream_id) {
            $elt.show();
            // Add search box for topics list.
            $elt.children("div.bottom_left_row").append($(render_filter_topics()));
            $("#filter-topic-input").trigger("focus");
            $("#clear_search_topic_button").hide();
        } else {
            $elt.hide();
        }
    });
}

export function zoom_out_topics(): void {
    // Show stream list titles and pinned stream splitter
    $(".stream-filters-label").each(function () {
        $(this).show();
    });
    $(".streams_subheader").each(function () {
        $(this).show();
    });

    $("#streams_list").expectOne().removeClass("zoom-in").addClass("zoom-out");
    $("#stream_filters li.narrow-filter").show();
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
    const args = {
        name,
        id: sub.stream_id,
        url: hash_util.by_stream_url(sub.stream_id),
        is_muted,
        invite_only: sub.invite_only,
        is_web_public: sub.is_web_public,
        color: sub.color,
        pin_to_top: sub.pin_to_top,
        hide_unread_count: settings_data.should_mask_unread_count(is_muted),
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

    update_whether_active(): void {
        if (stream_list_sort.has_recent_activity(this.sub) || this.sub.pin_to_top === true) {
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

export function create_sidebar_row(sub: StreamSubscription): void {
    if (stream_sidebar.has_row_for(sub.stream_id)) {
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

export function update_streams_sidebar(force_rerender = false): void {
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

    stream_cursor.redraw();

    const filter = narrow_state.filter();
    if (!filter) {
        return;
    }

    update_stream_sidebar_for_narrow(filter);
}

export function update_dom_with_unread_counts(counts: FullUnreadCountsData): void {
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
}

export function update_dom_unread_counts_visibility(): void {
    const $streams_header = $("#streams_header");
    if (settings_data.should_mask_unread_count(false)) {
        $streams_header.addClass("hide_unread_counts");
    } else {
        $streams_header.removeClass("hide_unread_counts");
    }
    for (const stream of stream_sidebar.rows.values()) {
        const $subscription_block = stream.get_li().find(".subscription_block");

        const is_muted = stream_data.is_muted(stream.sub.stream_id);
        const hide_count = settings_data.should_mask_unread_count(is_muted);

        if (hide_count) {
            $subscription_block.addClass("hide_unread_counts");
        } else {
            $subscription_block.removeClass("hide_unread_counts");
        }
    }
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
    update_streams_sidebar();
}

export function get_sidebar_stream_topic_info(filter: Filter): {
    stream_id?: number;
    topic_selected: boolean;
} {
    const result: {
        stream_id?: number;
        topic_selected: boolean;
    } = {
        stream_id: undefined,
        topic_selected: false,
    };

    const op_stream = filter.operands("channel");
    if (op_stream.length === 0) {
        return result;
    }

    const stream_name = op_stream[0];
    const stream_id = stream_data.get_stream_id(stream_name);

    if (!stream_id) {
        return result;
    }

    if (!stream_data.is_subscribed(stream_id)) {
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

    topic_list.rebuild($stream_li, stream_id);

    return $stream_li;
}

export function handle_narrow_activated(filter: Filter): void {
    const $stream_li = update_stream_sidebar_for_narrow(filter);
    if ($stream_li) {
        scroll_stream_into_view($stream_li);
    }
}

export function handle_message_view_deactivated(): void {
    deselect_stream_items();
    clear_topics();
}

function focus_stream_filter(e: JQuery.ClickEvent): void {
    stream_cursor.reset();
    e.stopPropagation();
}

function actually_update_streams_for_search(): void {
    update_streams_sidebar();
    resize.resize_page_components();
    stream_cursor.reset();
}

const update_streams_for_search = _.throttle(actually_update_streams_for_search, 50);

// Exported for tests only.
export function initialize_stream_cursor(): void {
    stream_cursor = new ListCursor({
        list: {
            scroll_container_selector: "#left_sidebar_scroll_container",
            find_li(opts) {
                const stream_id = opts.key;
                const $li = get_stream_li(stream_id);
                return $li;
            },
            first_key: stream_list_sort.first_stream_id,
            prev_key: stream_list_sort.prev_stream_id,
            next_key: stream_list_sort.next_stream_id,
        },
        highlight_class: "highlighted_stream",
    });
}

export function initialize({
    on_stream_click,
}: {
    on_stream_click: (stream_id: number, trigger: string) => void;
}): void {
    create_initial_sidebar_rows();

    // We build the stream_list now.  It may get re-built again very shortly
    // when new messages come in, but it's fairly quick.
    build_stream_list(false);
    update_subscribe_to_more_streams_link();
    initialize_stream_cursor();
    set_event_handlers({on_stream_click});

    $("#stream_filters").on("click", ".show-more-topics", (e) => {
        zoom_in();

        e.preventDefault();
        e.stopPropagation();
    });

    $(".show-all-streams").on("click", (e) => {
        zoom_out();

        e.preventDefault();
        e.stopPropagation();
    });
}

export function set_event_handlers({
    on_stream_click,
}: {
    on_stream_click: (stream_id: number, trigger: string) => void;
}): void {
    $("#stream_filters").on("click", "li .subscription_block", (e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey) {
            return;
        }
        const stream_id = stream_id_for_elt($(e.target).parents("li"));
        on_stream_click(stream_id, "sidebar");

        clear_and_hide_search();

        e.preventDefault();
        e.stopPropagation();
    });

    $("#clear_search_stream_button").on("click", clear_search);

    $("#streams_header")
        .expectOne()
        .on("click", (e) => {
            e.preventDefault();
            if (e.target.id === "streams_inline_icon") {
                return;
            }
            toggle_filter_displayed(e);
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
            $("#toggle_private_messages_section_icon").addClass("fa-caret-right");
            $("#toggle_private_messages_section_icon").removeClass("fa-caret-down");
        } else {
            $("#toggle_private_messages_section_icon").addClass("fa-caret-down");
            $("#toggle_private_messages_section_icon").removeClass("fa-caret-right");
        }
    }

    // check for user scrolls on streams list for first time
    scroll_util.get_scroll_element($("#left_sidebar_scroll_container")).on("scroll", () => {
        has_scrolled = true;
        toggle_pm_header_icon();
    });

    const $search_input = $(".stream-list-filter").expectOne();

    function keydown_enter_key(): void {
        const stream_id = stream_cursor.get_key();

        if (stream_id === undefined) {
            // This can happen for empty searches, no need to warn.
            return;
        }

        clear_and_hide_search();
        on_stream_click(stream_id, "sidebar enter key");
    }

    keydown_util.handle({
        $elem: $search_input,
        handlers: {
            Enter() {
                keydown_enter_key();
                return true;
            },
            ArrowUp() {
                stream_cursor.prev();
                return true;
            },
            ArrowDown() {
                stream_cursor.next();
                return true;
            },
        },
    });

    $search_input.on("click", focus_stream_filter);
    $search_input.on("focusout", () => {
        stream_cursor.clear();
    });
    $search_input.on("input", update_streams_for_search);
}

export function searching(): boolean {
    return $(".stream-list-filter").expectOne().is(":focus");
}

export function clear_search(e: JQuery.ClickEvent): void {
    e.stopPropagation();
    const $filter = $(".stream-list-filter").expectOne();
    if ($filter.val() === "") {
        clear_and_hide_search();
        return;
    }
    $filter.val("");
    $filter.trigger("blur");
    update_streams_for_search();
}

export function show_search_section(): void {
    $("#streams_header").addClass("showing-stream-search-section");
    $(".stream_search_section").expectOne().removeClass("notdisplayed");
    resize.resize_stream_filters_container();
}

export function hide_search_section(): void {
    $("#streams_header").removeClass("showing-stream-search-section");
    $(".stream_search_section").expectOne().addClass("notdisplayed");
    resize.resize_stream_filters_container();
}

export function initiate_search(): void {
    popovers.hide_all();
    show_search_section();

    const $filter = $(".stream-list-filter").expectOne();

    if (
        // Check if left column is a overlay and is not visible.
        $("#streamlist-toggle").is(":visible") &&
        !sidebar_ui.left_sidebar_expanded_as_overlay
    ) {
        popovers.hide_all();
        sidebar_ui.show_streamlist_sidebar();
    }
    $filter.trigger("focus");

    stream_cursor.reset();
}

export function clear_and_hide_search(): void {
    const $filter = $(".stream-list-filter").expectOne();
    if ($filter.val() !== "") {
        $filter.val("");
        update_streams_for_search();
    }
    stream_cursor.clear();
    $filter.trigger("blur");

    hide_search_section();
}

export function toggle_filter_displayed(e: JQuery.ClickEvent): void {
    if ($(".stream_search_section.notdisplayed").length === 0) {
        clear_and_hide_search();
    } else {
        initiate_search();
    }
    e.preventDefault();
}

export function scroll_stream_into_view($stream_li: JQuery): void {
    const $container = $("#left_sidebar_scroll_container");

    if ($stream_li.length !== 1) {
        blueslip.error("Invalid stream_li was passed in");
        return;
    }
    const stream_header_height = $("#streams_header").outerHeight();
    scroll_util.scroll_element_into_container($stream_li, $container, stream_header_height);
}

export function maybe_scroll_narrow_into_view(): void {
    // we don't want to interfere with user scrolling once the page loads
    if (has_scrolled) {
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
