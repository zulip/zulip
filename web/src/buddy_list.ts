import $ from "jquery";
import assert from "minimalistic-assert";
import tippy from "tippy.js";

import render_section_header from "../templates/buddy_list/section_header.hbs";
import render_view_all_subscribers from "../templates/buddy_list/view_all_subscribers.hbs";
import render_view_all_users from "../templates/buddy_list/view_all_users.hbs";
import render_empty_list_widget_for_list from "../templates/empty_list_widget_for_list.hbs";
import render_presence_row from "../templates/presence_row.hbs";
import render_presence_rows from "../templates/presence_rows.hbs";

import * as blueslip from "./blueslip";
import * as buddy_data from "./buddy_data";
import type {BuddyUserInfo} from "./buddy_data";
import {media_breakpoints_num} from "./css_variables";
import * as hash_util from "./hash_util";
import {$t} from "./i18n";
import * as message_viewport from "./message_viewport";
import * as narrow_state from "./narrow_state";
import * as padded_widget from "./padded_widget";
import * as peer_data from "./peer_data";
import * as people from "./people";
import * as scroll_util from "./scroll_util";
import * as stream_data from "./stream_data";
import type {StreamSubscription} from "./sub_store";
import {INTERACTIVE_HOVER_DELAY} from "./tippyjs";
import {user_settings} from "./user_settings";

function get_formatted_sub_count(sub_count: number): string {
    if (sub_count < 1000) {
        return sub_count.toString();
    }
    return new Intl.NumberFormat(user_settings.default_language, {notation: "compact"}).format(
        sub_count,
    );
}

function total_subscriber_count(
    current_sub: StreamSubscription | undefined,
    pm_ids_set: Set<number>,
): number {
    // Includes inactive users who might not show up in the buddy list.
    if (current_sub) {
        return peer_data.get_subscriber_count(current_sub.stream_id, false);
    } else if (pm_ids_set.size) {
        const pm_ids_list = [...pm_ids_set];
        // Plus one for the "me" user, who isn't in the recipients list (except
        // for when it's a private message conversation with only "me" in it).
        if (pm_ids_list.length === 1 && people.is_my_user_id(pm_ids_list[0])) {
            return 1;
        }
        return pm_ids_list.length + 1;
    }
    return 0;
}

function should_hide_headers(
    current_sub: StreamSubscription | undefined,
    pm_ids_set: Set<number>,
): boolean {
    // If we aren't in a stream/DM view, then there's never "other"
    // users, so we don't show section headers and only show one
    // untitled section.
    return !current_sub && !pm_ids_set.size;
}

type BuddyListRenderData = {
    current_sub: StreamSubscription | undefined;
    pm_ids_set: Set<number>;
    subscriber_count: number;
    other_users_count: number;
    total_user_count: number;
    hide_headers: boolean;
};

function get_render_data(): BuddyListRenderData {
    const current_sub = narrow_state.stream_sub();
    const pm_ids_set = narrow_state.pm_ids_set();

    const subscriber_count = total_subscriber_count(current_sub, pm_ids_set);
    const total_user_count = people.get_active_human_count();
    const other_users_count = total_user_count - subscriber_count;
    const hide_headers = should_hide_headers(current_sub, pm_ids_set);

    return {
        current_sub,
        pm_ids_set,
        subscriber_count,
        other_users_count,
        total_user_count,
        hide_headers,
    };
}

class BuddyListConf {
    matching_view_list_selector = "#buddy-list-users-matching-view";
    other_user_list_selector = "#buddy-list-other-users";
    scroll_container_selector = "#buddy_list_wrapper";
    item_selector = "li.user_sidebar_entry";
    padding_selector = "#buddy_list_wrapper_padding";
    compare_function = buddy_data.compare_function;

    items_to_html(opts: {items: BuddyUserInfo[]}): string {
        const html = render_presence_rows({presence_rows: opts.items});
        return html;
    }

    item_to_html(opts: {item: BuddyUserInfo}): string {
        const html = render_presence_row(opts.item);
        return html;
    }

    get_li_from_user_id(opts: {user_id: number}): JQuery {
        const user_id = opts.user_id;
        const $buddy_list_container = $("#buddy_list_wrapper");
        return $buddy_list_container.find(
            `${this.item_selector}[data-user-id='${CSS.escape(user_id.toString())}']`,
        );
    }

