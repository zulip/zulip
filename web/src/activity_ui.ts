import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";

import * as activity from "./activity.ts";
import * as blueslip from "./blueslip.ts";
import * as buddy_data from "./buddy_data.ts";
import {buddy_list} from "./buddy_list.ts";
import * as buddy_list_presence from "./buddy_list_presence.ts";
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
import * as scroll_util from "./scroll_util.ts";
import {realm} from "./state_data.ts";
import * as ui_util from "./ui_util.ts";
import type {FullUnreadCountsData} from "./unread.ts";
import {UserSearch} from "./user_search.ts";
import * as util from "./util.ts";

export let user_cursor: ListCursor<number> | undefined;
export let user_filter: UserSearch | undefined;

// Function initialized from `ui_init` to avoid importing narrow.js and causing circular imports.
let narrow_by_user_id: (user_id: number) => void;

export function get_narrow_by_user_id_function_for_test_code(): (user_id: number) => void {
    return narrow_by_user_id;
}

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

// Tracks which buddy list section header is currently highlighted
// during keyboard navigation (null when on a user row or nothing).
let highlighted_section_container: string | null = null;

const buddy_list_section_containers = [
    "#buddy-list-participants-container",
    "#buddy-list-users-matching-view-container",
    "#buddy-list-other-users-container",
] as const;

function get_visible_section_containers(): string[] {
    if (buddy_list.render_data.hide_headers) {
        return [];
    }
    const containers: string[] = [];
    for (const selector of buddy_list_section_containers) {
        if (!$(selector).hasClass("no-display")) {
            containers.push(selector);
        }
    }
    return containers;
}

function highlight_section_header(container_selector: string): void {
    clear_section_header_highlight();
    highlighted_section_container = container_selector;
    const $header = $(`${container_selector} .buddy-list-subsection-header`);
    $header.addClass("highlighted_section_header");
    const $scroll_container = $(buddy_list.scroll_container_selector);
    scroll_util.scroll_element_into_container($header, $scroll_container);
}

function clear_section_header_highlight(): void {
    if (highlighted_section_container !== null) {
        $(`${highlighted_section_container} .buddy-list-subsection-header`).removeClass(
            "highlighted_section_header",
        );
        highlighted_section_container = null;
    }
}

function get_buddy_list_section(
    container_selector: string,
): {user_ids: number[]; is_collapsed: boolean} | undefined {
    switch (container_selector) {
        case "#buddy-list-participants-container":
            return buddy_list.participants_section;
        case "#buddy-list-users-matching-view-container":
            return buddy_list.users_matching_view_section;
        case "#buddy-list-other-users-container":
            return buddy_list.other_users_section;
        default:
            return undefined;
    }
}

function get_section_for_user_id(user_id: number): string | undefined {
    if (buddy_list.participants_section.user_ids.includes(user_id)) {
        return "#buddy-list-participants-container";
    }
    if (buddy_list.users_matching_view_section.user_ids.includes(user_id)) {
        return "#buddy-list-users-matching-view-container";
    }
    if (buddy_list.other_users_section.user_ids.includes(user_id)) {
        return "#buddy-list-other-users-container";
    }
    return undefined;
}

function toggle_buddy_list_section(container_selector: string): void {
    switch (container_selector) {
        case "#buddy-list-participants-container":
            buddy_list.toggle_participants_section();
            break;
        case "#buddy-list-users-matching-view-container":
            buddy_list.toggle_users_matching_view_section();
            break;
        case "#buddy-list-other-users-container":
            buddy_list.toggle_other_users_section();
            break;
    }
}

