import $ from "jquery";
import _ from "lodash";

import render_stream_privacy from "../templates/stream_privacy.hbs";
import render_stream_sidebar_row from "../templates/stream_sidebar_row.hbs";
import render_stream_subheader from "../templates/streams_subheader.hbs";
import render_subscribe_to_more_streams from "../templates/subscribe_to_more_streams.hbs";

import * as blueslip from "./blueslip";
import * as color_class from "./color_class";
import * as hash_util from "./hash_util";
import {$t} from "./i18n";
import * as keydown_util from "./keydown_util";
import {ListCursor} from "./list_cursor";
import * as narrow from "./narrow";
import * as narrow_state from "./narrow_state";
import * as pm_list from "./pm_list";
import * as popovers from "./popovers";
import * as resize from "./resize";
import * as scroll_util from "./scroll_util";
import * as settings_data from "./settings_data";
import * as stream_data from "./stream_data";
import * as stream_popover from "./stream_popover";
import * as stream_sort from "./stream_sort";
import * as sub_store from "./sub_store";
import * as topic_list from "./topic_list";
import * as topic_zoom from "./topic_zoom";
import * as ui from "./ui";
import * as ui_util from "./ui_util";
import * as unread from "./unread";

export let stream_cursor;

let has_scrolled = false;

export function update_count_in_dom($stream_li, count, stream_has_any_unread_mention_messages) {
    // The subscription_block properly excludes the topic list,
    // and it also has sensitive margins related to whether the
    // count is there or not.
    const $subscription_block = $stream_li.find(".subscription_block");

    ui_util.update_unread_count_in_dom($subscription_block, count);
    ui_util.update_unread_mention_info_in_dom(
        $subscription_block,
        stream_has_any_unread_mention_messages,
    );

    if (count === 0) {
        $subscription_block.removeClass("stream-with-count");
    } else {
        $subscription_block.addClass("stream-with-count");
    }
}

class StreamSidebar {
    rows = new Map(); // stream id -> row widget

    set_row(stream_id, widget) {
        this.rows.set(stream_id, widget);
    }

    get_row(stream_id) {
        return this.rows.get(stream_id);
    }

    has_row_for(stream_id) {
        return this.rows.has(stream_id);
    }

    remove_row(stream_id) {
        // This only removes the row from our data structure.
        // Our caller should use build_stream_list() to re-draw
        // the sidebar, so that we don't have to deal with edge
        // cases like removing the last pinned stream (and removing
        // the divider).

        this.rows.delete(stream_id);
    }
}
export const stream_sidebar = new StreamSidebar();

function get_search_term() {
    const $search_box = $(".stream-list-filter");
    const search_term = $search_box.expectOne().val().trim();
    return search_term;
}

export function add_sidebar_row(sub) {
    create_sidebar_row(sub);
    build_stream_list();
    stream_cursor.redraw();
}

export function remove_sidebar_row(stream_id) {
    stream_sidebar.remove_row(stream_id);
    build_stream_list();
    stream_cursor.redraw();
}

export function create_initial_sidebar_rows() {
    // This code is slightly opaque, but it ends up building
    // up list items and attaching them to the "sub" data
    // structures that are kept in stream_data.js.
    const subs = stream_data.subscribed_subs();

    for (const sub of subs) {
        create_sidebar_row(sub);
    }
}

export function build_stream_list(force_rerender) {
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

    // The main logic to build the list is in stream_sort.js, and
    // we get five lists of streams (pinned/normal/muted_pinned/muted_normal/dormant).
    const stream_groups = stream_sort.sort_groups(streams, get_search_term());

    if (stream_groups.same_as_before && !force_rerender) {
        return;
    }

    const elems = [];

    function add_sidebar_li(stream_id) {
        const sidebar_row = stream_sidebar.get_row(stream_id);
        sidebar_row.update_whether_active();
        elems.push(sidebar_row.get_li());
    }

    topic_list.clear();
    $parent.empty();

    const any_pinned_streams = stream_groups.pinned_streams.length > 0;
    const any_normal_streams = stream_groups.normal_streams.length > 0;
    const any_dormant_streams = stream_groups.dormant_streams.length > 0;

    if (any_pinned_streams) {
        elems.push(
            render_stream_subheader({
                subheader_name: $t({
                    defaultMessage: "Pinned",
                }),
            }),
        );
    }

    for (const stream_id of stream_groups.pinned_streams) {
        add_sidebar_li(stream_id);
    }

    for (const stream_id of stream_groups.muted_pinned_streams) {
        add_sidebar_li(stream_id);
    }

    if (any_normal_streams) {
        elems.push(
            render_stream_subheader({
                subheader_name: $t({
                    defaultMessage: "Active",
                }),
            }),
        );
    }

    for (const stream_id of stream_groups.normal_streams) {
        add_sidebar_li(stream_id);
    }

    for (const stream_id of stream_groups.muted_active_streams) {
        add_sidebar_li(stream_id);
    }

    if (any_dormant_streams) {
        elems.push(
            render_stream_subheader({
                subheader_name: $t({
                    defaultMessage: "Inactive",
                }),
            }),
        );
    }

    for (const stream_id of stream_groups.dormant_streams) {
        add_sidebar_li(stream_id);
    }

    $parent.append(elems);
}