    get_user_id_from_li(opts: {$li: JQuery}): number {
        const user_id = opts.$li.expectOne().attr("data-user-id");
        assert(user_id !== undefined);
        return Number.parseInt(user_id, 10);
    }

    get_data_from_user_ids(user_ids: number[]): BuddyUserInfo[] {
        const data = buddy_data.get_items_for_users(user_ids);
        return data;
    }

    height_to_fill(): number {
        // Because the buddy list gets sized dynamically, we err on the side
        // of using the height of the entire viewport for deciding
        // how much content to render.  Even on tall monitors this should
        // still be a significant optimization for orgs with thousands of
        // users.
        const height = message_viewport.height();
        return height;
    }
}

export class BuddyList extends BuddyListConf {
    all_user_ids: number[] = [];
    users_matching_view_ids: number[] = [];
    other_user_ids: number[] = [];
    users_matching_view_is_collapsed = false;
    other_users_is_collapsed = false;
    render_count = 0;
    render_data = get_render_data();
    // This is a bit of a hack to make sure we at least have
    // an empty list to start, before we get the initial payload.
    $users_matching_view_container = $(this.matching_view_list_selector);
    $other_users_container = $(this.other_user_list_selector);

    initialize_tooltips(): void {
        $("#right-sidebar").on(
            "mouseenter",
            ".buddy-list-heading",
            function (this: HTMLElement, e) {
                e.stopPropagation();
                const $elem = $(this);
                let placement: "left" | "auto" = "left";
                if (window.innerWidth < media_breakpoints_num.md) {
                    // On small devices display tooltips based on available space.
                    // This will default to "bottom" placement for this tooltip.
                    placement = "auto";
                }
                tippy($elem[0], {
                    // Because the buddy list subheadings are potential click targets
                    // for purposes having nothing to do with the subscriber count
                    // (collapsing/expanding), we delay showing the tooltip until the
                    // user lingers a bit longer.
                    delay: INTERACTIVE_HOVER_DELAY,
                    // Don't show tooltip on touch devices (99% mobile) since touch
                    // pressing on users in the left or right sidebar leads to narrow
                    // being changed and the sidebar is hidden. So, there is no user
                    // displayed to show tooltip for. It is safe to show the tooltip
                    // on long press but it not worth the inconvenience of having a
                    // tooltip hanging around on a small mobile screen if anything
                    // going wrong.
                    touch: false,
                    arrow: true,
                    placement,
                    showOnCreate: true,
                    onShow(instance) {
                        let tooltip_text;
                        const current_sub = narrow_state.stream_sub();
                        const pm_ids_set = narrow_state.pm_ids_set();
                        const subscriber_count = total_subscriber_count(current_sub, pm_ids_set);
                        const elem_id = $elem.attr("id");
                        if (elem_id === "buddy-list-users-matching-view-section-heading") {
                            if (current_sub) {
                                tooltip_text = $t(
                                    {
                                        defaultMessage:
                                            "{N, plural, one {# subscriber} other {# subscribers}}",
                                    },
                                    {N: subscriber_count},
                                );
                            } else {
                                tooltip_text = $t(
                                    {
                                        defaultMessage:
                                            "{N, plural, one {# participant} other {# participants}}",
                                    },
                                    {N: subscriber_count},
                                );
                            }
                        } else {
                            const total_user_count = people.get_active_human_count();
                            const other_users_count = total_user_count - subscriber_count;
                            tooltip_text = $t(
                                {
                                    defaultMessage:
                                        "{N, plural, one {# other user} other {# other users}}",
                                },
                                {N: other_users_count},
                            );
                        }
                        instance.setContent(tooltip_text);
                    },
                    onHidden(instance) {
                        instance.destroy();
                    },
                    appendTo: () => document.body,
                });
            },
        );
    }

