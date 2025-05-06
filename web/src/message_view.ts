import * as Sentry from "@sentry/browser";
import {SPAN_STATUS_OK} from "@sentry/core";
import $ from "jquery";
import assert from "minimalistic-assert";
import {z} from "zod";

import * as activity_ui from "./activity_ui.ts";
import {all_messages_data} from "./all_messages_data.ts";
import * as blueslip from "./blueslip.ts";
import * as browser_history from "./browser_history.ts";
import * as channel from "./channel.ts";
import * as compose_actions from "./compose_actions.ts";
import type {NarrowActivateOpts} from "./compose_actions.ts";
import * as compose_banner from "./compose_banner.ts";
import * as compose_closed_ui from "./compose_closed_ui.ts";
import * as compose_notifications from "./compose_notifications.ts";
import * as compose_recipient from "./compose_recipient.ts";
import * as compose_state from "./compose_state.ts";
import * as condense from "./condense.ts";
import * as feedback_widget from "./feedback_widget.ts";
import type {FetchStatus} from "./fetch_status.ts";
import {Filter} from "./filter.ts";
import * as hash_parser from "./hash_parser.ts";
import * as hash_util from "./hash_util.ts";
import {$t} from "./i18n.ts";
import * as inbox_ui from "./inbox_ui.ts";
import * as inbox_util from "./inbox_util.ts";
import * as left_sidebar_navigation_area from "./left_sidebar_navigation_area.ts";
import * as message_edit from "./message_edit.ts";
import * as message_feed_loading from "./message_feed_loading.ts";
import * as message_feed_top_notices from "./message_feed_top_notices.ts";
import * as message_fetch from "./message_fetch.ts";
import * as message_helper from "./message_helper.ts";
import type {MessageList, SelectIdOpts} from "./message_list.ts";
import * as message_list from "./message_list.ts";
import {MessageListData} from "./message_list_data.ts";
import * as message_list_data_cache from "./message_list_data_cache.ts";
import * as message_lists from "./message_lists.ts";
import * as message_scroll_state from "./message_scroll_state.ts";
import {raw_message_schema} from "./message_store.ts";
import * as message_store from "./message_store.ts";
import * as message_view_header from "./message_view_header.ts";
import * as message_viewport from "./message_viewport.ts";
import * as narrow_banner from "./narrow_banner.ts";
import * as narrow_history from "./narrow_history.ts";
import * as narrow_state from "./narrow_state.ts";
import * as narrow_title from "./narrow_title.ts";
import {page_params} from "./page_params.ts";
import * as people from "./people.ts";
import * as pm_list from "./pm_list.ts";
import * as popup_banners from "./popup_banners.ts";
import * as recent_view_ui from "./recent_view_ui.ts";
import * as recent_view_util from "./recent_view_util.ts";
import * as resize from "./resize.ts";
import * as scheduled_messages_feed_ui from "./scheduled_messages_feed_ui.ts";
import {
    message_edit_history_visibility_policy_values,
    web_mark_read_on_scroll_policy_values,
} from "./settings_config.ts";
import * as spectators from "./spectators.ts";
import type {NarrowTerm} from "./state_data.ts";
import {realm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_list from "./stream_list.ts";
import * as submessage from "./submessage.ts";
import * as topic_generator from "./topic_generator.ts";
import * as typing_events from "./typing_events.ts";
import * as unread from "./unread.ts";
import * as unread_ops from "./unread_ops.ts";
import * as unread_ui from "./unread_ui.ts";
import {user_settings} from "./user_settings.ts";
import * as util from "./util.ts";

const LARGER_THAN_MAX_MESSAGE_ID = 10000000000000000;

const fetch_message_response_schema = z.object({
    message: raw_message_schema,
});

export function reset_ui_state(opts: {trigger?: string}): void {
    // Resets the state of various visual UI elements that are
    // a function of the current narrow.
    popup_banners.close_found_missing_unreads_banner();
    narrow_banner.hide_empty_narrow_message();
    message_feed_top_notices.hide_top_of_narrow_notices();
    message_feed_loading.hide_indicators();
    unread_ui.reset_unread_banner();
    // We sometimes prevent draft restoring until the narrow resets.
    compose_state.allow_draft_restoring();
    // Most users aren't going to send a bunch of a out-of-narrow messages
    // and expect to visit a list of narrows, so let's get these out of the way.
    let skip_automatic_new_visibility_policy_banner = false;
    if (opts && opts.trigger === "outside_current_view") {
        skip_automatic_new_visibility_policy_banner = true;
    }
    compose_banner.clear_message_sent_banners(true, skip_automatic_new_visibility_policy_banner);
}

export function changehash(newhash: string, trigger: string): void {
    if (browser_history.state.changing_hash) {
        // If we retargeted the narrow operation because a message was moved,
        // we want to have the current narrow hash in the browser history.
        if (trigger === "retarget message location") {
            window.location.replace(newhash);
        }
        return;
    }
    message_viewport.stop_auto_scrolling();

    if (trigger === "retarget topic location") {
        // It is important to use `replaceState` rather than `replace`
        // here for the `back` button to work; we don't want to use
        // any metadata potentially stored by
        // update_current_history_state_data associated with an old
        // URL for the target conversation, and conceptually we want
        // to replace the inaccurate/old URL for the conversation with
        // the current/corrected value.
        window.history.replaceState(null, "", newhash);
    } else {
        browser_history.set_hash(newhash);
    }
}

export function update_hash_to_match_filter(filter: Filter, trigger: string): void {
    if (browser_history.state.changing_hash && trigger !== "retarget message location") {
        return;
    }
    const new_hash = hash_util.search_terms_to_hash(filter.terms());
    changehash(new_hash, trigger);

    if (stream_list.is_zoomed_in()) {
        browser_history.update_current_history_state_data({show_more_topics: true});
    }
}

type TargetMessageIdInfo = {
    target_id: number | undefined;
    final_select_id: number | undefined;
    local_select_id: number | undefined;
    first_unread_msg_id_pending_server_verification: number | undefined;
};

function create_and_update_message_list(
    filter: Filter,
    id_info: TargetMessageIdInfo,
    opts: ShowMessageViewOpts & {
        then_select_id: number;
    },
): {
    msg_list: MessageList;
    restore_rendered_list: boolean;
} {
    const excludes_muted_topics = filter.excludes_muted_topics();

    // Check if we already have a rendered message list for the `filter`.
    // TODO: If we add a message list other than `is_in_home` to be save as rendered,
    // we need to add a `is_equal` function to `Filter` to compare the filters.
    let msg_list;
    let restore_rendered_list = false;
    const is_combined_feed_global_view = filter.is_in_home();
    if (!opts.force_rerender) {
        for (const list of message_lists.all_rendered_message_lists()) {
            if (is_combined_feed_global_view && list.data.filter.is_in_home()) {
                if (opts.then_select_id > 0 && !list.msg_id_in_fetched_range(opts.then_select_id)) {
                    // We don't have the target message in the current rendered list.
                    // Read MessageList.should_preserve_current_rendered_state for details.
                    break;
                }

                msg_list = list;
                restore_rendered_list = true;
                break;
            }
        }
    }

    if (!restore_rendered_list) {
        // If we don't have a cached message list for the narrow, we
        // need to construct one from scratch.
        let msg_data = new MessageListData({
            filter,
            excludes_muted_topics,
        });

        const original_id_info = {...id_info};
        // Populate the message list if we can apply our filter locally (i.e.
        // with no server help) and we have the message we want to select.
        // Also update id_info accordingly.
        if (!filter.requires_adjustment_for_moved_with_target) {
            const superset_datasets = message_list_data_cache.get_superset_datasets(filter);
            for (const superset_data of superset_datasets) {
                // Reset properties that might have been set.
                id_info = Object.assign(id_info, original_id_info);
                maybe_add_local_messages({
                    id_info,
                    msg_data,
                    superset_data,
                });

                if (id_info.local_select_id) {
                    // We have the message we want to select.
                    break;
                }

                msg_data = new MessageListData({
                    filter,
                    excludes_muted_topics,
                });
            }
        }

        if (!id_info.local_select_id) {
            // If we're not actually ready to select an ID, we need to
            // trash the `MessageListData` object that we just constructed
            // and pass an empty one to MessageList, because the block of
            // messages in the MessageListData built inside
            // maybe_add_local_messages is likely not be contiguous with
            // the block we're about to request from the server instead.
            msg_data = new MessageListData({
                filter,
                excludes_muted_topics,
            });
        }

        msg_list = new message_list.MessageList({
            data: msg_data,
        });
    }
    assert(msg_list !== undefined);

    // Put the narrow terms in the URL fragment/hash.
    //
    // opts.change_hash will be false when the URL fragment was
    // the source of this narrow, and the fragment was not a link to
    // a specific target message ID that has been moved.
    //
    // This needs to be called at the same time as updating the
    // current message list so that we don't need to think about
    // bugs related to the URL fragment/hash being desynced from
    // message_lists.current.
    //
    // It's fine for the hash change to happen anytime before updating
    // the current message list as we are trying to emulate the `hashchange`
    // workflow we have which calls `message_view.show` after hash is updated.
    if (opts.change_hash) {
        update_hash_to_match_filter(filter, opts.trigger ?? "unknown");
        opts.show_more_topics = browser_history.get_current_state_show_more_topics() ?? false;
    }

    // Show the new set of messages. It is important to set message_lists.current to
    // the view right as it's being shown, because we rely on message_lists.current
    // being shown for deciding when to condense messages.
    // From here on down, any calls to the narrow_state API will
    // reflect the requested narrow.
    message_lists.update_current_message_list(msg_list);
    return {msg_list, restore_rendered_list};
}

function handle_post_message_list_change(
    id_info: TargetMessageIdInfo,
    msg_list: MessageList,
    opts: NarrowActivateOpts,
    select_immediately: boolean,
    select_opts: SelectIdOpts,
    then_select_offset: number | undefined,
): void {
    // Important: We need to consider opening the compose box
    // before calling render_message_list_with_selected_message, so that the logic in
    // recenter_view for positioning the currently selected
    // message can take into account the space consumed by the
    // open compose box.
    compose_actions.on_narrow(opts);

    if (select_immediately) {
        render_message_list_with_selected_message({
            id_info,
            select_offset: then_select_offset,
            msg_list: message_lists.current,
            select_opts,
        });
    }

    handle_post_view_change(msg_list, opts);

    unread_ui.update_unread_banner();

    // It is important to call this after other important updates
    // like narrow filter and compose recipients happen.
    compose_recipient.handle_middle_pane_transition();
}

export function try_rendering_locally_for_same_narrow(
    filter: Filter,
    opts: ShowMessageViewOpts,
): boolean {
    const current_filter = narrow_state.filter();
    let target_scroll_offset;
    if (!current_filter) {
        return false;
    }

    let target_id;
    if (opts.then_select_id !== undefined) {
        target_id = opts.then_select_id;
        target_scroll_offset = opts.then_select_offset;
    } else if (filter.has_operator("near")) {
        target_id = Number.parseInt(filter.operands("near")[0]!, 10);
    } else if (filter.equals(current_filter)) {
        // The caller doesn't want to force rerender and the filter is the same.
        // Also, we don't have a specific message id we want to select, so we
        // just keep the same message id selected.
        return true;
    } else {
        return false;
    }

    const target_message = message_lists.current?.get(target_id);
    if (!target_message) {
        return false;
    }

    const adjusted_terms = Filter.adjusted_terms_if_moved(filter.terms(), target_message);
    if (adjusted_terms !== null) {
        filter = new Filter(adjusted_terms);
    }

    // If the difference between the current filter and the new filter
    // is just a `near` operator, or just the value of a `near` operator,
    // we can render the new filter without a rerender of the message list
    // if the target message in the `near` operator is already rendered.
    const excluded_operators = ["near"];
    if (!filter.equals(current_filter, excluded_operators)) {
        return false;
    }

    assert(message_lists.current !== undefined);
    const currently_selected_id = message_lists.current?.selected_id();
    if (currently_selected_id !== target_id) {
        message_lists.current.select_id(target_id, {
            then_scroll: true,
            ...(target_scroll_offset !== undefined && {target_scroll_offset}),
        });
    }

    message_lists.current.data.filter = filter;
    update_hash_to_match_filter(filter, "retarget message location");
    message_view_header.render_title_area();
    return true;
}

export type ShowMessageViewOpts = {
    force_rerender?: boolean;
    force_close?: boolean;
    change_hash?: boolean;
    trigger?: string;
    fetched_target_message?: boolean;
    then_select_id?: number | undefined;
    then_select_offset?: number | undefined;
    show_more_topics?: boolean;
};

export function get_id_info(): TargetMessageIdInfo {
    return {
        target_id: undefined,
        final_select_id: undefined,
        local_select_id: undefined,
        first_unread_msg_id_pending_server_verification: undefined,
    };
}

export let show = (raw_terms: NarrowTerm[], show_opts: ShowMessageViewOpts): void => {
    /* Main entry point for switching to a new view / message list.

       Supported parameters:

       raw_terms: Narrowing/search terms; used to construct
       a Filter object that decides which messages belong in the
       view.

       All other options are encoded via the `opts` dictionary:

       * trigger: Optional parameter used mainly for logging and some
         custom UI behavior for certain buttons.  Generally aim to
         have this be unique for each UI widget that can trigger narrowing.

       * change_hash: Whether this narrow should change the URL
         fragment ("hash") in the URL bar.  Should be true unless the
         URL is already correct (E.g. because the hashchange logic
         itself is triggering the change of view).

       * then_select_id: If the caller wants us to do the narrow
         centered on a specific message ID ("anchor" in the API
         parlance), specify that here.  Useful e.g. when the user
         clicks on a specific message; implied by a `near:` operator.

       * then_select_offset: Offset from the top of the page in pixels
         at which to place the then_select_id message following
         rendering.  Important to avoid what would otherwise feel like
         visual glitches after clicking on a specific message's heading
         or rerendering due to server-side changes.
    */

    // No operators is an alias for the Combined Feed view.
    if (raw_terms.length === 0) {
        raw_terms = [{operator: "in", operand: "home"}];
    }
    const filter = new Filter(raw_terms);
    filter.try_adjusting_for_moved_with_target();

    if (!show_opts.force_rerender && try_rendering_locally_for_same_narrow(filter, show_opts)) {
        return;
    }

    const is_combined_feed_global_view = filter.is_in_home();
    const is_narrowed_to_combined_feed_view = narrow_state.filter()?.is_in_home();
    if (
        !show_opts.force_rerender &&
        is_narrowed_to_combined_feed_view &&
        is_combined_feed_global_view
    ) {
        // If we're already looking at the combined feed, exit without doing any work.
        return;
    }

    if (is_combined_feed_global_view && message_scroll_state.actively_scrolling) {
        // TODO: Figure out why puppeteer test for this fails when run for narrows
        // other than `Combined feed`.

        // There is no way to intercept in-flight scroll events, and they will
        // cause you to end up in the wrong place if you are actively scrolling
        // on an unnarrow. Wait a bit and try again once the scrolling is likely over.
        setTimeout(() => {
            show(raw_terms, show_opts);
        }, 50);
        return;
    }

    // Since message_view.show is called directly from various
    // places in our code without passing through hashchange,
    // we need to check if the narrow is allowed for spectator here too.
    if (
        page_params.is_spectator &&
        raw_terms.length > 0 &&
        // TODO: is:home is currently not permitted for spectators
        // because they can't mute things; maybe that's the wrong
        // policy?
        !is_combined_feed_global_view &&
        raw_terms.some(
            (raw_term) =>
                !hash_parser.is_an_allowed_web_public_narrow(raw_term.operator, raw_term.operand),
        )
    ) {
        spectators.login_to_access();
        return;
    }

    const coming_from_recent_view = recent_view_util.is_visible();
    const coming_from_inbox = inbox_util.is_visible();

    const opts = {
        change_hash: true,
        trigger: "unknown",
        show_more_topics: false,
        ...show_opts,
        then_select_id: show_opts.then_select_id ?? -1,
    };

    const span_data = {
        op: "function",
        data: {raw_terms, trigger: opts.trigger},
    };
    void Sentry.startSpan({...span_data, name: "narrow"}, async (span) => {
        const id_info = get_id_info();
        const terms = filter.terms();

        // These two narrowing operators specify what message should be
        // selected and should be the center of the narrow.
        if (filter.has_operator("near")) {
            id_info.target_id = Number.parseInt(filter.operands("near")[0]!, 10);
        }
        if (filter.has_operator("id")) {
            id_info.target_id = Number.parseInt(filter.operands("id")[0]!, 10);
        }

        // Narrow with near / id operator. There are two possibilities:
        // * The user is clicking a permanent link to a conversation, in which
        //   case we want to look up the anchor message and see if it has moved.
        // * The user did a search for something like stream:foo topic:bar near:1
        //   (or some other ID that is not an actual message in the topic).
        //
        // We attempt the match the stream and topic with that of the
        // message in case the message was moved after the link was
        // created. This ensures near / id links work and will redirect
        // correctly if the topic was moved (including being resolved).
        if (id_info.target_id && filter.has_operator("channel") && filter.has_operator("topic")) {
            const target_message = message_store.get(id_info.target_id);

            if (target_message) {
                // If we have the target message ID for the narrow in our
                // local cache, and the target message has been moved from
                // the stream/topic pair that was requested to some other
                // location, then we should retarget this narrow operation
                // to where the message is located now.
                const narrow_topic = filter.operands("topic")[0]!;
                const narrow_stream_data = stream_data.get_sub_by_id_string(
                    filter.operands("channel")[0]!,
                );
                if (!narrow_stream_data) {
                    // The stream id is invalid or incorrect in the URL.
                    // We reconstruct the narrow with the data from the
                    // target message ID that we have.
                    const adjusted_terms = Filter.adjusted_terms_if_moved(
                        raw_terms,
                        target_message,
                    );

                    if (adjusted_terms === null) {
                        return;
                    }

                    show(adjusted_terms, {
                        ...opts,
                        // Update the URL fragment to reflect the redirect.
                        change_hash: true,
                        trigger: "retarget message location",
                    });
                    return;
                }
                const narrow_stream_id = narrow_stream_data.stream_id;
                const narrow_dict = {stream_id: narrow_stream_id, topic: narrow_topic};

                const narrow_exists_in_edit_history =
                    message_edit.stream_and_topic_exist_in_edit_history(
                        target_message,
                        narrow_stream_id,
                        narrow_topic,
                    );

                // It's possible for a message to have moved to another
                // topic and then moved back to the current topic. In this
                // situation, narrow_exists_in_edit_history will be true,
                // but we don't need to redirect the narrow.
                const narrow_matches_target_message =
                    target_message.type === "stream" &&
                    util.same_stream_and_topic(target_message, narrow_dict);

                if (
                    !narrow_matches_target_message &&
                    (narrow_exists_in_edit_history ||
                        realm.realm_message_edit_history_visibility_policy ===
                            message_edit_history_visibility_policy_values.never.code)
                ) {
                    const adjusted_terms = Filter.adjusted_terms_if_moved(
                        raw_terms,
                        target_message,
                    );
                    if (adjusted_terms !== null) {
                        show(adjusted_terms, {
                            ...opts,
                            // Update the URL fragment to reflect the redirect.
                            change_hash: true,
                            trigger: "retarget message location",
                        });
                        return;
                    }
                }
            } else if (!opts.fetched_target_message) {
                // If we don't have the target message ID locally and
                // haven't attempted to fetch it, then we ask the server
                // for it.
                channel.get({
                    url: `/json/messages/${id_info.target_id}`,
                    data: {allow_empty_topic_name: true},
                    success(raw_data) {
                        const data = fetch_message_response_schema.parse(raw_data);
                        // After the message is fetched, we make the
                        // message locally available and then call
                        // message_view.show recursively, setting a flag to
                        // indicate we've already done this.
                        message_helper.process_new_message(data.message);
                        show(raw_terms, {
                            ...opts,
                            fetched_target_message: true,
                        });
                    },
                    error() {
                        // Message doesn't exist or user doesn't have
                        // access to the target message ID. This will
                        // happen, for example, if a user types
                        // `stream:foo topic:bar near:1` into the search
                        // box. No special rewriting is required, so call
                        // message_view.show recursively.
                        show(raw_terms, {
                            fetched_target_message: true,
                            ...opts,
                        });
                    },
                });

                // The channel.get will call message_view.show recursively
                // from a continuation unconditionally; the correct thing
                // to do here is return.
                return;
            }
        }

        // IMPORTANT: No code that modifies UI state should appear above
        // this point. This is important to prevent calling such functions
        // more than once in the event that we call message_view.show.
        // recursively.
        reset_ui_state(opts);

        if (coming_from_recent_view) {
            recent_view_ui.hide();
        } else if (coming_from_inbox) {
            inbox_ui.hide();
        }

        blueslip.debug("Narrowed", {
            operators: terms.map((e) => e.operator),
            trigger: opts ? opts.trigger : undefined,
            previous_id: message_lists.current?.selected_id(),
        });

        if (opts.then_select_id > 0) {
            // We override target_id in this case, since the user could be
            // having a near: narrow auto-reloaded.
            id_info.target_id = opts.then_select_id;
            // Position selected row to not scroll off-screen.
            if (opts.then_select_offset === undefined && message_lists.current !== undefined) {
                const $row = message_lists.current.get_row(opts.then_select_id);
                if ($row.length > 0) {
                    const row_props = $row.get_offset_to_window();
                    const navbar_height = $("#navbar-fixed-container").height()!;
                    // 30px height + 10px top margin.
                    const compose_box_top = $("#compose").get_offset_to_window().top;
                    const sticky_header_outer_height = 40;
                    const min_height_for_message_top_visible =
                        navbar_height + sticky_header_outer_height;

                    if (
                        // We want to keep the selected message in the same scroll position after the narrow changes if possible.
                        // Row top should be below the sticky header.
                        row_props.top >= min_height_for_message_top_visible &&
                        // Row top and some part of message should be above the compose box.
                        row_props.top + 10 <= compose_box_top
                    ) {
                        // Use the same offset of row in the new narrow as it is in the current narrow.
                        opts.then_select_offset = row_props.top;
                    } else {
                        // Otherwise, show selected message below the sticky header.
                        opts.then_select_offset = min_height_for_message_top_visible;
                    }
                }
            }
        }

        const {msg_list, restore_rendered_list} = create_and_update_message_list(
            filter,
            id_info,
            opts,
        );

        let select_immediately: boolean;
        let select_opts: SelectIdOpts;
        let then_select_offset: number | undefined;
        if (restore_rendered_list) {
            select_immediately = true;
            select_opts = {
                empty_ok: true,
                force_rerender: false,
            };

            if (opts.then_select_id !== -1) {
                // Restore user's last position in narrow if user is navigation via browser back / forward button.
                id_info.final_select_id = opts.then_select_id;
                then_select_offset = opts.then_select_offset;
            }

            // We are navigating to the combined feed from another
            // narrow, so we reset the reading state to allow user to
            // read messages again in the combined feed if user has
            // marked some messages as unread in the last combined
            // feed session and thus prevented reading.
            assert(message_lists.current !== undefined);
            message_lists.current.resume_reading();
            // Reset the collapsed status of messages rows.
            condense.condense_and_collapse(message_lists.current.view.$list.find(".message_row"));
            message_edit.restore_edit_state_after_message_view_change();
            submessage.process_widget_rows_in_list(message_lists.current);
            message_feed_top_notices.update_top_of_narrow_notices(msg_list);

            // We may need to scroll to the selected message after swapping
            // the currently displayed center panel to the combined feed.
            message_viewport.maybe_scroll_to_selected();
        } else {
            select_immediately = id_info.local_select_id !== undefined;
            select_opts = {
                empty_ok: false,
                force_rerender: true,
            };

            if (id_info.target_id === id_info.final_select_id) {
                then_select_offset = opts.then_select_offset;
            }

            {
                let anchor;

                // Either we're trying to center the narrow around a
                // particular message ID (which could be max_int), or we're
                // asking the server to figure out for us what the first
                // unread message is, and center the narrow around that.
                switch (id_info.final_select_id) {
                    case undefined:
                        anchor = "first_unread";
                        break;
                    case -1:
                        // This case should never happen in this code path; it's
                        // here in case we choose to extract this as an
                        // independent reusable function.
                        anchor = "oldest";
                        break;
                    case LARGER_THAN_MAX_MESSAGE_ID:
                        anchor = "newest";
                        break;
                    default:
                        anchor = id_info.final_select_id;
                }
                message_fetch.load_messages_for_narrow({
                    anchor,
                    validate_filter_topic_post_fetch:
                        filter.requires_adjustment_for_moved_with_target,
                    cont() {
                        if (message_lists.current !== msg_list) {
                            return;
                        }

                        if (filter.narrow_requires_hash_change) {
                            // We've already adjusted our filter via
                            // filter.try_adjusting_for_moved_with_target, and
                            // should update the URL hash accordingly.
                            update_hash_to_match_filter(filter, "retarget topic location");
                            // Since filter is updated, we need to handle various things
                            // like updating the message view header title, unread banner
                            // based on the updated filter.
                            handle_post_message_list_change(
                                id_info,
                                message_lists.current,
                                opts,
                                select_immediately,
                                select_opts,
                                then_select_offset,
                            );
                            filter.narrow_requires_hash_change = false;
                        }
                        if (!select_immediately) {
                            render_message_list_with_selected_message({
                                id_info,
                                select_offset: then_select_offset,
                                msg_list,
                                select_opts,
                            });
                        }
                    },
                    msg_list,
                });
            }
        }
        assert(select_opts !== undefined);
        assert(select_immediately !== undefined);

        handle_post_message_list_change(
            id_info,
            msg_list,
            opts,
            select_immediately,
            select_opts,
            then_select_offset,
        );
        if (
            id_info.first_unread_msg_id_pending_server_verification &&
            filter.is_conversation_view()
        ) {
            const params = message_fetch.get_parameters_for_message_fetch_api({
                anchor: "first_unread",
                num_before: 0,
                num_after: 0,
                cont() {
                    // Success callback is sufficient to do what we need to do
                    // here, we don't need another post fetch callback.
                },
                msg_list_data: msg_list.data,
            });
            void channel.get({
                url: "/json/messages",
                data: params,
                success(raw_data) {
                    // If we switched narrow, there is nothing to do.
                    if (
                        msg_list.id !== message_lists.current?.id ||
                        !id_info.first_unread_msg_id_pending_server_verification
                    ) {
                        return;
                    }
                    const data = message_fetch.response_schema.parse(raw_data);
                    const first_unread_message_id = data.anchor;
                    const current_selected_id = msg_list.selected_id();
                    if (
                        first_unread_message_id <
                        id_info.first_unread_msg_id_pending_server_verification
                    ) {
                        // We convert the current narrow into a `near` narrow so that
                        // user doesn't accidentally mark msgs read which they haven't seen.
                        const terms = [
                            ...msg_list.data.filter.terms(),
                            {
                                operator: "near",
                                operand: current_selected_id.toString(),
                            },
                        ];
                        const opts = {
                            trigger: "old_unreads_missing",
                        };
                        show(terms, opts);

                        const on_jump_to_first_unread = (): void => {
                            // This is a no-op if the user has already switched narrow.
                            if (msg_list.id !== message_lists.current?.id) {
                                return;
                            }

                            show(
                                message_lists.current.data.filter
                                    .terms()
                                    .filter((term) => term.operator !== "near"),
                                {then_select_id: first_unread_message_id},
                            );
                        };
                        // Show user a banner with a button to allow user to navigate
                        // to the first unread if required.
                        popup_banners.open_found_missing_unreads_banner(on_jump_to_first_unread);
                    }
                },
            });
        }

        const post_span_context = {
            name: "post-narrow busy time",
            op: "function",
        };
        await Sentry.startSpan(post_span_context, async () => {
            span?.setStatus({code: SPAN_STATUS_OK});
            await new Promise((resolve) => setTimeout(resolve, 0));
            resize.resize_stream_filters_container();
        });
    });
};

export function rewire_show(value: typeof show): void {
    show = value;
}

function navigate_to_anchor_message(opts: {
    anchor: string;
    fetch_status_shows_anchor_fetched: (fetch_status: FetchStatus) => boolean;
    message_list_data_to_target_message_id: (data: MessageListData) => number;
}): void {
    const {anchor, fetch_status_shows_anchor_fetched, message_list_data_to_target_message_id} =
        opts;
    // The function navigates user to the anchor in the current
    // message list. We don't use `message_view.show` here due
    // to following reasons:
    // * `message_view.show` has a lot of logic related to rendering
    //    a new message list which is not required here since we want
    //    to just select the anchor in the current message list without
    //    losing any context.
    // * `message_view.show` tries to reset the narrow state like marking
    //    messages as read / narrow banners etc. which we don't want here.
    // *  User is already at the correct hash, so we don't need to
    //    check / update as it as done in `message_view.show`.
    // *  We don't need to care about `then_select_id` or `near` operators
    //    here, which will otherwise be a source of confusion if we did
    //    this in `message_view.show`.
    //
    // These functions are scoped inside `navigate_to_anchor_message` to
    // to avoid them being used for any other purpose.
    function duplicate_current_msg_list_with_new_data(data: MessageListData): MessageList {
        assert(message_lists.current !== undefined);
        const msg_list = new message_list.MessageList({data});
        msg_list.reading_prevented = message_lists.current.reading_prevented;
        return msg_list;
    }

    function select_msg_id(msg_id: number, select_opts?: SelectIdOpts): void {
        assert(message_lists.current !== undefined);
        message_lists.current.select_id(msg_id, {
            then_scroll: true,
            from_scroll: false,
            ...select_opts,
        });
    }

    function select_anchor_using_data(data: MessageListData): void {
        const msg_list = duplicate_current_msg_list_with_new_data(data);
        message_lists.update_current_message_list(msg_list);
        // `force_rerender` is required to render the new data.
        select_msg_id(message_list_data_to_target_message_id(data), {force_rerender: true});
    }

    assert(message_lists.current !== undefined);
    if (fetch_status_shows_anchor_fetched(message_lists.current.data.fetch_status)) {
        select_msg_id(message_list_data_to_target_message_id(message_lists.current.data));
    } else if (fetch_status_shows_anchor_fetched(all_messages_data.fetch_status)) {
        // We can load messages into `msg_list_data` but we don't know
        // the fetch status until we contact server. If we are contacting the
        // server, it is better to just fetch the required messages instead
        // of just fetching status.
        //
        // So, a cheaper check is to see if we have found the anchor in
        // `all_messages_data`, and if we have, we can say `msg_list_data`
        // will also have the anchor (for oldest / newest anchors at least).
        const msg_list_data = new MessageListData({
            filter: message_lists.current.data.filter,
            excludes_muted_topics: message_lists.current.data.excludes_muted_topics,
        });
        load_local_messages(msg_list_data, all_messages_data);
        select_anchor_using_data(msg_list_data);
    } else {
        const msg_list_data = new MessageListData({
            filter: message_lists.current.data.filter,
            excludes_muted_topics: message_lists.current.data.excludes_muted_topics,
        });

        message_fetch.load_messages_around_anchor(
            anchor,
            () => {
                select_anchor_using_data(msg_list_data);
            },
            msg_list_data,
        );
    }
}

export function fast_track_current_msg_list_to_anchor(anchor: string): void {
    assert(message_lists.current !== undefined);
    if (message_lists.current.visibly_empty()) {
        return;
    }

    if (anchor === "oldest") {
        navigate_to_anchor_message({
            anchor,
            fetch_status_shows_anchor_fetched(fetch_status) {
                return fetch_status.has_found_oldest();
            },
            message_list_data_to_target_message_id(msg_list_data) {
                return msg_list_data.first()!.id;
            },
        });
    } else if (anchor === "newest") {
        navigate_to_anchor_message({
            anchor,
            fetch_status_shows_anchor_fetched(fetch_status) {
                return fetch_status.has_found_newest();
            },
            message_list_data_to_target_message_id(msg_list_data) {
                return msg_list_data.last()!.id;
            },
        });
    } else {
        blueslip.error(`Invalid anchor value: ${anchor}`);
    }
}

function min_defined(a: number | undefined, b: number | undefined): number | undefined {
    if (a === undefined) {
        return b;
    }
    if (b === undefined) {
        return a;
    }
    return Math.min(a, b);
}

function load_local_messages(msg_data: MessageListData, superset_data: MessageListData): boolean {
    // This little helper loads messages into our narrow message
    // data and returns true unless it's visibly empty.  We use this for
    // cases when our local cache (superset_data) has at least
    // one message the user will expect to see in the new narrow.

    const in_msgs = superset_data.all_messages();
    const is_contiguous_history = true;
    msg_data.add_messages(in_msgs, is_contiguous_history);

    return !msg_data.visibly_empty();
}

export function maybe_add_local_messages(opts: {
    id_info: TargetMessageIdInfo;
    msg_data: MessageListData;
    superset_data: MessageListData;
}): void {
    // This function determines whether we need to go to the server to
    // fetch messages for the requested narrow, or whether we have the
    // data cached locally to render the narrow correctly without
    // waiting for the server.  There are two high-level outcomes:
    //
    // 1. We're centering this narrow on the first unread message: In
    // this case final_select_id is left undefined or first unread
    // message id locally.
    //
    // 2. We're centering this narrow on the most recent matching
    // message. In this case we select final_select_id to the latest
    // message in the local cache (if the local cache has the latest
    // messages for this narrow) or max_int (if it doesn't).
    //
    // In either case, this function does two very closely related
    // things, both of which are somewhat optional:
    //
    //  - update id_info with more complete values
    //  - add messages into our message list from our local cache
    const id_info = opts.id_info;
    const msg_data = opts.msg_data;
    const superset_data = opts.superset_data;
    const filter = msg_data.filter;
    const unread_info = narrow_state.get_first_unread_info(filter);

    // If we don't have a specific message we're hoping to select
    // (i.e. no `target_id`) and the narrow's filter doesn't
    // allow_use_first_unread_when_narrowing, we want to just render
    // the latest messages matching the filter.  To ensure this, we
    // set an initial value final_select_id to `max_int`.
    //
    // While that's a confusing naming choice (`final_select_id` is
    // meant to be final in the context of the caller), this sets the
    // default behavior to be fetching and then selecting the very
    // latest message in this narrow.
    //
    // If we're able to render the narrow locally, we'll end up
    // overwriting this value with the ID of the latest message in the
    // narrow later in this function.
    if (!id_info.target_id && !filter.allow_use_first_unread_when_narrowing()) {
        // Note that this may be overwritten; see above comment.
        id_info.final_select_id = LARGER_THAN_MAX_MESSAGE_ID;
    }

    if (unread_info.flavor === "cannot_compute") {
        // Full-text search and potentially other future cases where
        // we can't check which messages match on the frontend, so it
        // doesn't matter what's in our cache, we must go to the server.
        if (id_info.target_id) {
            // TODO: Ideally, in this case we should be asking the
            // server to give us the first unread or the target_id,
            // whichever is first (i.e. basically the `found` logic
            // below), but the server doesn't support that query.
            id_info.final_select_id = id_info.target_id;
        }
        // if we can't compute a next unread id, just return without
        // setting local_select_id, so that we go to the server.
        return;
    }

    // We can now assume filter.can_apply_locally(),
    // because !can_apply_locally => cannot_compute

    if (unread_info.flavor === "found" && filter.allow_use_first_unread_when_narrowing()) {
        // We have at least one unread message in this narrow, and the
        // narrow is one where we use the first unread message in
        // narrowing positioning decisions.  So either we aim for the
        // first unread message, or the target_id (if any), whichever
        // is earlier.  See #2091 for a detailed explanation of why we
        // need to look at unread here.
        id_info.final_select_id = min_defined(id_info.target_id, unread_info.msg_id);
        assert(id_info.final_select_id !== undefined);

        // We found a message id to select from the unread data available
        // locally but if we didn't have the complete unread data locally
        // cached, we need to check from server if it is the first unread.
        if (unread.old_unreads_missing) {
            id_info.first_unread_msg_id_pending_server_verification = unread_info.msg_id;
        }

        if (!load_local_messages(msg_data, superset_data)) {
            // We don't have the message we want to select locally,
            // and since our unread data is incomplete, we just
            // ask server directly for `first_unread`.
            if (
                unread.old_unreads_missing &&
                // Ensure our intent is to narrow to first unread.
                id_info.final_select_id === unread_info.msg_id &&
                id_info.target_id === undefined
            ) {
                id_info.final_select_id = undefined;
            }
            return;
        }

        // Now that we know what message ID we're going to land on, we
        // can see if we can take the user there locally.
        if (msg_data.get(id_info.final_select_id)) {
            id_info.local_select_id = id_info.final_select_id;
        }

        // If we don't have the first unread message locally, we must
        // go to the server to get it before we can render the narrow.
        return;
    }

    // In all cases below here, the first unread message is irrelevant
    // to our positioning decisions, either because there are no
    // unread messages (unread_info.flavor === 'not_found') or because
    // this is a mixed narrow where we prefer the bottom of the feed
    // to the first unread message for positioning (and the narrow
    // will be configured to not mark messages as read).

    if (!id_info.target_id) {
        // Without unread messages or a target ID, we're narrowing to
        // the very latest message or first unread if matching the narrow allows.

        if (!superset_data.fetch_status.has_found_newest()) {
            // If superset_data is not caught up, then we cannot
            // populate the latest messages for the target narrow
            // correctly from there, so we must go to the server.
            return;
        }

        if (!load_local_messages(msg_data, superset_data)) {
            return;
        }

        // Otherwise, we have matching messages, and superset_data
        // is caught up, so the last message in our now-populated
        // msg_data object must be the last message matching the
        // narrow the server could give us, so we can render locally.
        // and use local latest message id instead of max_int if set earlier.
        const last_msg = msg_data.last();
        assert(last_msg !== undefined);
        id_info.final_select_id = last_msg.id;
        id_info.local_select_id = id_info.final_select_id;
        return;
    }

    // We have a target_id and no unread messages complicating things,
    // so we definitely want to land on the target_id message.
    id_info.final_select_id = id_info.target_id;

    // TODO: We could improve on this next condition by considering
    // cases where
    // `superset_data.fetch_status.has_found_oldest()`; which
    // would come up with e.g. `near: 0` in a small organization.
    //
    // And similarly for `near: max_int` with has_found_newest.
    if (
        superset_data.visibly_empty() ||
        id_info.target_id < superset_data.first()!.id ||
        id_info.target_id > superset_data.last()!.id
    ) {
        // If the target message is outside the range that we had
        // available for local population, we must go to the server.
        return;
    }
    if (!load_local_messages(msg_data, superset_data)) {
        return;
    }
    if (msg_data.get(id_info.target_id)) {
        // We have a range of locally renderable messages, including
        // our target, so we can render the narrow locally.
        id_info.local_select_id = id_info.final_select_id;
        return;
    }

    // Note: Arguably, we could have a use_closest sort of condition
    // here to handle cases where `target_id` doesn't match the narrow
    // but is within the locally renderable range.  But
    // !can_apply_locally + target_id is a rare combination in the
    // first place, so we don't bother.
    return;
}

export function render_message_list_with_selected_message(opts: {
    msg_list: MessageList | undefined;
    id_info: TargetMessageIdInfo;
    select_offset: number | undefined;
    select_opts: SelectIdOpts;
}): void {
    if (message_lists.current !== undefined && message_lists.current !== opts.msg_list) {
        // If we navigated away from a view while we were fetching
        // messages for it, don't attempt to move the currently
        // selected message.
        return;
    }

    assert(message_lists.current !== undefined);
    if (message_lists.current.visibly_empty()) {
        // There's nothing to select if there are no messages.
        return;
    }

    const id_info = opts.id_info;
    const select_offset = opts.select_offset;

    const msg_id = id_info.final_select_id ?? message_lists.current.first_unread_message_id();
    // There should be something since it's not visibly empty.
    assert(msg_id !== undefined);

    const preserve_pre_narrowing_screen_position =
        message_lists.current.get(msg_id) !== undefined && select_offset !== undefined;

    const then_scroll = !preserve_pre_narrowing_screen_position;

    // Here we render the actual message list to the DOM with the
    // target selected message, using the force_rerender parameter.
    //
    // TODO: Probably this should accept the offset parameter rather
    // than calling `set_message_offset` just after.
    message_lists.current.select_id(msg_id, {
        then_scroll,
        use_closest: true,
        ...opts.select_opts,
    });

    if (preserve_pre_narrowing_screen_position) {
        // Scroll so that the selected message is in the same
        // position in the viewport as it was prior to
        // narrowing
        message_lists.current.view.set_message_offset(select_offset);
    }
    message_lists.current.view.update_sticky_recipient_headers();
    unread_ops.process_visible();
    narrow_history.save_narrow_state_and_flush();
}

function activate_stream_for_cycle_hotkey(stream_id: number): void {
    // This is the common code for A/D hotkeys.
    const filter_expr = [{operator: "channel", operand: stream_id.toString()}];
    show(filter_expr, {});
}

export function stream_cycle_backward(): void {
    const curr_stream_id = narrow_state.stream_id();

    if (!curr_stream_id) {
        return;
    }

    const stream_id = topic_generator.get_prev_stream(curr_stream_id);

    if (!stream_id) {
        return;
    }

    activate_stream_for_cycle_hotkey(stream_id);
}

export function stream_cycle_forward(): void {
    const curr_stream_id = narrow_state.stream_id();

    if (!curr_stream_id) {
        return;
    }

    const stream_id = topic_generator.get_next_stream(curr_stream_id);

    if (!stream_id) {
        return;
    }

    activate_stream_for_cycle_hotkey(stream_id);
}

export function narrow_to_next_topic(opts: {trigger: string; only_followed_topics: boolean}): void {
    const curr_info = {
        stream_id: narrow_state.stream_id(),
        topic: narrow_state.topic(),
    };

    const next_narrow = topic_generator.get_next_topic(
        curr_info.stream_id,
        curr_info.topic,
        opts.only_followed_topics,
    );

    if (!next_narrow && opts.only_followed_topics) {
        feedback_widget.show({
            populate($container) {
                $container.text(
                    $t({defaultMessage: "You have no unread messages in followed topics."}),
                );
            },
            title_text: $t({defaultMessage: "You're done!"}),
        });
        return;
    }

    if (!next_narrow) {
        feedback_widget.show({
            populate($container) {
                $container.text($t({defaultMessage: "You have no more unread topics."}));
            },
            title_text: $t({defaultMessage: "You're done!"}),
        });
        return;
    }

    const filter_expr = [
        {operator: "channel", operand: next_narrow.stream_id.toString()},
        {operator: "topic", operand: next_narrow.topic},
    ];

    show(filter_expr, opts);
}

export function narrow_to_next_pm_string(opts = {}): void {
    const current_direct_message = narrow_state.pm_ids_string();
    const next_direct_message = topic_generator.get_next_unread_pm_string(current_direct_message);

    if (!next_direct_message) {
        feedback_widget.show({
            populate($container) {
                $container.text($t({defaultMessage: "You have no more unread direct messages."}));
            },
            title_text: $t({defaultMessage: "You're done!"}),
        });
        return;
    }

    // Hopefully someday we can narrow by user_ids_string instead of
    // mapping back to emails.
    const direct_message = people.user_ids_string_to_emails_string(next_direct_message);
    assert(direct_message !== undefined);

    const filter_expr = [{operator: "dm", operand: direct_message}];

    // force_close parameter is true to not auto open compose_box
    const updated_opts = {
        ...opts,
        force_close: true,
    };

    show(filter_expr, updated_opts);
}

export function narrow_by_topic(
    target_id: number,
    opts: {
        trigger: string;
    },
): void {
    // don't use message_lists.current as it won't work for muted messages or for out-of-narrow links
    const original = message_store.get(target_id);
    assert(original !== undefined);
    if (original.type !== "stream") {
        // Only stream messages have topics, but the
        // user wants us to narrow in some way.
        narrow_by_recipient(target_id, opts);
        return;
    }

    if (
        user_settings.web_mark_read_on_scroll_policy !==
        web_mark_read_on_scroll_policy_values.never.code
    ) {
        // We don't check message_list.can_mark_messages_read
        // here because the target message_list isn't initialized;
        // but the targeted message is about to be marked read
        // in the new view.
        unread_ops.notify_server_message_read(original);
    }

    const search_terms = [
        {operator: "channel", operand: original.stream_id.toString()},
        {operator: "topic", operand: original.topic},
    ];
    show(search_terms, {then_select_id: target_id, ...opts});
}

export function narrow_by_recipient(
    target_id: number,
    opts: {
        trigger: string;
    },
): void {
    const show_opts = {then_select_id: target_id, ...opts};
    // don't use message_lists.current as it won't work for muted messages or for out-of-narrow links
    const message = message_store.get(target_id);
    assert(message !== undefined);
    const emails = message.reply_to.split(",");
    const reply_to = people.sort_emails_by_username(emails);

    switch (message.type) {
        case "private":
            if (
                user_settings.web_mark_read_on_scroll_policy !==
                web_mark_read_on_scroll_policy_values.never.code
            ) {
                // We don't check message_list.can_mark_messages_read
                // here because the target message_list isn't initialized;
                // but the targeted message is about to be marked read
                // in the new view.
                unread_ops.notify_server_message_read(message);
            }
            show([{operator: "dm", operand: reply_to.join(",")}], show_opts);
            break;

        case "stream":
            if (
                user_settings.web_mark_read_on_scroll_policy ===
                web_mark_read_on_scroll_policy_values.always.code
            ) {
                // We don't check message_list.can_mark_messages_read
                // here because the target message_list isn't initialized;
                // but the targeted message is about to be marked read
                // in the new view.
                unread_ops.notify_server_message_read(message);
            }
            show(
                [
                    {
                        operator: "stream",
                        operand: message.stream_id.toString(),
                    },
                ],
                show_opts,
            );
            break;
    }
}

export function to_compose_target(): void {
    if (!compose_state.composing()) {
        return;
    }

    const opts = {
        trigger: "narrow_to_compose_target",
    };

    compose_banner.clear_search_view_banner();

    if (compose_state.get_message_type() === "stream") {
        const stream_id = compose_state.stream_id();
        if (!stream_id) {
            return;
        }
        // If we are composing to a new topic, we narrow to the stream but
        // grey-out the message view instead of narrowing to an empty view.
        const terms = [{operator: "channel", operand: stream_id.toString()}];
        const topic = compose_state.topic();
        if (topic !== "" || !realm.realm_mandatory_topics) {
            terms.push({operator: "topic", operand: topic});
        }
        show(terms, opts);
        return;
    }

    if (compose_state.get_message_type() === "private") {
        const recipient_string = compose_state.private_message_recipient();
        const emails = util.extract_pm_recipients(recipient_string);
        const invalid = emails.filter((email) => !people.is_valid_email_for_compose(email));
        // If there are no recipients or any recipient is
        // invalid, narrow to your direct message feed.
        if (emails.length === 0 || invalid.length > 0) {
            show([{operator: "is", operand: "dm"}], opts);
            return;
        }
        show([{operator: "dm", operand: util.normalize_recipients(recipient_string)}], opts);
    }
}

function handle_post_view_change(
    msg_list: MessageList,
    opts: {
        change_hash: boolean;
        show_more_topics: boolean;
    },
): void {
    const filter = msg_list.data.filter;

    if (narrow_state.narrowed_by_reply()) {
        compose_notifications.maybe_show_one_time_non_interleaved_view_messages_fading_banner();
    } else {
        compose_notifications.maybe_show_one_time_interleaved_view_messages_fading_banner();
    }

    scheduled_messages_feed_ui.update_schedule_message_indicator();
    typing_events.render_notifications_for_narrow();

    if (filter.contains_only_private_messages()) {
        compose_closed_ui.update_buttons_for_private();
    } else if (filter.is_conversation_view() || filter.includes_full_stream_history()) {
        compose_closed_ui.update_buttons_for_stream_views();
    } else {
        compose_closed_ui.update_buttons_for_non_specific_views();
    }
    compose_closed_ui.update_recipient_text_for_reply_button();

    message_view_header.render_title_area();

    narrow_title.update_narrow_title(filter);
    left_sidebar_navigation_area.handle_narrow_activated(filter);
    stream_list.handle_narrow_activated(filter, opts.change_hash, opts.show_more_topics);
    pm_list.handle_narrow_activated(filter);
    activity_ui.build_user_sidebar();
}

export function rerender_combined_feed(combined_feed_msg_list: MessageList): void {
    // Remove cache to avoid repopulating from it.
    message_list_data_cache.remove(combined_feed_msg_list.data.filter);
    show(combined_feed_msg_list.data.filter.terms(), {
        then_select_id: combined_feed_msg_list.selected_id(),
        then_select_offset: browser_history.current_scroll_offset(),
        trigger: "stream / topic visibility policy change",
        force_rerender: true,
    });
}