export function get_stream_li(stream_id) {
    const row = stream_sidebar.get_row(stream_id);
    if (!row) {
        // Not all streams are in the sidebar, so we don't report
        // an error here, and it's up for the caller to error if
        // they expected otherwise.
        return undefined;
    }

    const $li = row.get_li();
    if (!$li) {
        blueslip.error("Cannot find li for id " + stream_id);
        return undefined;
    }

    if ($li.length > 1) {
        blueslip.error("stream_li has too many elements for " + stream_id);
        return undefined;
    }

    return $li;
}

export function update_subscribe_to_more_streams_link() {
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

function stream_id_for_elt($elt) {
    return Number.parseInt($elt.attr("data-stream-id"), 10);
}

export function zoom_in_topics(options) {
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
        } else {
            $elt.hide();
        }
    });

    // we also need to hide the PM section and allow
    // stream list to take complete left-sidebar in zoomedIn view.
    $(".private_messages_container").hide();
}

export function zoom_out_topics() {
    // Show PM section
    $(".private_messages_container").show();

    // Show stream list titles and pinned stream splitter
    $(".stream-filters-label").each(function () {
        $(this).show();
    });
    $(".streams_subheader").each(function () {
        $(this).show();
    });

    $("#streams_list").expectOne().removeClass("zoom-in").addClass("zoom-out");
    $("#stream_filters li.narrow-filter").show();
}

export function set_in_home_view(stream_id, in_home) {
    const $li = get_stream_li(stream_id);
    if (!$li) {
        blueslip.error("passed in bad stream id " + stream_id);
        return;
    }

    if (in_home) {
        $li.removeClass("out_of_home_view");
    } else {
        $li.addClass("out_of_home_view");
    }
}

function build_stream_sidebar_li(sub) {
    const name = sub.name;
    const args = {
        name,
        id: sub.stream_id,
        uri: hash_util.by_stream_url(sub.stream_id),
        is_muted: stream_data.is_muted(sub.stream_id) === true,
        invite_only: sub.invite_only,
        is_web_public: sub.is_web_public,
        color: sub.color,
        pin_to_top: sub.pin_to_top,
    };
    args.dark_background = color_class.get_css_class(args.color);
    const $list_item = $(render_stream_sidebar_row(args));
    return $list_item;
}

class StreamSidebarRow {
    constructor(sub) {
        this.sub = sub;
        this.$list_item = build_stream_sidebar_li(sub);
        this.update_unread_count();
    }

    update_whether_active() {
        if (stream_data.is_active(this.sub) || this.sub.pin_to_top === true) {
            this.$list_item.removeClass("inactive_stream");
        } else {
            this.$list_item.addClass("inactive_stream");
        }
    }

    get_li() {
        return this.$list_item;
    }

    remove() {
        this.$list_item.remove();
    }

    update_unread_count() {
        const count = unread.num_unread_for_stream(this.sub.stream_id);
        const stream_has_any_unread_mention_messages = unread.stream_has_any_unread_mentions(
            this.sub.stream_id,
        );
        update_count_in_dom(this.$list_item, count, stream_has_any_unread_mention_messages);
    }
}

function build_stream_sidebar_row(sub) {
    stream_sidebar.set_row(sub.stream_id, new StreamSidebarRow(sub));
}

export function create_sidebar_row(sub) {
    if (stream_sidebar.has_row_for(sub.stream_id)) {
        // already exists
        blueslip.warn("Dup try to build sidebar row for stream " + sub.stream_id);
        return;
    }
    build_stream_sidebar_row(sub);
}