export function clear_for_testing(): void {
    user_cursor = undefined;
    user_filter = undefined;
    highlighted_section_container = null;
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
    buddy_list_presence.update_indicators();
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
            await peer_data.fetch_stream_subscribers(stream_id);
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

export function initialize(opts: {narrow_by_user_id: (user_id: number) => void}): void {
    narrow_by_user_id = opts.narrow_by_user_id;

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

export function update_presence_info(info: PresenceInfoFromEvent): void {
    const presence_entry = Object.entries(info)[0];
    assert(presence_entry !== undefined);
    const [user_id_string, presence_info] = presence_entry;
    const user_id = Number.parseInt(user_id_string, 10);

    // There can be some case where the presence event
    // was set for an inaccessible user if
    // CAN_ACCESS_ALL_USERS_GROUP_LIMITS_PRESENCE is
    // disabled. We just ignore that event and return.
    const person = people.maybe_get_user_by_id(user_id, true);
    if (person === undefined || person.is_inaccessible_user) {
        return;
    }

    presence.update_info_from_event(user_id, presence_info);
    redraw_user(user_id);
    pm_list.update_private_messages();
}

export function redraw(): void {
    build_user_sidebar();
    assert(user_cursor !== undefined);
    user_cursor.redraw();
    pm_list.update_private_messages();
    buddy_list_presence.update_indicators();
}

export function reset_users(): void {
    // Call this when we're leaving the search widget.
    build_user_sidebar();
    assert(user_cursor !== undefined);
    clear_section_header_highlight();
    user_cursor.clear();
}

export function narrow_for_user(opts: {$li: JQuery}): void {
    const user_id = buddy_list.get_user_id_from_li({$li: opts.$li});
    narrow_for_user_id({user_id});
}

export function narrow_for_user_id(opts: {user_id: number}): void {
    assert(narrow_by_user_id);
    narrow_by_user_id(opts.user_id);
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
}

export let set_cursor_and_filter = (): void => {
    user_cursor = new ListCursor({
        list: buddy_list,
        highlight_class: "highlighted_user",
    });

    user_filter = new UserSearch({
        update_list: update_users_for_search,
        reset_items: reset_users,
        on_focus() {
            clear_section_header_highlight();
            user_cursor!.reset();
        },
        set_is_highlight_visible(value: boolean) {
            user_cursor!.set_is_highlight_visible(value);
        },
    });

    const $input = user_filter.input_field();

    $input.on("blur", (e) => {
        if (
            e.relatedTarget instanceof HTMLElement &&
            $(e.relatedTarget).closest(".user-list-sidebar-menu-icon").length > 0
        ) {
            return;
        }
        clear_section_header_highlight();
        user_cursor!.clear();
    });

    keydown_util.handle({
        $elem: $input,
        handlers: {
            Enter() {
                if (highlighted_section_container !== null) {
                    toggle_buddy_list_section(highlighted_section_container);
                    return true;
                }
                keydown_enter_key();
                return true;
            },
            ArrowUp() {
                const visible_headers = get_visible_section_containers();

                // On a section header: move to last user of
                // previous section, or previous header.
                if (highlighted_section_container !== null) {
                    const idx = visible_headers.indexOf(highlighted_section_container);
                    if (idx > 0) {
                        const prev_container = visible_headers[idx - 1]!;
                        const prev_section = get_buddy_list_section(prev_container);
                        if (
                            prev_section &&
                            !prev_section.is_collapsed &&
                            prev_section.user_ids.length > 0
                        ) {
                            clear_section_header_highlight();
                            user_cursor!.go_to(prev_section.user_ids.at(-1));
                            return true;
                        }
                        highlight_section_header(prev_container);
                        return true;
                    }
                    return true;
                }

                // No section headers visible: use existing behavior.
                if (visible_headers.length === 0) {
                    user_cursor!.prev();
                    return true;
                }

                const current_key = user_cursor!.get_key();
                if (current_key === undefined) {
                    return true;
                }

                if (!user_cursor!.is_highlight_visible) {
                    user_cursor!.prev();
                    return true;
                }

                // At first user of a section: move to its header.
                const current_section = get_section_for_user_id(current_key);
                if (current_section !== undefined && visible_headers.includes(current_section)) {
                    const section = get_buddy_list_section(current_section);
                    if (
                        section &&
                        section.user_ids.length > 0 &&
                        section.user_ids[0] === current_key
                    ) {
                        user_cursor!.clear();
                        highlight_section_header(current_section);
                        return true;
                    }
                }

                // Normal movement within a section.
                const prev_key = buddy_list.prev_key(current_key);
                if (prev_key === undefined) {
                    return true;
                }
                user_cursor!.go_to(prev_key);
                return true;
            },
            ArrowDown() {
                const visible_headers = get_visible_section_containers();

                // On a section header: move to first user in
                // section (if expanded), or to next header.
                if (highlighted_section_container !== null) {
                    const section = get_buddy_list_section(highlighted_section_container);
                    if (section && !section.is_collapsed && section.user_ids.length > 0) {
                        clear_section_header_highlight();
                        user_cursor!.go_to(section.user_ids[0]);
                        return true;
                    }
                    const idx = visible_headers.indexOf(highlighted_section_container);
                    if (idx !== -1 && idx < visible_headers.length - 1) {
                        highlight_section_header(visible_headers[idx + 1]!);
                        return true;
                    }
                    return true;
                }

                // No section headers visible: use existing behavior.
                if (visible_headers.length === 0) {
                    user_cursor!.next();
                    return true;
                }

                const current_key = user_cursor!.get_key();

                // First ArrowDown: land on first section header.
                if (current_key !== undefined && !user_cursor!.is_highlight_visible) {
                    user_cursor!.set_is_highlight_visible(true);
                    user_cursor!.clear();
                    highlight_section_header(visible_headers[0]!);
                    return true;
                }

                if (current_key === undefined) {
                    user_cursor!.set_is_highlight_visible(true);
                    highlight_section_header(visible_headers[0]!);
                    return true;
                }

                // Check for section boundary crossing.
                const next_key = buddy_list.next_key(current_key);
                if (next_key === undefined) {
                    // At end of navigable users. There may still be
                    // a collapsed section header to navigate to.
                    const current_section = get_section_for_user_id(current_key);
                    if (current_section !== undefined) {
                        const idx = visible_headers.indexOf(current_section);
                        if (idx !== -1 && idx < visible_headers.length - 1) {
                            user_cursor!.clear();
                            highlight_section_header(visible_headers[idx + 1]!);
                            return true;
                        }
                    }
                    return true;
                }

                const current_section = get_section_for_user_id(current_key);
                const next_section = get_section_for_user_id(next_key);

                if (
                    current_section !== next_section &&
                    next_section !== undefined &&
                    visible_headers.includes(next_section)
                ) {
                    user_cursor!.clear();
                    highlight_section_header(next_section);
                    return true;
                }

                user_cursor!.go_to(next_key);
                return true;
            },
            Tab() {
                if (highlighted_section_container !== null) {
                    return true;
                }
                const user_id = user_cursor!.get_key();
                if (user_id === undefined) {
                    return true;
                }
                const $li = buddy_list.find_li({key: user_id});
                if ($li === undefined) {
                    return true;
                }
                const $vdot = $li.find(".user-list-sidebar-menu-icon").first();
                if ($vdot.length === 0) {
                    return true;
                }
                $vdot.trigger("focus");
                return true;
            },
        },
    });

    $(".buddy-list-section").on("keydown", ".user-list-sidebar-menu-icon", (e) => {
        // When a popover is open, let the hotkey system handle
        // arrow keys and Escape so they navigate the popover.
        if (popovers.any_active() && e.key !== "Enter" && e.key !== "Tab") {
            return;
        }
        switch (e.key) {
            case "Enter":
                // Use native click so the delegated handler in
                // user_card_popover.ts fires correctly.
                if (e.currentTarget instanceof HTMLElement) {
                    e.currentTarget.click();
                }
                e.preventDefault();
                e.stopPropagation();
                break;
            case "Escape":
                $input.trigger("focus");
                e.preventDefault();
                e.stopPropagation();
                break;
            case "Tab": {
                e.preventDefault();
                e.stopPropagation();
                if (!e.shiftKey) {
                    user_cursor!.next();
                }
                // Save cursor position before focusing search, since
                // the search input's focus handler resets the cursor.
                const target_key = user_cursor!.get_key();
                $input.trigger("focus");
                if (target_key !== undefined) {
                    user_cursor!.go_to(target_key);
                }
                break;
            }
            case "ArrowDown": {
                e.preventDefault();
                e.stopPropagation();
                const old_key = user_cursor!.get_key();
                user_cursor!.next();
                const new_key = user_cursor!.get_key();
                if (new_key !== undefined && new_key !== old_key) {
                    const $li = buddy_list.find_li({key: new_key});
                    if ($li !== undefined) {
                        const $vdot = $li.find(".user-list-sidebar-menu-icon").first();
                        if ($vdot.length > 0) {
                            $vdot.trigger("focus");
                        }
                    }
                }
                break;
            }
            case "ArrowUp": {
                e.preventDefault();
                e.stopPropagation();
                const old_key = user_cursor!.get_key();
                user_cursor!.prev();
                const new_key = user_cursor!.get_key();
                if (new_key !== undefined && new_key !== old_key) {
                    const $li = buddy_list.find_li({key: new_key});
                    if ($li !== undefined) {
                        const $vdot = $li.find(".user-list-sidebar-menu-icon").first();
                        if ($vdot.length > 0) {
                            $vdot.trigger("focus");
                            return;
                        }
                    }
                }
                $input.trigger("focus");
                break;
            }
            default:
                break;
        }
    });

    $(".buddy-list-section").on("focusout", ".user-list-sidebar-menu-icon", (e) => {
        // Don't clear if focus moves to the search input or another vdot.
        if (
            e.relatedTarget instanceof HTMLElement &&
            ($(e.relatedTarget).closest(".user-list-filter").length > 0 ||
                $(e.relatedTarget).closest(".user-list-sidebar-menu-icon").length > 0)
        ) {
            return;
        }
        user_cursor!.clear();
    });
};

export function rewire_set_cursor_and_filter(value: typeof set_cursor_and_filter): void {
    set_cursor_and_filter = value;
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