    populate(opts: {all_user_ids: number[]}): void {
        this.render_count = 0;
        this.$users_matching_view_container.empty();
        this.users_matching_view_ids = [];
        this.$other_users_container.empty();
        this.other_user_ids = [];

        // Reset data to be relevant for this current view.
        this.render_data = get_render_data();

        // We rely on our caller to give us items
        // in already-sorted order.
        this.all_user_ids = opts.all_user_ids;

        this.fill_screen_with_content();

        $("#buddy-list-users-matching-view-container .view-all-subscribers-link").remove();
        $("#buddy-list-other-users-container .view-all-users-link").remove();
        if (!buddy_data.get_is_searching_users()) {
            this.render_view_user_list_links();
        }

        this.render_section_headers();
        if (this.render_data.hide_headers) {
            // Ensure the section isn't collapsed, because we're hiding its header
            // so there's no way to collapse or uncollapse the list in this view.
            $("#buddy-list-other-users-container").toggleClass("collapsed", false);
        } else {
            $("#buddy-list-other-users-container").toggleClass(
                "collapsed",
                this.other_users_is_collapsed,
            );
            this.update_empty_list_placeholders();
        }
    }

    update_empty_list_placeholders(): void {
        const {subscriber_count, other_users_count} = this.render_data;
        const has_inactive_users_matching_view =
            subscriber_count > this.users_matching_view_ids.length;
        const has_inactive_other_users = other_users_count > this.other_user_ids.length;

        let matching_view_empty_list_message;
        let other_users_empty_list_message;

        if (buddy_data.get_is_searching_users()) {
            matching_view_empty_list_message = $t({defaultMessage: "No matching users."});
            other_users_empty_list_message = $t({defaultMessage: "No matching users."});
        } else {
            if (has_inactive_users_matching_view) {
                matching_view_empty_list_message = $t({defaultMessage: "No active users."});
            } else {
                matching_view_empty_list_message = $t({defaultMessage: "None."});
            }

            if (has_inactive_other_users) {
                other_users_empty_list_message = $t({defaultMessage: "No active users."});
            } else {
                other_users_empty_list_message = $t({defaultMessage: "None."});
            }
        }

        $("#buddy-list-users-matching-view").attr(
            "data-search-results-empty",
            matching_view_empty_list_message,
        );
        if ($("#buddy-list-users-matching-view .empty-list-message").length) {
            const empty_list_widget_html = render_empty_list_widget_for_list({
                matching_view_empty_list_message,
            });
            $("#buddy-list-users-matching-view").html(empty_list_widget_html);
        }

        $("#buddy-list-other-users").attr(
            "data-search-results-empty",
            other_users_empty_list_message,
        );
        if ($("#buddy-list-other-users .empty-list-message").length) {
            const empty_list_widget_html = render_empty_list_widget_for_list({
                other_users_empty_list_message,
            });
            $("#buddy-list-other-users").html(empty_list_widget_html);
        }
    }

    render_section_headers(): void {
        const {current_sub, subscriber_count, other_users_count, total_user_count, hide_headers} =
            this.render_data;
        $("#buddy-list-users-matching-view-container .buddy-list-subsection-header").empty();
        $("#buddy-list-other-users-container .buddy-list-subsection-header").empty();

        $("#buddy-list-users-matching-view-container").toggleClass("no-display", hide_headers);

        // Usually we show the user counts in the headers, but if we're hiding
        // those headers then we show the total user count in the main title.
        const default_userlist_title = $t({defaultMessage: "USERS"});
        if (hide_headers) {
            const formatted_count = get_formatted_sub_count(total_user_count);
            const userlist_title = `${default_userlist_title} (${formatted_count})`;
            $("#userlist-title").text(userlist_title);
            return;
        }
        $("#userlist-title").text(default_userlist_title);

        let header_text;
        if (current_sub) {
            header_text = $t({defaultMessage: "In this channel"});
        } else {
            header_text = $t({defaultMessage: "In this conversation"});
        }

        $("#buddy-list-users-matching-view-container .buddy-list-subsection-header").append(
            $(
                render_section_header({
                    id: "buddy-list-users-matching-view-section-heading",
                    header_text,
                    user_count: get_formatted_sub_count(subscriber_count),
                    toggle_class: "toggle-users-matching-view",
                    is_collapsed: this.users_matching_view_is_collapsed,
                }),
            ),
        );

        $("#buddy-list-other-users-container .buddy-list-subsection-header").append(
            $(
                render_section_header({
                    id: "buddy-list-other-users-section-heading",
                    header_text: $t({defaultMessage: "Others"}),
                    user_count: get_formatted_sub_count(other_users_count),
                    toggle_class: "toggle-other-users",
                    is_collapsed: this.other_users_is_collapsed,
                }),
            ),
        );
    }

