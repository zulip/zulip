import $ from "jquery";
import assert from "minimalistic-assert";
import * as tippy from "tippy.js";

import render_section_header from "../templates/buddy_list/section_header.hbs";
import render_view_all_subscribers from "../templates/buddy_list/view_all_subscribers.hbs";
import render_view_all_users from "../templates/buddy_list/view_all_users.hbs";
import render_empty_list_widget_for_list from "../templates/empty_list_widget_for_list.hbs";
import render_presence_row from "../templates/presence_row.hbs";
import render_presence_rows from "../templates/presence_rows.hbs";

import * as blueslip from "./blueslip.ts";
import * as buddy_data from "./buddy_data.ts";
import type {BuddyUserInfo} from "./buddy_data.ts";
import {media_breakpoints_num} from "./css_variables.ts";
import type {Filter} from "./filter.ts";
import * as hash_util from "./hash_util.ts";
import {$t} from "./i18n.ts";
import * as message_viewport from "./message_viewport.ts";
import * as narrow_state from "./narrow_state.ts";
import * as padded_widget from "./padded_widget.ts";
import * as peer_data from "./peer_data.ts";
import * as people from "./people.ts";
import * as scroll_util from "./scroll_util.ts";
import {current_user} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import type {StreamSubscription} from "./sub_store.ts";
import {INTERACTIVE_HOVER_DELAY} from "./tippyjs.ts";
import {user_settings} from "./user_settings.ts";
import * as util from "./util.ts";

function get_formatted_sub_count(sub_count: number): string {
    if (sub_count < 1000) {
        return sub_count.toString();
    }
    return new Intl.NumberFormat(user_settings.default_language, {notation: "compact"}).format(
        sub_count,
    );
}

