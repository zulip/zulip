import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";

import * as activity from "./activity.ts";
import * as blueslip from "./blueslip.ts";
import * as buddy_data from "./buddy_data.ts";
import {buddy_list} from "./buddy_list.ts";
import * as keydown_util from "./keydown_util.ts";
import {ListCursor} from "./list_cursor.ts";
import * as loading from "./loading.ts";
import * as narrow_state from "./narrow_state.ts";
import * as peer_data from "./peer_data.ts";
import * as people from "./people.ts";
import * as pm_list from "./pm_list.ts";
import * as popovers from "./popovers.ts";
import * as presence from "./presence.ts";
import type {PresenceInfoFromEvent} from "./presence.ts";
import * as sidebar_ui from "./sidebar_ui.ts";
import {realm} from "./state_data.ts";
import * as ui_util from "./ui_util.ts";
import type {FullUnreadCountsData} from "./unread.ts";
import {UserSearch} from "./user_search.ts";
import * as util from "./util.ts";

export let user_cursor: ListCursor<number> | undefined;
export let user_filter: UserSearch | undefined;

// Function initialized from `ui_init` to avoid importing narrow.js and causing circular imports.
let narrow_by_email: (email: string) => void;

function get_pm_list_item(user_id: string): JQuery | undefined {
    return buddy_list.find_li({
        key: Number.parseInt(user_id, 10),
    });
}

function set_pm_count(user_ids_string: string, count: number): void {
    const $pm_li = get_pm_list_item(user_ids_string);
    if ($pm_li !== undefined) {
        ui_util.update_unread_count_in_dom($pm_li, count);
    }
}

export function update_dom_with_unread_counts(counts: FullUnreadCountsData): void {
    // counts is just a data object that gets calculated elsewhere
    // Our job is to update some DOM elements.

    for (const [user_ids_string, count] of counts.pm_count) {
        // TODO: just use user_ids_string in our markup
        const is_pm = !user_ids_string.includes(",");
        if (is_pm) {
            set_pm_count(user_ids_string, count);
        }
    }
}

export function clear_for_testing(): void {
    user_cursor = undefined;
    user_filter = undefined;
}

export let update_presence_indicators = (): void => {
    $("[data-presence-indicator-user-id]").each(function () {
        const user_id = Number.parseInt($(this).attr("data-presence-indicator-user-id") ?? "", 10);
        const is_deactivated = !people.is_active_user_for_popover(user_id || 0);
        assert(!Number.isNaN(user_id));
        const user_circle_class = buddy_data.get_user_circle_class(user_id, is_deactivated);
        const user_circle_class_with_icon = `${user_circle_class} zulip-icon-${user_circle_class}`;
        $(this)
            .removeClass(
                `
                user-circle-active zulip-icon-user-circle-active
                user-circle-idle zulip-icon-user-circle-idle
                user-circle-offline zulip-icon-user-circle-offline
            `,
            )
            .addClass(user_circle_class_with_icon);
    });
};

export function rewire_update_presence_indicators(value: typeof update_presence_indicators): void {
    update_presence_indicators = value;
}

export function redraw_user(user_id: number): void {
    if (realm.realm_presence_disabled) {
        return;
    }

    const filter_text = get_filter_text();

    if (!buddy_data.matches_filter(filter_text, user_id)) {
        return;
    }

    buddy_list.insert_or_move([user_id]);
    update_presence_indicators();
}

export function rerender_user_sidebar_participants(): void {
    if (!narrow_state.stream_id() || narrow_state.topic() === undefined) {
        return;
    }

    buddy_list.rerender_participants();
}

export function check_should_redraw_new_user(user_id: number): boolean {
    if (realm.realm_presence_disabled) {
        return false;
    }

    const user_is_in_presence_info = presence.presence_info.has(user_id);
    const user_not_yet_known = people.maybe_get_user_by_id(user_id, true) === undefined;
    return user_is_in_presence_info && user_not_yet_known;
}

export function searching(): boolean {
    return user_filter?.searching() ?? false;
}

export let build_user_sidebar = (): number[] | undefined => {
    if (realm.realm_presence_disabled) {
        return undefined;
    }

    assert(user_filter !== undefined);
    const filter_text = user_filter.text();

    const all_user_ids = buddy_data.get_filtered_and_sorted_user_ids(filter_text);

    buddy_list.populate({all_user_ids});

    return all_user_ids; // for testing
};

export function rewire_build_user_sidebar(value: typeof build_user_sidebar): void {
    build_user_sidebar = value;
}

export function remove_loading_indicator_for_search(): void {
    loading.destroy_indicator($("#buddy-list-loading-subscribers"));
    $("#buddy_list_wrapper").show();
}

// We need to make sure we have all subscribers before displaying
// users during search, because we show all matching users and
// sort them by if they're subscribed. We store all pending fetches,
// in case we navigate away from a stream and back to it and kick
// off another search. We also store the current pending fetch so
// we know if it's still relevant once it's completed.
let pending_fetch_for_search_stream_id: number | undefined;
const all_pending_fetches_for_search = new Map<number, Promise<void>>();

export async function await_pending_promise_for_testing(): Promise<void> {
    assert(pending_fetch_for_search_stream_id !== undefined);
    await all_pending_fetches_for_search.get(pending_fetch_for_search_stream_id);
}