    toggle_users_matching_view_section(): void {
        this.users_matching_view_is_collapsed = !this.users_matching_view_is_collapsed;
        $("#buddy-list-users-matching-view-container").toggleClass(
            "collapsed",
            this.users_matching_view_is_collapsed,
        );
        $("#buddy-list-users-matching-view-container .toggle-users-matching-view").toggleClass(
            "fa-caret-down",
            !this.users_matching_view_is_collapsed,
        );
        $("#buddy-list-users-matching-view-container .toggle-users-matching-view").toggleClass(
            "fa-caret-right",
            this.users_matching_view_is_collapsed,
        );

        // Collapsing and uncollapsing sections has a similar effect to
        // scrolling, so we make sure to fill screen with content here as well.
        this.fill_screen_with_content();
    }

    toggle_other_users_section(): void {
        this.other_users_is_collapsed = !this.other_users_is_collapsed;
        $("#buddy-list-other-users-container").toggleClass(
            "collapsed",
            this.other_users_is_collapsed,
        );
        $("#buddy-list-other-users-container .toggle-other-users").toggleClass(
            "fa-caret-down",
            !this.other_users_is_collapsed,
        );
        $("#buddy-list-other-users-container .toggle-other-users").toggleClass(
            "fa-caret-right",
            this.other_users_is_collapsed,
        );

        // Collapsing and uncollapsing sections has a similar effect to
        // scrolling, so we make sure to fill screen with content here as well.
        this.fill_screen_with_content();
    }

    render_more(opts: {chunk_size: number}): void {
        const chunk_size = opts.chunk_size;

        const begin = this.render_count;
        const end = begin + chunk_size;

        const more_user_ids = this.all_user_ids.slice(begin, end);

        if (more_user_ids.length === 0) {
            return;
        }

        const items = this.get_data_from_user_ids(more_user_ids);
        const subscribed_users = [];
        const other_users = [];
        const current_sub = this.render_data.current_sub;
        const pm_ids_set = narrow_state.pm_ids_set();

        for (const item of items) {
            if (buddy_data.user_matches_narrow(item.user_id, pm_ids_set, current_sub?.stream_id)) {
                subscribed_users.push(item);
                this.users_matching_view_ids.push(item.user_id);
            } else {
                other_users.push(item);
                this.other_user_ids.push(item.user_id);
            }
        }

        // Remove the empty list message before adding users
        if (
            $(`${this.matching_view_list_selector} .empty-list-message`).length > 0 &&
            subscribed_users.length
        ) {
            this.$users_matching_view_container.empty();
        }
        const subscribed_users_html = this.items_to_html({
            items: subscribed_users,
        });
        this.$users_matching_view_container = $(this.matching_view_list_selector);
        this.$users_matching_view_container.append($(subscribed_users_html));

        // Remove the empty list message before adding users
        if (
            $(`${this.other_user_list_selector} .empty-list-message`).length > 0 &&
            other_users.length
        ) {
            this.$other_users_container.empty();
        }
        const other_users_html = this.items_to_html({
            items: other_users,
        });
        this.$other_users_container = $(this.other_user_list_selector);
        this.$other_users_container.append($(other_users_html));

        // Invariant: more_user_ids.length >= items.length.
        // (Usually they're the same, but occasionally user ids
        // won't return valid items.  Even though we don't
        // actually render these user ids, we still "count" them
        // as rendered.

        this.render_count += more_user_ids.length;
        this.update_padding();
    }

    render_view_user_list_links(): void {
        const {current_sub, subscriber_count, other_users_count} = this.render_data;
        const has_inactive_users_matching_view =
            subscriber_count > this.users_matching_view_ids.length;
        const has_inactive_other_users = other_users_count > this.other_user_ids.length;

        // For stream views, we show a link at the bottom of the list of subscribed users that
        // lets a user find the full list of subscribed users and information about them.
        if (
            current_sub &&
            stream_data.can_view_subscribers(current_sub) &&
            has_inactive_users_matching_view
        ) {
            const stream_edit_hash = hash_util.channels_settings_edit_url(
                current_sub,
                "subscribers",
            );
            $("#buddy-list-users-matching-view-container").append(
                $(
                    render_view_all_subscribers({
                        stream_edit_hash,
                    }),
                ),
            );
        }

        // We give a link to view the list of all users to help reduce confusion about
        // there being hidden (inactive) "other" users.
        if (has_inactive_other_users) {
            $("#buddy-list-other-users-container").append($(render_view_all_users()));
        }
    }

