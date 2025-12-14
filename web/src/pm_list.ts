import $ from "jquery";
import _ from "lodash";
import * as z from "zod/mini";

import type {Filter} from "./filter.ts";
import {$t} from "./i18n.ts";
import {localstorage} from "./localstorage.ts";
import * as mouse_drag from "./mouse_drag.ts";
import * as pm_list_data from "./pm_list_data.ts";
import type {DisplayObject} from "./pm_list_data.ts";
import * as pm_list_dom from "./pm_list_dom.ts";
import type {PMNode} from "./pm_list_dom.ts";
import * as resize from "./resize.ts";
import * as scroll_util from "./scroll_util.ts";
import * as ui_util from "./ui_util.ts";
import type {FullUnreadCountsData} from "./unread.ts";
import * as util from "./util.ts";
import * as vdom from "./vdom.ts";

export const LEFT_SIDEBAR_DIRECT_MESSAGES_TITLE = $t({defaultMessage: "DIRECT MESSAGES"});

let prior_dom: vdom.Tag<PMNode> | undefined;

// This module manages the direct messages section in the upper
// left corner of the app.  This was split out from stream_list.ts.

const ls_key = "left_sidebar_direct_messages_collapsed_state";
const ls_schema = z._default(z.boolean(), false);
const ls = localstorage();
let private_messages_collapsed = false;
let last_direct_message_count: number | undefined;

// The direct messages section can be zoomed in to view more messages.
// This keeps track of if we're zoomed in or not.
let zoomed = false;

// Scroll position before user started searching.
let pre_search_scroll_position = 0;
let previous_search_term = "";

export function is_zoomed_in(): boolean {
    return zoomed;
}

function get_private_messages_section_header(): JQuery {
    return $("#direct-messages-section-header");
}

export function set_count(count: number): void {
    ui_util.update_unread_count_in_dom(get_private_messages_section_header(), count);
}

export function close(): void {
    private_messages_collapsed = true;
    ls.set(ls_key, private_messages_collapsed);
    update_private_messages();
}

export function _build_direct_messages_list(opts: {
    all_conversations_shown: boolean;
    conversations_to_be_shown: DisplayObject[];
    search_term: string;
}): vdom.Tag<PMNode> {
    const pm_list_nodes = opts.conversations_to_be_shown.map((conversation) =>
        pm_list_dom.keyed_pm_li(conversation),
    );
    const pm_list_info = pm_list_data.get_list_info(zoomed, opts.search_term);
    const more_conversations_unread_count = pm_list_info.more_conversations_unread_count;

    if (!opts.all_conversations_shown) {
        pm_list_nodes.push(
            pm_list_dom.more_private_conversations_li(more_conversations_unread_count),
        );
    }
    const dom_ast = pm_list_dom.pm_ul(pm_list_nodes);

    return dom_ast;
}

function set_dom_to(new_dom: vdom.Tag<PMNode>): void {
    const $container = scroll_util.get_content_element($("#direct-messages-list"));

    function replace_content(html: string): void {
        $container.html(html);
    }

    function find(): JQuery {
        return $container.find("ul");
    }

    vdom.update(replace_content, find, new_dom, prior_dom);
    prior_dom = new_dom;
}

export function update_private_messages(): void {
    const is_left_sidebar_search_active = ui_util.get_left_sidebar_search_term() !== "";
    const is_dm_section_expanded = is_left_sidebar_search_active || !private_messages_collapsed;
    $("#toggle-direct-messages-section-icon").toggleClass(
        "rotate-icon-down",
        is_dm_section_expanded,
    );
    $("#toggle-direct-messages-section-icon").toggleClass(
        "rotate-icon-right",
        !is_dm_section_expanded,
    );

    let search_term = "";
    if (zoomed) {
        const $filter = $<HTMLInputElement>(".direct-messages-list-filter").expectOne();
        search_term = $filter.val()!;
    } else if (is_left_sidebar_search_active) {
        search_term = ui_util.get_left_sidebar_search_term();
        if (util.prefix_match({value: LEFT_SIDEBAR_DIRECT_MESSAGES_TITLE, search_term})) {
            // Show all DMs if the search term matches the header text.
            search_term = "";
        }
    }

    const conversations = pm_list_data.get_conversations(search_term);
    const pm_list_info = pm_list_data.get_list_info(zoomed, search_term);
    const conversations_to_be_shown = pm_list_info.conversations_to_be_shown;

    const all_conversations_shown = conversations_to_be_shown.length === conversations.length;
    const is_header_visible =
        // Always show header when zoomed in.
        zoomed ||
        // Show header if there are conversations to be shown.
        conversations_to_be_shown.length > 0 ||
        // Show header if there are hidden conversations somehow.
        !all_conversations_shown ||
        // If there is no search term, always show the header.
        !search_term;
    $("#direct-messages-section-header").toggleClass("hidden-by-filters", !is_header_visible);

    if (!is_dm_section_expanded) {
        // In the collapsed state, we will still display the current
        // conversation, to preserve the UI invariant that there's
        // always something highlighted in the left sidebar.
        const all_conversations = pm_list_data.get_conversations();
        const active_conversation = all_conversations.find(
            (conversation) => conversation.is_active,
        );

        if (active_conversation) {
            const node = [pm_list_dom.keyed_pm_li(active_conversation)];
            const new_dom = pm_list_dom.pm_ul(node);
            set_dom_to(new_dom);
        } else {
            // Otherwise, empty the section.
            $(".dm-list").empty();
            prior_dom = undefined;
        }
    } else {
        const new_dom = _build_direct_messages_list({
            all_conversations_shown,
            conversations_to_be_shown,
            search_term,
        });
        set_dom_to(new_dom);
    }
    // Make sure to update the left sidebar heights after updating
    // direct messages.
    setTimeout(resize.resize_stream_filters_container, 0);
}