export function redraw_stream_privacy(sub) {
    const $li = get_stream_li(sub.stream_id);
    if (!$li) {
        // We don't want to raise error here, if we can't find stream in subscription
        // stream list. Cause we allow org admin to update stream privacy
        // even if they don't subscribe to public stream.
        return;
    }

    const $div = $li.find(".stream-privacy");
    const dark_background = color_class.get_css_class(sub.color);

    const args = {
        invite_only: sub.invite_only,
        is_web_public: sub.is_web_public,
        dark_background,
    };

    const html = render_stream_privacy(args);
    $div.html(html);
}

function set_stream_unread_count(stream_id, count, stream_has_any_unread_mention_messages) {
    const $stream_li = get_stream_li(stream_id);
    if (!$stream_li) {
        // This can happen for legitimate reasons, but we warn
        // just in case.
        blueslip.warn("stream id no longer in sidebar: " + stream_id);
        return;
    }
    update_count_in_dom($stream_li, count, stream_has_any_unread_mention_messages);
}

export function update_streams_sidebar(force_rerender) {
    build_stream_list(force_rerender);

    stream_cursor.redraw();

    if (!narrow_state.active()) {
        return;
    }

    const filter = narrow_state.filter();

    update_stream_sidebar_for_narrow(filter);
}

export function update_dom_with_unread_counts(counts) {
    // counts.stream_count maps streams to counts
    for (const [stream_id, count] of counts.stream_count) {
        const stream_has_any_unread_mention_messages =
            counts.streams_with_mentions.includes(stream_id);
        set_stream_unread_count(stream_id, count, stream_has_any_unread_mention_messages);
    }
}

export function rename_stream(sub) {
    // The sub object is expected to already have the updated name
    build_stream_sidebar_row(sub);
    update_streams_sidebar(true); // big hammer
}

export function refresh_pinned_or_unpinned_stream(sub) {
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
            blueslip.error("passed in bad stream id " + sub.stream_id);
            return;
        }
        scroll_stream_into_view($stream_li);
    }
}

export function refresh_muted_or_unmuted_stream(sub) {
    build_stream_sidebar_row(sub);
    update_streams_sidebar();
}