    // From `type List<Key>`, where the key is a user_id.
    first_key(): number | undefined {
        if (this.users_matching_view_ids.length) {
            return this.users_matching_view_ids[0];
        }
        if (this.other_user_ids.length) {
            return this.other_user_ids[0];
        }
        return undefined;
    }

    // From `type List<Key>`, where the key is a user_id.
    prev_key(key: number): number | undefined {
        let i = this.users_matching_view_ids.indexOf(key);
        // This would be the middle of the list of users matching view,
        // moving to a prev user matching the view.
        if (i > 0) {
            return this.users_matching_view_ids[i - 1];
        }
        // If it's the first user matching the view, we don't move the selection.
        if (i === 0) {
            return undefined;
        }

        // This would be the middle of the other users list moving to a prev other user.
        i = this.other_user_ids.indexOf(key);
        if (i > 0) {
            return this.other_user_ids[i - 1];
        }
        // The key before the first other user is the last user matching view, if that exists,
        // and if it doesn't then we don't move the selection.
        if (i === 0) {
            if (this.users_matching_view_ids.length > 0) {
                return this.users_matching_view_ids.at(-1);
            }
            return undefined;
        }
        // The only way we reach here is if the key isn't found in either list,
        // which shouldn't happen.
        blueslip.error("Couldn't find key in buddy list", {
            key,
            users_matching_view_ids: this.users_matching_view_ids,
            other_user_ids: this.other_user_ids,
        });
        return undefined;
    }

    // From `type List<Key>`, where the key is a user_id.
    next_key(key: number): number | undefined {
        let i = this.users_matching_view_ids.indexOf(key);
        // Moving from users matching the view to the list of other users,
        // if they exist, otherwise do nothing.
        if (i >= 0 && i === this.users_matching_view_ids.length - 1) {
            if (this.other_user_ids.length > 0) {
                return this.other_user_ids[0];
            }
            return undefined;
        }
        // This is a regular move within the list of users matching the view.
        if (i >= 0) {
            return this.users_matching_view_ids[i + 1];
        }

        i = this.other_user_ids.indexOf(key);
        // If we're at the end of other users, we don't do anything.
        if (i >= 0 && i === this.other_user_ids.length - 1) {
            return undefined;
        }
        // This is a regular move within other users.
        if (i >= 0) {
            return this.other_user_ids[i + 1];
        }

        // The only way we reach here is if the key isn't found in either list,
        // which shouldn't happen.
        blueslip.error("Couldn't find key in buddy list", {
            key,
            users_matching_view_ids: this.users_matching_view_ids,
            other_user_ids: this.other_user_ids,
        });
        return undefined;
    }

    maybe_remove_user_id(opts: {user_id: number}): void {
        let pos = this.users_matching_view_ids.indexOf(opts.user_id);
        if (pos >= 0) {
            this.users_matching_view_ids.splice(pos, 1);
        } else {
            pos = this.other_user_ids.indexOf(opts.user_id);
            if (pos < 0) {
                return;
            }
            this.other_user_ids.splice(pos, 1);
        }
        pos = this.all_user_ids.indexOf(opts.user_id);
        this.all_user_ids.splice(pos, 1);

        if (pos < this.render_count) {
            this.render_count -= 1;
            const $li = this.find_li({key: opts.user_id});
            assert($li !== undefined);
            $li.remove();
            this.update_padding();
        }
    }

    find_position(opts: {user_id: number; user_id_list: number[]}): number {
        const user_id = opts.user_id;
        let i;

        const user_id_list = opts.user_id_list;

        const current_sub = narrow_state.stream_sub();
        const pm_ids_set = narrow_state.pm_ids_set();

        for (i = 0; i < user_id_list.length; i += 1) {
            const list_user_id = user_id_list[i];

            if (this.compare_function(user_id, list_user_id, current_sub, pm_ids_set) < 0) {
                return i;
            }
        }

        return user_id_list.length;
    }

    force_render(opts: {pos: number}): void {
        const pos = opts.pos;

        // Try to render a bit optimistically here.
        const cushion_size = 3;
        const chunk_size = pos + cushion_size - this.render_count;

        if (chunk_size <= 0) {
            blueslip.error("cannot show user id at this position", {
                pos,
                render_count: this.render_count,
                chunk_size,
            });
        }

        this.render_more({
            chunk_size,
        });
    }