function do_update_users_for_search(): void {
    // Hide all the popovers but not userlist sidebar
    // when the user is searching.
    popovers.hide_all();

    const stream_id = narrow_state.stream_id(narrow_state.filter(), true);
    if (!stream_id || peer_data.has_full_subscriber_data(stream_id)) {
        pending_fetch_for_search_stream_id = undefined;
        build_user_sidebar();
        assert(user_cursor !== undefined);
        user_cursor.reset();
        return;
    }

    pending_fetch_for_search_stream_id = stream_id;

    // If we're already fetching for this stream, we don't need to wait for
    // another promise. The sidebar will be updated once that promise resolves.
    if (all_pending_fetches_for_search.has(stream_id)) {
        return;
    }

    all_pending_fetches_for_search.set(
        stream_id,
        (async () => {
            $("#buddy_list_wrapper").hide();
            loading.make_indicator($("#buddy-list-loading-subscribers"));
            await peer_data.maybe_fetch_stream_subscribers(stream_id);
            all_pending_fetches_for_search.delete(stream_id);

            // If we changed narrows during the fetch, don't rebuild the sidebar
            // anymore. Let the new narrow handle its own state. The loading indicator
            // should have already been removed on narrow change.
            if (pending_fetch_for_search_stream_id !== stream_id) {
                return;
            }
            remove_loading_indicator_for_search();
            pending_fetch_for_search_stream_id = undefined;
            build_user_sidebar();
            assert(user_cursor !== undefined);
            user_cursor.reset();
        })(),
    );
}

const update_users_for_search = _.throttle(do_update_users_for_search, 50);

export function initialize(opts: {narrow_by_email: (email: string) => void}): void {
    narrow_by_email = opts.narrow_by_email;

    set_cursor_and_filter();

    build_user_sidebar();

    buddy_list.start_scroll_handler();

    function get_full_presence_list_update(): void {
        activity.send_presence_to_server(redraw);
    }

    /* Time between keep-alive pings */
    const active_ping_interval_ms = realm.server_presence_ping_interval_seconds * 1000;
    util.call_function_periodically(get_full_presence_list_update, active_ping_interval_ms);

    // Let the server know we're here, but do not pass
    // redraw, since we just got all this info in page_params.
    activity.send_presence_to_server();
}

export function update_presence_info(
    user_id: number,
    info: PresenceInfoFromEvent,
    server_time: number,
): void {
    // There can be some case where the presence event
    // was set for an inaccessible user if
    // CAN_ACCESS_ALL_USERS_GROUP_LIMITS_PRESENCE is
    // disabled. We just ignore that event and return.
    const person = people.maybe_get_user_by_id(user_id, true);
    if (person === undefined || person.is_inaccessible_user) {
        return;
    }

    presence.update_info_from_event(user_id, info, server_time);
    redraw_user(user_id);
    pm_list.update_private_messages();
}

export function redraw(): void {
    build_user_sidebar();
    assert(user_cursor !== undefined);
    user_cursor.redraw();
    pm_list.update_private_messages();
    update_presence_indicators();
}

export function reset_users(): void {
    // Call this when we're leaving the search widget.
    build_user_sidebar();
    assert(user_cursor !== undefined);
    user_cursor.clear();
}

export function narrow_for_user(opts: {$li: JQuery}): void {
    const user_id = buddy_list.get_user_id_from_li({$li: opts.$li});
    narrow_for_user_id({user_id});
}

export function narrow_for_user_id(opts: {user_id: number}): void {
    const person = people.get_by_user_id(opts.user_id);
    const email = person.email;

    assert(narrow_by_email);
    narrow_by_email(email);
    assert(user_filter !== undefined);
    user_filter.clear_search();
}

function keydown_enter_key(): void {
    assert(user_cursor !== undefined);
    const user_id = user_cursor.get_key();
    if (user_id === undefined) {
        return;
    }

    narrow_for_user_id({user_id});
    sidebar_ui.hide_all();
    popovers.hide_all();
}

export function set_cursor_and_filter(): void {
    user_cursor = new ListCursor({
        list: buddy_list,
        highlight_class: "highlighted_user",
    });

    user_filter = new UserSearch({
        update_list: update_users_for_search,
        reset_items: reset_users,
        on_focus() {
            user_cursor!.reset();
        },
    });

    const $input = user_filter.input_field();

    $input.on("blur", () => {
        user_cursor!.clear();
    });

    keydown_util.handle({
        $elem: $input,
        handlers: {
            Enter() {
                keydown_enter_key();
                return true;
            },
            ArrowUp() {
                user_cursor!.prev();
                return true;
            },
            ArrowDown() {
                user_cursor!.next();
                return true;
            },
        },
    });
}

export function initiate_search(): void {
    if (user_filter) {
        $("body").removeClass("hide-right-sidebar");
        popovers.hide_all();
        user_filter.initiate_search();
    }
}

export function clear_search(): void {
    if (user_filter) {
        user_filter.clear_search();
        remove_loading_indicator_for_search();
    }
}

export function get_filter_text(): string {
    if (!user_filter) {
        // This may be overly defensive, but there may be
        // situations where get called before everything is
        // fully initialized.  The empty string is a fine
        // default here.
        blueslip.warn("get_filter_text() is called before initialization");
        return "";
    }

    return user_filter.text();
}