function get_total_human_subscriber_count(
    current_sub: StreamSubscription | undefined,
    pm_ids_set: Set<number>,
): number {
    // Excludes human users, but may include long-inactive users who
    // might not show up in the buddy list.
    if (current_sub) {
        return peer_data.get_subscriber_count(current_sub.stream_id, false);
    } else if (pm_ids_set.size > 0) {
        // The current user is only in the provided recipients list
        // for direct message conversations with oneself.
        const all_recipient_user_ids_set = pm_ids_set.union(new Set([current_user.user_id]));

        let human_user_count = 0;
        for (const pm_id of all_recipient_user_ids_set) {
            if (!people.is_valid_bot_user(pm_id) && people.is_person_active(pm_id)) {
                human_user_count += 1;
            }
        }
        return human_user_count;
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
    return !current_sub && pm_ids_set.size === 0;
}

type BuddyListRenderData = {
    current_sub: StreamSubscription | undefined;
    pm_ids_set: Set<number>;
    total_human_subscribers_count: number;
    other_users_count: number;
    hide_headers: boolean;
    get_all_participant_ids: () => Set<number>;
};

function get_render_data(): BuddyListRenderData {
    const current_sub = narrow_state.stream_sub();
    const pm_ids_set = narrow_state.pm_ids_set();

    const total_human_subscribers_count = get_total_human_subscriber_count(current_sub, pm_ids_set);
    const other_users_count = people.get_active_human_count() - total_human_subscribers_count;
    const hide_headers = should_hide_headers(current_sub, pm_ids_set);
    const get_all_participant_ids = buddy_data.get_conversation_participants_callback();

    return {
        current_sub,
        pm_ids_set,
        total_human_subscribers_count,
        other_users_count,
        hide_headers,
        get_all_participant_ids,
    };
}

class BuddyListConf {
    participants_list_selector = "#buddy-list-participants";
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
    participant_user_ids: number[] = [];
    users_matching_view_ids: number[] = [];
    other_user_ids: number[] = [];
    participants_is_collapsed = false;
    users_matching_view_is_collapsed = false;
    other_users_is_collapsed = true;
    render_count = 0;
    render_data = get_render_data();
    // This is a bit of a hack to make sure we at least have
    // an empty list to start, before we get the initial payload.
    $participants_list = $(this.participants_list_selector);
    $users_matching_view_list = $(this.matching_view_list_selector);
    $other_users_list = $(this.other_user_list_selector);
    current_filter: Filter | undefined | "unset" = "unset";

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
                tippy.default(util.the($elem), {
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
                        const total_human_subscribers_count = get_total_human_subscriber_count(
                            current_sub,
                            pm_ids_set,
                        );
                        const participant_count = Number.parseInt(
                            $("#buddy-list-participants-section-heading").attr("data-user-count")!,
                            10,
                        );
                        const elem_id = $elem.attr("id");
                        if (elem_id === "buddy-list-participants-section-heading") {
                            tooltip_text = $t(
                                {
                                    defaultMessage:
                                        "{N, plural, one {# participant} other {# participants}}",
                                },
                                {N: participant_count},
                            );
                        } else if (elem_id === "buddy-list-users-matching-view-section-heading") {
                            if (participant_count) {
                                tooltip_text = $t(
                                    {
                                        defaultMessage:
                                            "{N, plural, one {# other subscriber} other {# other subscribers}}",
                                    },
                                    {N: total_human_subscribers_count - participant_count},
                                );
                            } else if (current_sub) {
                                tooltip_text = $t(
                                    {
                                        defaultMessage:
                                            "{N, plural, one {# subscriber} other {# subscribers}}",
                                    },
                                    {N: total_human_subscribers_count},
                                );
                            } else {
                                tooltip_text = $t(
                                    {
                                        defaultMessage:
                                            "{N, plural, one {# participant} other {# participants}}",
                                    },
                                    {N: total_human_subscribers_count},
                                );
                            }
                        } else {
                            const other_users_count =
                                people.get_active_human_count() - total_human_subscribers_count;
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
        this.$participants_list.empty();
        this.participant_user_ids = [];
        this.$users_matching_view_list.empty();
        this.users_matching_view_ids = [];
        this.$other_users_list.empty();
        this.other_user_ids = [];

        // Reset data to be relevant for this current view.
        this.render_data = get_render_data();

        // We rely on our caller to give us items
        // in already-sorted order.
        this.all_user_ids = opts.all_user_ids;

        if (buddy_data.get_is_searching_users()) {
            // Show all sections when searching users
            this.set_section_collapse(".buddy-list-section-container", false);
        } else {
            this.set_section_collapse(
                "#buddy-list-participants-container",
                this.participants_is_collapsed,
            );
            this.set_section_collapse(
                "#buddy-list-users-matching-view-container",
                this.users_matching_view_is_collapsed,
            );
            this.set_section_collapse(
                "#buddy-list-other-users-container",
                this.other_users_is_collapsed,
            );
        }

        // Ensure the "other" section is visible when headers are collapsed,
        // because we're hiding its header so there's no way to collapse or
        // uncollapse the list in this view. Ensure we're showing/hiding as
        // the user specified otherwise.
        this.set_section_collapse(
            "#buddy-list-other-users-container",
            this.render_data.hide_headers ? false : this.other_users_is_collapsed,
        );

        this.update_empty_list_placeholders();
        this.fill_screen_with_content();

        // This must happen after `fill_screen_with_content`
        $("#buddy-list-users-matching-view-container .view-all-subscribers-link").remove();
        $("#buddy-list-other-users-container .view-all-users-link").remove();
        if (!buddy_data.get_is_searching_users()) {
            this.render_view_user_list_links();
        }
        this.display_or_hide_sections();

        // `populate` always rerenders all user rows, so we need new load handlers.
        // This logic only does something is a user has enabled the setting to
        // view avatars in the buddy list, and otherwise the jQuery selector will
        // always be the empty set.
        $("#user-list .user-profile-picture img")
            .off("load")
            .on("load", function (this: HTMLElement) {
                $(this)
                    .closest(".user-profile-picture")
                    .toggleClass("avatar-preload-background", false);
            });
    }

    update_empty_list_placeholders(): void {
        const {total_human_subscribers_count, other_users_count} = this.render_data;
        const has_inactive_users_matching_view =
            total_human_subscribers_count >
            this.users_matching_view_ids.length + this.participant_user_ids.length;
        const has_inactive_other_users = other_users_count > this.other_user_ids.length;

        let matching_view_empty_list_message;
        let other_users_empty_list_message;
        // Only visible when searching, since we usually hide an empty participants section
        let participants_empty_list_message;

        if (buddy_data.get_is_searching_users()) {
            matching_view_empty_list_message = $t({defaultMessage: "No matching users."});
            other_users_empty_list_message = $t({defaultMessage: "No matching users."});
            participants_empty_list_message = $t({defaultMessage: "No matching users."});
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

        function add_or_update_empty_list_placeholder(selector: string, message: string): void {
            if (
                $(selector).children().length === 0 ||
                $(`${selector} .empty-list-message`).length > 0
            ) {
                const empty_list_widget_html = render_empty_list_widget_for_list({
                    empty_list_message: message,
                });
                $(selector).html(empty_list_widget_html);
            }
        }

        add_or_update_empty_list_placeholder(
            "#buddy-list-users-matching-view",
            matching_view_empty_list_message,
        );

        add_or_update_empty_list_placeholder(
            "#buddy-list-other-users",
            other_users_empty_list_message,
        );

        if (participants_empty_list_message) {
            add_or_update_empty_list_placeholder(
                "#buddy-list-participants",
                participants_empty_list_message,
            );
        }
    }

    update_section_header_counts(): void {
        const {total_human_subscribers_count, other_users_count} = this.render_data;
        const all_participant_ids = this.render_data.get_all_participant_ids();
        const subscriber_section_user_count =
            total_human_subscribers_count - all_participant_ids.size;

        const formatted_participants_count = get_formatted_sub_count(all_participant_ids.size);
        const formatted_sub_users_count = get_formatted_sub_count(subscriber_section_user_count);
        const formatted_other_users_count = get_formatted_sub_count(other_users_count);

        $("#buddy-list-participants-container .buddy-list-heading-user-count").text(
            formatted_participants_count,
        );
        $("#buddy-list-users-matching-view-container .buddy-list-heading-user-count").text(
            formatted_sub_users_count,
        );
        $("#buddy-list-other-users-container .buddy-list-heading-user-count").text(
            formatted_other_users_count,
        );

        $("#buddy-list-participants-section-heading").attr(
            "data-user-count",
            all_participant_ids.size,
        );
        $("#buddy-list-users-matching-view-section-heading").attr(
            "data-user-count",
            subscriber_section_user_count,
        );
        $("#buddy-list-users-other-users-section-heading").attr(
            "data-user-count",
            other_users_count,
        );
    }

    render_section_headers(): void {
        const {hide_headers} = this.render_data;
        const all_participant_ids = this.render_data.get_all_participant_ids();

        // If we're not changing filters, this just means some users were added or
        // removed but otherwise everything is the same, so we don't need to do a full
        // rerender.
        if (this.current_filter === narrow_state.filter()) {
            this.update_section_header_counts();
            return;
        }
        this.current_filter = narrow_state.filter();

        const {current_sub, total_human_subscribers_count, other_users_count} = this.render_data;
        $(".buddy-list-subsection-header").empty();
        $(".buddy-list-subsection-header").toggleClass("no-display", hide_headers);
        if (hide_headers) {
            return;
        }

        $("#buddy-list-participants-container .buddy-list-subsection-header").append(
            $(
                render_section_header({
                    id: "buddy-list-participants-section-heading",
                    header_text: $t({defaultMessage: "THIS CONVERSATION"}),
                    user_count: get_formatted_sub_count(all_participant_ids.size),
                    is_collapsed: this.participants_is_collapsed,
                }),
            ),
        );

        $("#buddy-list-users-matching-view-container .buddy-list-subsection-header").append(
            $(
                render_section_header({
                    id: "buddy-list-users-matching-view-section-heading",
                    header_text: current_sub
                        ? $t({defaultMessage: "THIS CHANNEL"})
                        : $t({defaultMessage: "THIS CONVERSATION"}),
                    user_count: get_formatted_sub_count(
                        total_human_subscribers_count - all_participant_ids.size,
                    ),
                    is_collapsed: this.users_matching_view_is_collapsed,
                }),
            ),
        );

        $("#buddy-list-other-users-container .buddy-list-subsection-header").append(
            $(
                render_section_header({
                    id: "buddy-list-other-users-section-heading",
                    header_text: $t({defaultMessage: "OTHERS"}),
                    user_count: get_formatted_sub_count(other_users_count),
                    is_collapsed: this.other_users_is_collapsed,
                }),
            ),
        );
    }

    set_section_collapse(container_selector: string, is_collapsed: boolean): void {
        $(container_selector).toggleClass("collapsed", is_collapsed);
        $(`${container_selector} .buddy-list-section-toggle`).toggleClass(
            "rotate-icon-down",
            !is_collapsed,
        );
        $(`${container_selector} .buddy-list-section-toggle`).toggleClass(
            "rotate-icon-right",
            is_collapsed,
        );
    }

    toggle_participants_section(): void {
        this.participants_is_collapsed = !this.participants_is_collapsed;
        this.set_section_collapse(
            "#buddy-list-participants-container",
            this.participants_is_collapsed,
        );

        // Collapsing and uncollapsing sections has a similar effect to
        // scrolling, so we make sure to fill screen with content here as well.
        this.fill_screen_with_content();
    }

    toggle_users_matching_view_section(): void {
        this.users_matching_view_is_collapsed = !this.users_matching_view_is_collapsed;
        this.set_section_collapse(
            "#buddy-list-users-matching-view-container",
            this.users_matching_view_is_collapsed,
        );

        // Collapsing and uncollapsing sections has a similar effect to
        // scrolling, so we make sure to fill screen with content here as well.
        this.fill_screen_with_content();
    }

    toggle_other_users_section(): void {
        this.other_users_is_collapsed = !this.other_users_is_collapsed;
        this.set_section_collapse(
            "#buddy-list-other-users-container",
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
        const participants = [];
        const subscribed_users = [];
        const other_users = [];
        const current_sub = this.render_data.current_sub;
        const pm_ids_set = narrow_state.pm_ids_set();
        const all_participant_ids = this.render_data.get_all_participant_ids();

        for (const item of items) {
            if (all_participant_ids.has(item.user_id)) {
                participants.push(item);
                this.participant_user_ids.push(item.user_id);
            } else if (
                buddy_data.user_matches_narrow(item.user_id, pm_ids_set, current_sub?.stream_id)
            ) {
                subscribed_users.push(item);
                this.users_matching_view_ids.push(item.user_id);
            } else {
                other_users.push(item);
                this.other_user_ids.push(item.user_id);
            }
        }

        this.$participants_list = $(this.participants_list_selector);
        if (participants.length > 0) {
            // Remove the empty list message before adding users
            if ($(`${this.participants_list_selector} .empty-list-message`).length > 0) {
                this.$participants_list.empty();
            }
            const participants_html = this.items_to_html({
                items: participants,
            });
            this.$participants_list.append($(participants_html));
        }

        this.$users_matching_view_list = $(this.matching_view_list_selector);
        if (subscribed_users.length > 0) {
            // Remove the empty list message before adding users
            if ($(`${this.matching_view_list_selector} .empty-list-message`).length > 0) {
                this.$users_matching_view_list.empty();
            }
            const subscribed_users_html = this.items_to_html({
                items: subscribed_users,
            });
            this.$users_matching_view_list.append($(subscribed_users_html));
        }

        this.$other_users_list = $(this.other_user_list_selector);
        if (other_users.length > 0) {
            // Remove the empty list message before adding users
            if ($(`${this.other_user_list_selector} .empty-list-message`).length > 0) {
                this.$other_users_list.empty();
            }
            const other_users_html = this.items_to_html({
                items: other_users,
            });
            this.$other_users_list.append($(other_users_html));
        }

        // Invariant: more_user_ids.length >= items.length.
        // (Usually they're the same, but occasionally user ids
        // won't return valid items.  Even though we don't
        // actually render these user ids, we still "count" them
        // as rendered.

        this.render_count += more_user_ids.length;
        this.update_padding();
    }

    display_or_hide_sections(): void {
        const {get_all_participant_ids, hide_headers, total_human_subscribers_count} =
            this.render_data;

        // If we're in the mode of hiding headers, that means we're only showing the "others"
        // section, so hide the other two sections.
        $("#buddy-list-users-matching-view-container").toggleClass("no-display", hide_headers);
        const hide_participants_list = hide_headers || get_all_participant_ids().size === 0;
        $("#buddy-list-participants-container").toggleClass("no-display", hide_participants_list);

        // This is the case where every subscriber is in the participants list. In this case, we
        // hide the "in this channel" section.
        if (
            !hide_participants_list &&
            total_human_subscribers_count === this.participant_user_ids.length
        ) {
            $("#buddy-list-users-matching-view-container").toggleClass("no-display", true);
        }
    }

    render_view_user_list_links(): void {
        const {current_sub, total_human_subscribers_count, other_users_count} = this.render_data;
        const has_inactive_users_matching_view =
            total_human_subscribers_count >
            this.users_matching_view_ids.length + this.participant_user_ids.length;
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

        // Note that we don't show a link for the participants list because we expect
        // all participants to be shown (except bots or deactivated users).
    }

    // From `type List<Key>`, where the key is a user_id.
    first_key(): number | undefined {
        if (this.participant_user_ids.length > 0) {
            return this.participant_user_ids[0];
        }
        if (this.users_matching_view_ids.length > 0) {
            return this.users_matching_view_ids[0];
        }
        if (this.other_user_ids.length > 0) {
            return this.other_user_ids[0];
        }
        return undefined;
    }

    // From `type List<Key>`, where the key is a user_id.
    prev_key(key: number): number | undefined {
        let i = this.participant_user_ids.indexOf(key);
        // This would be the middle of the list of participants,
        // moving to a prev participant.
        if (i > 0) {
            return this.participant_user_ids[i - 1];
        }
        // If it's the first participant, we don't move the selection.
        if (i === 0) {
            return undefined;
        }

        i = this.users_matching_view_ids.indexOf(key);
        // This would be the middle of the list of users matching view,
        // moving to a prev user matching the view.
        if (i > 0) {
            return this.users_matching_view_ids[i - 1];
        }
        // The key before the first user matching view is the last participant, if that exists,
        // and if it doesn't then we don't move the selection.
        if (i === 0) {
            if (this.participant_user_ids.length > 0) {
                return this.participant_user_ids.at(-1);
            }
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
            // If there are no matching users but there are participants, go there
            if (this.participant_user_ids.length > 0) {
                return this.participant_user_ids.at(-1);
            }
            return undefined;
        }
        // The only way we reach here is if the key isn't found in either list,
        // which shouldn't happen.
        blueslip.error("Couldn't find key in buddy list", {
            key,
            participant_user_ids: this.participant_user_ids,
            users_matching_view_ids: this.users_matching_view_ids,
            other_user_ids: this.other_user_ids,
        });
        return undefined;
    }

    // From `type List<Key>`, where the key is a user_id.
    next_key(key: number): number | undefined {
        let i = this.participant_user_ids.indexOf(key);
        // Moving from participants to the list of users matching view,
        // if they exist, otherwise do nothing.
        if (i >= 0 && i === this.participant_user_ids.length - 1) {
            if (this.users_matching_view_ids.length > 0) {
                return this.users_matching_view_ids[0];
            }
            // If there are no matching users but there are other users, go there
            if (this.other_user_ids.length > 0) {
                return this.other_user_ids[0];
            }
            return undefined;
        }
        // This is a regular move within the list of users matching the view.
        if (i >= 0) {
            return this.participant_user_ids[i + 1];
        }

        i = this.users_matching_view_ids.indexOf(key);
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
            participant_user_ids: this.participant_user_ids,
            users_matching_view_ids: this.users_matching_view_ids,
            other_user_ids: this.other_user_ids,
        });
        return undefined;
    }

    maybe_remove_user_id(opts: {user_id: number}): void {
        let was_removed = false;
        for (const user_id_list of [
            this.participant_user_ids,
            this.users_matching_view_ids,
            this.other_user_ids,
        ]) {
            const pos = user_id_list.indexOf(opts.user_id);
            if (pos !== -1) {
                user_id_list.splice(pos, 1);
                was_removed = true;
                break;
            }
        }
        if (!was_removed) {
            return;
        }
        const pos = this.all_user_ids.indexOf(opts.user_id);
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
        const user_id_list = opts.user_id_list;

        const current_sub = narrow_state.stream_sub();
        const pm_ids_set = narrow_state.pm_ids_set();

        const i = user_id_list.findIndex(
            (list_user_id) =>
                this.compare_function(
                    user_id,
                    list_user_id,
                    current_sub,
                    pm_ids_set,
                    this.render_data.get_all_participant_ids(),
                ) < 0,
        );
        return i === -1 ? user_id_list.length : i;
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

        if (pos === -1) {
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
        is_subscribed_user: boolean;
        is_participant_user: boolean;
    }): void {
        const user_id_following_insertion = opts.new_user_id;
        const html = opts.html;
        const is_subscribed_user = opts.is_subscribed_user;
        const is_participant_user = opts.is_participant_user;

        // This means we're inserting at the end
        if (user_id_following_insertion === undefined) {
            if (is_participant_user) {
                this.$participants_list.append($(html));
            } else if (is_subscribed_user) {
                this.$users_matching_view_list.append($(html));
            } else {
                this.$other_users_list.append($(html));
            }
        } else {
            const $li = this.find_li({key: user_id_following_insertion});
            assert($li !== undefined);
            $li.before($(html));
        }

        this.render_count += 1;
        this.update_padding();
    }

    insert_or_move(user_ids: number[]): void {
        // TODO: Further optimize this function by clubbing DOM updates from
        // multiple insertions/movements into a single update.

        const all_participant_ids = this.render_data.get_all_participant_ids();
        const users = buddy_data.get_items_for_users(user_ids);
        for (const user of users) {
            const user_id = user.user_id;

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
            let user_id_list;
            if (all_participant_ids.has(user_id)) {
                user_id_list = this.participant_user_ids;
            } else if (is_subscribed_user) {
                user_id_list = this.users_matching_view_ids;
            } else {
                user_id_list = this.other_user_ids;
            }
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

            const html = this.item_to_html({item: user});
            this.insert_new_html({
                html,
                new_user_id,
                is_subscribed_user,
                is_participant_user: all_participant_ids.has(user_id),
            });
        }

        this.display_or_hide_sections();
        this.render_section_headers();
    }

    rerender_participants(): void {
        const all_participant_ids = this.render_data.get_all_participant_ids();
        const users_to_remove = this.participant_user_ids.filter(
            (user_id) => !all_participant_ids.has(user_id),
        );
        const users_to_add = [...all_participant_ids].filter(
            (user_id) => !this.participant_user_ids.includes(user_id),
        );

        // We are just moving the users around since we still want to show the
        // user in buddy list regardless of if they are a participant, so we
        // call `insert_or_move` on both `users_to_remove` and `users_to_add`.
        this.insert_or_move([...users_to_remove, ...users_to_add]);
    }

    fill_screen_with_content(): void {
        let height = this.height_to_fill();

        const elem = util.the(scroll_util.get_scroll_element($(this.scroll_container_selector)));

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