    find_li(opts: {key: number; force_render?: boolean}): JQuery | undefined {
        const user_id = opts.key;

        // Try direct DOM lookup first for speed.
        let $li = this.get_li_from_user_id({
            user_id,
        });

        if ($li.length === 1) {
            return $li;
        }

        if (!opts.force_render) {
            // Most callers don't force us to render a list
            // item that wouldn't be on-screen anyway.
            return $li;
        }

        // We reference all_user_ids to see if we've rendered
        // it yet.
        const pos = this.all_user_ids.indexOf(user_id);

        if (pos < 0) {
            return undefined;
        }

        this.force_render({
            pos,
        });

        $li = this.get_li_from_user_id({
            user_id,
        });

        return $li;
    }

    insert_new_html(opts: {
        new_user_id: number | undefined;
        html: string;
        new_pos_in_all_users: number;
        is_subscribed_user: boolean;
    }): void {
        const user_id_following_insertion = opts.new_user_id;
        const html = opts.html;
        const new_pos_in_all_users = opts.new_pos_in_all_users;
        const is_subscribed_user = opts.is_subscribed_user;

        // This means we're inserting at the end
        if (user_id_following_insertion === undefined) {
            if (new_pos_in_all_users === this.render_count) {
                this.render_count += 1;
                if (is_subscribed_user) {
                    this.$users_matching_view_container.append($(html));
                } else {
                    this.$other_users_container.append($(html));
                }
                this.update_padding();
            }
            return;
        }

        if (new_pos_in_all_users < this.render_count) {
            this.render_count += 1;
            const $li = this.find_li({key: user_id_following_insertion});
            assert($li !== undefined);
            $li.before($(html));
            this.update_padding();
        }
    }

    insert_or_move(opts: {user_id: number; item: BuddyUserInfo}): void {
        const user_id = opts.user_id;
        const item = opts.item;

        this.maybe_remove_user_id({user_id});

        const new_pos_in_all_users = this.find_position({
            user_id,
            user_id_list: this.all_user_ids,
        });

        const current_sub = narrow_state.stream_sub();
        const pm_ids_set = narrow_state.pm_ids_set();
        const is_subscribed_user = buddy_data.user_matches_narrow(
            user_id,
            pm_ids_set,
            current_sub?.stream_id,
        );
        const user_id_list = is_subscribed_user
            ? this.users_matching_view_ids
            : this.other_user_ids;
        const new_pos_in_user_list = this.find_position({
            user_id,
            user_id_list,
        });

        // Order is important here--get the new_user_id
        // before mutating our list.  An undefined value
        // corresponds to appending.
        const new_user_id = user_id_list[new_pos_in_user_list];

        user_id_list.splice(new_pos_in_user_list, 0, user_id);
        this.all_user_ids.splice(new_pos_in_all_users, 0, user_id);

        const html = this.item_to_html({item});
        this.insert_new_html({
            new_pos_in_all_users,
            html,
            new_user_id,
            is_subscribed_user,
        });
    }

    fill_screen_with_content(): void {
        let height = this.height_to_fill();

        const elem = scroll_util
            .get_scroll_element($(this.scroll_container_selector))
            .expectOne()[0];

        // Add a fudge factor.
        height += 10;

        while (this.render_count < this.all_user_ids.length) {
            const padding_height = $(this.padding_selector).height();
            assert(padding_height !== undefined);
            const bottom_offset = elem.scrollHeight - elem.scrollTop - padding_height;

            if (bottom_offset > height) {
                break;
            }

            const chunk_size = 20;

            this.render_more({
                chunk_size,
            });
        }
        this.render_section_headers();
    }

    start_scroll_handler(): void {
        // We have our caller explicitly call this to make
        // sure everything's in place.
        const $scroll_container = scroll_util.get_scroll_element($(this.scroll_container_selector));

        $scroll_container.on("scroll", () => {
            this.fill_screen_with_content();
        });
    }

    update_padding(): void {
        padded_widget.update_padding({
            shown_rows: this.render_count,
            total_rows: this.all_user_ids.length,
            content_selector: "#buddy_list_wrapper",
            padding_selector: this.padding_selector,
        });
    }
}

export const buddy_list = new BuddyList();