export function expand(): void {
    private_messages_collapsed = false;
    ls.set(ls_key, private_messages_collapsed);
    update_private_messages();
}

export function update_dom_with_unread_counts(
    counts: FullUnreadCountsData,
    skip_animations = false,
): void {
    // In theory, we could support passing the counts object through
    // to pm_list_data, rather than fetching it directly there. But
    // it's not an important optimization, because it's unlikely a
    // user would have 10,000s of unread direct messages where it
    // could matter.
    update_private_messages();

    // This is just the global unread count.
    const new_direct_message_count = counts.direct_message_count;
    set_count(new_direct_message_count);

    if (last_direct_message_count === undefined) {
        // We don't want to animate the DM header
        // when Zulip first loads, but we must update
        // the last DM count to correctly animate
        // the arrival of new unread DMs.
        last_direct_message_count = new_direct_message_count;
        return;
    }

    if (new_direct_message_count > last_direct_message_count && !skip_animations) {
        const $dm_header = $("#direct-messages-section-header");
        const $top_dm_item = $(".dm-list .dm-list-item:first-child");
        const top_item_active = $top_dm_item.hasClass("active-sub-filter");
        const top_item_no_unreads = $top_dm_item.hasClass("zero-dm-unreads");
        const $scroll_wrapper = $("#left_sidebar_scroll_container .simplebar-content-wrapper");
        let dms_scrolled_up = false;

        if ($scroll_wrapper.length > 0) {
            const scroll_top = $scroll_wrapper.scrollTop() ?? 0;
            dms_scrolled_up = scroll_top > 0;
        }
        // If the DMs area is scrolled up at all, we highlight the
        // DM header's count. It is possible for the DMs section to
        // be collapsed *and* the active conversation be scrolled
        // out of view, too, so we err on the side of highlighting
        // the header row.
        // If the DMs area is collapsed without the top item being
        // active, as is the case when narrowed to a DM, or if the
        // active DM item has the .zero-dm-unreads class, we highlight
        // the DM header's count.
        // That makes the assumption that a new DM has arrived in a
        // conversation other than the active one. Note that that will
        // fail animate anything--the header or the row--when an unread
        // arrives for a conversion other than the active one. But in
        // typical active DMing, unreads will be cleared immediately,
        // so that should be a fairly rare edge case.
        if (
            dms_scrolled_up ||
            (is_private_messages_collapsed() && !top_item_active) ||
            top_item_no_unreads
        ) {
            ui_util.do_new_unread_animation($dm_header);
        }
        // Unless the top item has the active-sub-filter class, which
        // we won't highlight to avoid annoying users in an active,
        // ongoing conversation, we highlight the top DM row, where
        // the newly arrived unread message will be, as the DM list
        // will be resorted by the time this logic runs.
        else if (!top_item_active) {
            ui_util.do_new_unread_animation($top_dm_item);
        }
    }

    last_direct_message_count = new_direct_message_count;
}

export function highlight_all_private_messages_view(): void {
    $(".direct-messages-container").addClass("active-direct-messages-section");
}

function unhighlight_all_private_messages_view(): void {
    $(".direct-messages-container").removeClass("active-direct-messages-section");
}

function scroll_pm_into_view($target_li: JQuery): void {
    const $container = $("#left_sidebar_scroll_container");
    const pm_header_height = $("#direct-messages-section-header").outerHeight();
    if ($target_li.length > 0) {
        scroll_util.scroll_element_into_container($target_li, $container, pm_header_height);
    }
}

function scroll_all_private_into_view(): void {
    const $container = $("#left_sidebar_scroll_container");
    const $scroll_element = scroll_util.get_scroll_element($container);
    $scroll_element.scrollTop(0);
}