export function get_sidebar_stream_topic_info(filter) {
    const result = {
        stream_id: undefined,
        topic_selected: false,
    };

    const op_stream = filter.operands("stream");
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

function deselect_stream_items() {
    $("ul#stream_filters li").removeClass("active-filter");
}

export function update_stream_sidebar_for_narrow(filter) {
    const info = get_sidebar_stream_topic_info(filter);

    deselect_stream_items();

    const stream_id = info.stream_id;

    if (!stream_id) {
        topic_zoom.clear_topics();
        return undefined;
    }

    const $stream_li = get_stream_li(stream_id);

    if (!$stream_li) {
        // This is a sanity check.  When we narrow to a subscribed
        // stream, there will always be a stream list item
        // corresponding to that stream in our sidebar.  This error
        // stopped appearing from March 2018 until at least
        // April 2020, so if it appears again, something regressed.
        blueslip.error("No stream_li for subscribed stream " + stream_id);
        topic_zoom.clear_topics();
        return undefined;
    }

    if (!info.topic_selected) {
        $stream_li.addClass("active-filter");
    }

    if (stream_id !== topic_list.active_stream_id()) {
        topic_zoom.clear_topics();
    }

    topic_list.rebuild($stream_li, stream_id);

    return $stream_li;
}

export function handle_narrow_activated(filter) {
    const $stream_li = update_stream_sidebar_for_narrow(filter);
    if ($stream_li) {
        scroll_stream_into_view($stream_li);
    }
}

export function handle_narrow_deactivated() {
    deselect_stream_items();
    topic_zoom.clear_topics();
}

function focus_stream_filter(e) {
    stream_cursor.reset();
    e.stopPropagation();
}

function keydown_enter_key() {
    const stream_id = stream_cursor.get_key();

    if (stream_id === undefined) {
        // This can happen for empty searches, no need to warn.
        return;
    }

    const sub = sub_store.get(stream_id);

    if (sub === undefined) {
        blueslip.error("Unknown stream_id for search/enter: " + stream_id);
        return;
    }

    clear_and_hide_search();
    narrow.by("stream", sub.name, {trigger: "sidebar enter key"});
}

function actually_update_streams_for_search() {
    update_streams_sidebar();
    resize.resize_page_components();
    stream_cursor.reset();
}

const update_streams_for_search = _.throttle(actually_update_streams_for_search, 50);

export function initialize() {
    create_initial_sidebar_rows();

    // We build the stream_list now.  It may get re-built again very shortly
    // when new messages come in, but it's fairly quick.
    build_stream_list();
    update_subscribe_to_more_streams_link();
    set_event_handlers();
}

export function set_event_handlers() {
    $("#stream_filters").on("click", "li .subscription_block", (e) => {
        if (e.metaKey || e.ctrlKey) {
            return;
        }
        const stream_id = stream_id_for_elt($(e.target).parents("li"));
        const sub = sub_store.get(stream_id);
        popovers.hide_all();
        narrow.by("stream", sub.name, {trigger: "sidebar"});

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

    function toggle_pm_header_icon() {
        if (pm_list.is_private_messages_collapsed()) {
            return;
        }

        const scroll_position = $(
            "#left_sidebar_scroll_container .simplebar-content-wrapper",
        ).scrollTop();
        const pm_list_height = $("#private_messages_list").height();
        if (scroll_position > pm_list_height) {
            $("#toggle_private_messages_section_icon").addClass("fa-caret-right");
            $("#toggle_private_messages_section_icon").removeClass("fa-caret-down");
        } else {
            $("#toggle_private_messages_section_icon").addClass("fa-caret-down");
            $("#toggle_private_messages_section_icon").removeClass("fa-caret-right");
        }
    }

    // check for user scrolls on streams list for first time
    ui.get_scroll_element($("#left_sidebar_scroll_container")).on("scroll", () => {
        has_scrolled = true;
        toggle_pm_header_icon();
    });

    stream_cursor = new ListCursor({
        list: {
            scroll_container_sel: "#left_sidebar_scroll_container",
            find_li(opts) {
                const stream_id = opts.key;
                const li = get_stream_li(stream_id);
                return li;
            },
            first_key: stream_sort.first_stream_id,
            prev_key: stream_sort.prev_stream_id,
            next_key: stream_sort.next_stream_id,
        },
        highlight_class: "highlighted_stream",
    });

    const $search_input = $(".stream-list-filter").expectOne();

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
    $search_input.on("focusout", () => stream_cursor.clear());
    $search_input.on("input", update_streams_for_search);
}

export function searching() {
    return $(".stream-list-filter").expectOne().is(":focus");
}

export function escape_search() {
    const $filter = $(".stream-list-filter").expectOne();
    if ($filter.val() === "") {
        clear_and_hide_search();
        return;
    }
    $filter.val("");
    update_streams_for_search();
}

export function clear_search(e) {
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

export function show_search_section() {
    $(".stream_search_section").expectOne().removeClass("notdisplayed");
    resize.resize_stream_filters_container();
}

export function hide_search_section() {
    $(".stream_search_section").expectOne().addClass("notdisplayed");
    resize.resize_stream_filters_container();
}

export function initiate_search() {
    show_search_section();

    const $filter = $(".stream-list-filter").expectOne();

    if (
        // Check if left column is a popover and is not visible.
        $("#streamlist-toggle").is(":visible") &&
        !$(".app-main .column-left").hasClass("expanded")
    ) {
        popovers.hide_all();
        stream_popover.show_streamlist_sidebar();
    }
    $filter.trigger("focus");

    stream_cursor.reset();
}

export function clear_and_hide_search() {
    const $filter = $(".stream-list-filter");
    if ($filter.val() !== "") {
        $filter.val("");
        update_streams_for_search();
    }
    stream_cursor.clear();
    $filter.trigger("blur");

    hide_search_section();
}

export function toggle_filter_displayed(e) {
    if ($(".stream_search_section.notdisplayed").length === 0) {
        clear_and_hide_search();
    } else {
        initiate_search();
    }
    e.preventDefault();
}

export function scroll_stream_into_view($stream_li) {
    const $container = $("#left_sidebar_scroll_container");

    if ($stream_li.length !== 1) {
        blueslip.error("Invalid stream_li was passed in");
        return;
    }
    const stream_header_height = $("#streams_header").outerHeight();
    scroll_util.scroll_element_into_container($stream_li, $container, stream_header_height);
}

export function maybe_scroll_narrow_into_view() {
    // we don't want to interfere with user scrolling once the page loads
    if (has_scrolled) {
        return;
    }

    const $stream_li = get_current_stream_li();
    if ($stream_li) {
        scroll_stream_into_view($stream_li);
    }
}

export function get_current_stream_li() {
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
