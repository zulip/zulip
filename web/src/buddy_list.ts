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
import type {Filter} from "./filter.ts";
import * as hash_util from "./hash_util.ts";
import {$t} from "./i18n.ts";
import * as message_viewport from "./message_viewport.ts";
import * as narrow_state from "./narrow_state.ts";
import * as padded_widget from "./padded_widget.ts";
import {page_params} from "./page_params.ts";
import * as peer_data from "./peer_data.ts";
import * as people from "./people.ts";
import * as scroll_util from "./scroll_util.ts";
import * as settings_config from "./settings_config.ts";
import {current_user} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import type {StreamSubscription} from "./sub_store.ts";
import {INTERACTIVE_HOVER_DELAY} from "./tippyjs.ts";
import * as ui_util from "./ui_util.ts";
import {user_settings} from "./user_settings.ts";
import * as util from "./util.ts";

function get_formatted_user_count(sub_count: number): string {
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
    if (current_sub) {
        return peer_data.get_subscriber_count(current_sub.stream_id, false);
    } else if (pm_ids_set.size > 0) {
        // The current user is only in the provided recipients list
        // for direct message conversations with oneself.
        const all_recipient_user_ids_set = pm_ids_set.union(new Set([current_user.user_id]));

        let human_user_count = 0;
        for (const pm_id of all_recipient_user_ids_set) {
            if (!people.is_valid_bot_user(pm_id)) {
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
    // Note: Until #34246 is complete, this might be incorrect when
    // we are dealing with a partial subscriber matrix, leading to
    // some counting bugs in the headers. This shouldn't show up in
    // production.
    total_human_subscribers_count: number;
    other_users_count: number;
    hide_headers: boolean;
    // Might include unsubscribed participants
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
        const non_participant_users_matching_view_count = async (): Promise<number | null> =>
            await this.non_participant_users_matching_view_count();
        const total_human_subscribers_count = (): number =>
            this.render_data.total_human_subscribers_count;

        $("#right-sidebar").on(
            "mouseenter",
            ".buddy-list-heading",
            function (this: HTMLElement, e) {
                e.stopPropagation();
                const $elem = $(this);
                let placement: "left" | "auto" = "left";
                if (ui_util.matches_viewport_state("lt_md_min")) {
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
                        const participant_count = Number.parseInt(
                            $("#buddy-list-participants-section-heading").attr("data-user-count")!,
                            10,
                        );
                        const elem_id = $elem.attr("id");
                        if (elem_id === "buddy-list-participants-section-heading") {
                            const tooltip_text = $t(
                                {
                                    defaultMessage:
                                        "{N, plural, one {# participant} other {# participants}}",
                                },
                                {N: participant_count},
                            );
                            instance.setContent(tooltip_text);
                        } else if (elem_id === "buddy-list-users-matching-view-section-heading") {
                            void (async () => {
                                let tooltip_text;
                                const stream_sub = narrow_state.stream_sub();
                                if (stream_sub) {
                                    // If we need to fetch the full data, show the total subscriber
                                    // count in the meantime.
                                    if (!peer_data.has_full_subscriber_data(stream_sub.stream_id)) {
                                        instance.setContent(
                                            $t(
                                                {
                                                    defaultMessage:
                                                        "{N, plural, one {# total subscriber} other {# total subscribers}}",
                                                },
                                                {N: total_human_subscribers_count()},
                                            ),
                                        );
                                    }
                                    const users_matching_view_count =
                                        await non_participant_users_matching_view_count();
                                    // This means a request failed and we don't know the count. So we can
                                    // leave the text as the total subscriber count.
                                    if (users_matching_view_count === null) {
                                        return;
                                    }
                                    tooltip_text = $t(
                                        {
                                            defaultMessage:
                                                "{N, plural, one {# other subscriber} other {# other subscribers}}",
                                        },
                                        {N: users_matching_view_count},
                                    );
                                } else {
                                    // This will happen immediately because we don't need
                                    // to fetch subscriber data.
                                    const users_matching_view_count =
                                        await non_participant_users_matching_view_count();
                                    assert(users_matching_view_count !== null);
                                    tooltip_text = $t(
                                        {
                                            defaultMessage:
                                                "{N, plural, one {# participant} other {# participants}}",
                                        },
                                        {N: users_matching_view_count},
                                    );
                                }
                                instance.setContent(tooltip_text);
                            })();
                        } else {
                            const other_users_count =
                                people.get_active_human_count() - total_human_subscribers_count();
                            const tooltip_text = $t(
                                {
                                    defaultMessage:
                                        "{N, plural, one {# other user} other {# other users}}",
                                },
                                {N: other_users_count},
                            );
                            instance.setContent(tooltip_text);
                        }
                    },
                    onHidden(instance) {
                        instance.destroy();
                    },
                    appendTo: () => document.body,
                });
            },
        );
    }

    async non_participant_users_matching_view_count(): Promise<number | null> {
        const {current_sub, get_all_participant_ids} = this.render_data;
        // We don't show "participants" for DMs, we just show the
        // "in this narrow" section (i.e. everyone in the conversation).
        // Confusingly, we do call this "participants" in the UI.
        if (current_sub === undefined) {
            return this.render_data.total_human_subscribers_count;
        }
        const participant_ids_list = [...get_all_participant_ids()];
        const subscribed_human_participant_ids = [];
        for (const user_id of participant_ids_list) {
            const is_subscribed = await peer_data.maybe_fetch_is_user_subscribed(
                current_sub.stream_id,
                user_id,
                false,
            );
            // This means a request failed and we don't know the count.
            if (is_subscribed === null) {
                return null;
            }
            if (is_subscribed && !people.is_valid_bot_user(user_id)) {
                subscribed_human_participant_ids.push(user_id);
            }
        }
        return (
            this.render_data.total_human_subscribers_count - subscribed_human_participant_ids.length
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
        $("#user-list").toggleClass(
            "with_avatars",
            user_settings.user_list_style ===
                settings_config.user_list_style_values.with_avatar.code,
        );

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
            // Ensure the "other" section is visible when headers are collapsed,
            // because we're hiding its header so there's no way to collapse or
            // uncollapse the list in this view. Ensure we're showing/hiding as
            // the user specified otherwise.
            this.set_section_collapse(
                "#buddy-list-other-users-container",
                this.render_data.hide_headers ? false : this.other_users_is_collapsed,
            );
        }

        this.fill_screen_with_content();

        // This must happen after `fill_screen_with_content`
        $("#buddy-list-users-matching-view-container .view-all-subscribers-link").empty();
        $("#buddy-list-other-users-container .view-all-users-link").empty();
        void this.render_view_user_list_links();
        this.display_or_hide_sections();
        void this.update_empty_list_placeholders();

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

    // We show "No matching users" if a section is empty during search.
    // Otherwise we hide sections with no users in them, except the "this
    // channel" section, since it could confuse users to show other sections
    // without that one.
    async update_empty_list_placeholders(): Promise<void> {
        function add_or_update_empty_list_placeholder(
            list_selector: string,
            message: string,
        ): void {
            // It's already set, so don't do extra work
            if ($(`${list_selector} .empty-list-message`).text() === message) {
                return;
            }
            // Remove any existing message first, since it's actually one of the
            // children of `$(list_selector)`
            $(`${list_selector} .empty-list-message`).remove();
            if ($(list_selector).children().length === 0) {
                const empty_list_widget_html = render_empty_list_widget_for_list({
                    empty_list_message: message,
                });
                $(list_selector).html(empty_list_widget_html);
            }
        }

        if (buddy_data.get_is_searching_users()) {
            const message = $t({defaultMessage: "No matching users."});
            add_or_update_empty_list_placeholder("#buddy-list-users-matching-view", message);
            add_or_update_empty_list_placeholder("#buddy-list-other-users", message);
            add_or_update_empty_list_placeholder("#buddy-list-participants", message);
            return;
        }

        const {current_sub, get_all_participant_ids} = this.render_data;
        $("#buddy-list-users-matching-view .empty-list-message").remove();
        const non_participant_users_matching_view_count =
            await this.non_participant_users_matching_view_count();
        if (
            non_participant_users_matching_view_count === null ||
            non_participant_users_matching_view_count > 0
        ) {
            // There are more subscribers (or we don't know how many subscribers there are)
            // so we don't need an empty list message.
            return;
        }
        // After the `await`, we might have changed to a different channel view.
        // If so, we shouldn't update the DOM anymore, and should let the newer `populate`
        // call set things up with fresh data.
        if (current_sub !== this.render_data.current_sub) {
            return;
        }
        if (get_all_participant_ids().size > 0) {
            add_or_update_empty_list_placeholder(
                "#buddy-list-users-matching-view",
                $t({defaultMessage: "No other subscribers."}),
            );
        } else {
            // There's no "this conversation" section, so it would be confusing
            // to say there are "other" subscribers.
            add_or_update_empty_list_placeholder(
                "#buddy-list-users-matching-view",
                $t({defaultMessage: "No subscribers."}),
            );
        }
    }

    async update_section_header_counts(): Promise<void> {
        const {other_users_count, current_sub} = this.render_data;
        const all_participant_ids = this.render_data.get_all_participant_ids();

        // Hide the counts until we have the data
        if (current_sub && !peer_data.has_full_subscriber_data(current_sub.stream_id)) {
            $(".buddy-list-heading-user-count-with-parens").addClass("hide");
        }

        const formatted_participants_count = get_formatted_user_count(all_participant_ids.size);
        const non_participant_users_matching_view_count =
            await this.non_participant_users_matching_view_count();
        // This means a request failed and we can't calculate the counts.
        if (non_participant_users_matching_view_count === null) {
            return;
        }
        const formatted_matching_users_count = get_formatted_user_count(
            non_participant_users_matching_view_count,
        );
        const formatted_other_users_count = get_formatted_user_count(other_users_count);

        // After the `await`, we might have changed to a different channel view.
        // If so, we shouldn't update the DOM anymore, and should let the newer `populate`
        // call set things up with fresh data.
        if (current_sub !== this.render_data.current_sub) {
            return;
        }

        $("#buddy-list-participants-container .buddy-list-heading-user-count").text(
            formatted_participants_count,
        );
        $("#buddy-list-users-matching-view-container .buddy-list-heading-user-count").text(
            formatted_matching_users_count,
        );
        $("#buddy-list-other-users-container .buddy-list-heading-user-count").text(
            formatted_other_users_count,
        );
        $(".buddy-list-heading-user-count-with-parens").removeClass("hide");

        $("#buddy-list-participants-section-heading").attr(
            "data-user-count",
            all_participant_ids.size,
        );
        $("#buddy-list-users-matching-view-section-heading").attr(
            "data-user-count",
            non_participant_users_matching_view_count,
        );
        $("#buddy-list-users-other-users-section-heading").attr(
            "data-user-count",
            other_users_count,
        );
    }

    async render_section_headers(): Promise<void> {
        const {hide_headers} = this.render_data;

        // If we're not changing filters, this just means some users were added or
        // removed but otherwise everything is the same, so we don't need to do a full
        // rerender.
        if (this.current_filter === narrow_state.filter()) {
            await this.update_section_header_counts();
            return;
        }
        this.current_filter = narrow_state.filter();

        const {current_sub} = this.render_data;
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
                    is_collapsed: this.users_matching_view_is_collapsed,
                }),
            ),
        );

        $("#buddy-list-other-users-container .buddy-list-subsection-header").append(
            $(
                render_section_header({
                    id: "buddy-list-other-users-section-heading",
                    header_text: $t({defaultMessage: "OTHERS"}),
                    is_collapsed: this.other_users_is_collapsed,
                }),
            ),
        );
        await this.update_section_header_counts();
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
        // `hide_headers === true` means that we're only showing one section, like
        // for Inbox view. We hide all headers and show only users from the "others"
        // section and should hide the other two sections.
        const {hide_headers, other_users_count, get_all_participant_ids} = this.render_data;

        const hide_participants = hide_headers || get_all_participant_ids().size === 0;
        // We always show the users matching view section, even if there's nobody in it,
        // since it can be confusing to see "others" out of context of the main population
        // of that narrow.
        const hide_users_matching_view = hide_headers;
        const hide_other_users = other_users_count === 0;

        $("#buddy-list-users-matching-view-container").toggleClass(
            "no-display",
            hide_users_matching_view,
        );
        $("#buddy-list-participants-container").toggleClass("no-display", hide_participants);
        $("#buddy-list-other-users-container").toggleClass("no-display", hide_other_users);
    }

    async render_view_user_list_links(): Promise<void> {
        // We don't show the "view user" links when searching, because
        // these links are meant to reduce confusion about the list
        // being incomplete, and it's obvious why it's incomplete during
        // search.
        if (buddy_data.get_is_searching_users()) {
            return;
        }

        const {current_sub, other_users_count} = this.render_data;
        const non_participant_users_matching_view_count =
            await this.non_participant_users_matching_view_count();
        // This means a request failed and we can't calculate the counts. We choose
        // not to render the links in that case.
        if (non_participant_users_matching_view_count === null) {
            return;
        }
        const has_inactive_users_matching_view =
            non_participant_users_matching_view_count > this.users_matching_view_ids.length;
        const has_inactive_other_users = other_users_count > this.other_user_ids.length;

        // After the `await`, we might have changed to a different channel view.
        // If so, we shouldn't update the DOM anymore, and should let the newer `populate`
        // call set things up with fresh data. We also want to ensure we're still not showing
        // the links when searching users, which might have changed since fetching data.
        if (current_sub !== this.render_data.current_sub || buddy_data.get_is_searching_users()) {
            return;
        }

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
            $("#buddy-list-users-matching-view-container .view-all-subscribers-link").html(
                render_view_all_subscribers({
                    stream_edit_hash,
                }),
            );
        }

        // We give a link to view the list of all users to help reduce confusion about
        // there being hidden (inactive) "other" users.
        if (has_inactive_other_users) {
            $("#buddy-list-other-users-container .view-all-users-link").html(
                render_view_all_users(),
            );
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

        const stream_id = narrow_state.stream_id(narrow_state.filter(), true);
        const pm_ids_set = narrow_state.pm_ids_set();

        const i = user_id_list.findIndex(
            (list_user_id) =>
                this.compare_function(
                    user_id,
                    list_user_id,
                    stream_id,
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

            const stream_id = narrow_state.stream_id(narrow_state.filter(), true);
            const pm_ids_set = narrow_state.pm_ids_set();
            const is_subscribed_user = buddy_data.user_matches_narrow(
                user_id,
                pm_ids_set,
                stream_id,
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
        void this.update_empty_list_placeholders();
        void this.render_section_headers();
    }

    rerender_participants(): void {
        if (page_params.is_spectator) {
            return;
        }

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
        void this.render_section_headers();
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