export function handle_narrow_activated(filter: Filter): void {
    const active_filter = filter;
    const is_all_private_message_view = _.isEqual(active_filter.sorted_term_types(), ["is-dm"]);
    const narrow_to_private_messages_section = active_filter.terms_with_operator("dm").length > 0;
    const is_private_messages_in_view = active_filter.has_operator("dm");

    if (is_all_private_message_view) {
        // In theory, this should get expanded when we scroll to the
        // top, but empirically that doesn't occur, so we just ensure the
        // section is expanded before scrolling.
        expand();
        highlight_all_private_messages_view();
        scroll_all_private_into_view();
    } else {
        unhighlight_all_private_messages_view();
    }
    if (narrow_to_private_messages_section) {
        const current_user_ids_string = pm_list_data.get_active_user_ids_string();
        if (current_user_ids_string !== undefined) {
            const $active_filter_li = $(
                `li[data-user-ids-string='${CSS.escape(current_user_ids_string)}']`,
            );
            scroll_pm_into_view($active_filter_li);
        }
        update_private_messages();
    } else if (!is_private_messages_in_view) {
        update_private_messages();
    }
}

export function handle_message_view_deactivated(): void {
    // Since one can renarrow via the keyboard shortcut or similar, we
    // avoid disturbing the zoomed state here.
    unhighlight_all_private_messages_view();
    update_private_messages();
}

export function is_private_messages_collapsed(): boolean {
    return private_messages_collapsed;
}

export function toggle_private_messages_section(): void {
    // change the state of direct message section depending on
    // the previous state.
    if (private_messages_collapsed) {
        expand();
    } else {
        close();
    }
}

function zoom_in(): void {
    zoomed = true;
    previous_search_term = "";
    pre_search_scroll_position = 0;
    ui_util.disable_left_sidebar_search();
    update_private_messages();
    $(".direct-messages-container").removeClass("zoom-out").addClass("zoom-in");
    $("#hide-more-direct-messages").addClass("dm-zoomed-in");
    $("#streams_list").hide();
    $(".left-sidebar .right-sidebar-items").hide();

    const $filter = $(".direct-messages-list-filter").expectOne();
    $filter.trigger("focus");
}

function zoom_out(): void {
    zoomed = false;
    ui_util.enable_left_sidebar_search();
    clear_search();
    $(".direct-messages-container").removeClass("zoom-in").addClass("zoom-out");
    $("#hide-more-direct-messages").removeClass("dm-zoomed-in");
    $("#streams_list").show();
    $(".left-sidebar .right-sidebar-items").show();
}

export function clear_search(): void {
    const $filter = $(".direct-messages-list-filter").expectOne();
    $filter.val("");
    update_private_messages();
    $filter.trigger("blur");
}

export function initialize(): void {
    // Restore collapsed status.
    private_messages_collapsed = ls_schema.parse(ls.get(ls_key));
    if (private_messages_collapsed) {
        close();
    } else {
        expand();
    }

    $(".direct-messages-container").on("click", "#show-more-direct-messages", (e) => {
        e.stopPropagation();
        e.preventDefault();

        zoom_in();
    });

    $(".dm-list").on("click", ".dm-box", (e) => {
        // To avoid the click behavior if a dm box is selected.
        if (mouse_drag.is_drag(e)) {
            e.preventDefault();
        }
    });

    $("#left-sidebar").on("click", "#hide-more-direct-messages", (e) => {
        e.stopPropagation();
        e.preventDefault();

        zoom_out();
    });

    const throttled_update_private_message = _.throttle(() => {
        const $filter = $<HTMLInputElement>(".direct-messages-list-filter").expectOne();
        const search_term = $filter.val()!;
        const is_previous_search_term_empty = previous_search_term === "";
        previous_search_term = search_term;

        const left_sidebar_scroll_container = scroll_util.get_left_sidebar_scroll_container();
        if (search_term === "") {
            requestAnimationFrame(() => {
                update_private_messages();
                // Restore previous scroll position.
                left_sidebar_scroll_container.scrollTop(pre_search_scroll_position);
            });
        } else {
            if (is_previous_search_term_empty) {
                // Store original scroll position to be restored later.
                pre_search_scroll_position = left_sidebar_scroll_container.scrollTop()!;
            }
            requestAnimationFrame(() => {
                update_private_messages();
                // Always scroll to top when there is a search term present.
                left_sidebar_scroll_container.scrollTop(0);
            });
        }
    }, 50);

    $(".direct-messages-container").on("input", ".direct-messages-list-filter", (e) => {
        e.preventDefault();

        throttled_update_private_message();
    });

    $(".direct-messages-container").on("mouseenter", () => {
        $("#direct-messages-section-header").addClass("hover-over-dm-section");
    });

    $(".direct-messages-container").on("mouseleave", () => {
        $("#direct-messages-section-header").removeClass("hover-over-dm-section");
    });
}
