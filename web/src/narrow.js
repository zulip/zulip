import * as Sentry from "@sentry/browser";
import $ from "jquery";

import {all_messages_data} from "./all_messages_data";
import * as blueslip from "./blueslip";
import * as browser_history from "./browser_history";
import * as channel from "./channel";
import * as compose_actions from "./compose_actions";
import * as compose_banner from "./compose_banner";
import * as compose_closed_ui from "./compose_closed_ui";
import * as compose_fade from "./compose_fade";
import * as compose_recipient from "./compose_recipient";
import * as compose_state from "./compose_state";
import * as condense from "./condense";
import {Filter} from "./filter";
import * as hash_util from "./hash_util";
import * as hashchange from "./hashchange";
import {$t} from "./i18n";
import * as inbox_ui from "./inbox_ui";
import * as inbox_util from "./inbox_util";
import * as left_sidebar_navigation_area from "./left_sidebar_navigation_area";
import * as message_edit from "./message_edit";
import * as message_feed_loading from "./message_feed_loading";
import * as message_feed_top_notices from "./message_feed_top_notices";
import * as message_fetch from "./message_fetch";
import * as message_helper from "./message_helper";
import * as message_list from "./message_list";
import {MessageListData} from "./message_list_data";
import * as message_lists from "./message_lists";
import * as message_store from "./message_store";
import * as message_view_header from "./message_view_header";
import * as narrow_banner from "./narrow_banner";
import * as narrow_history from "./narrow_history";
import * as narrow_state from "./narrow_state";
import * as notifications from "./notifications";
import {page_params} from "./page_params";
import * as people from "./people";
import * as pm_list from "./pm_list";
import * as recent_view_ui from "./recent_view_ui";
import * as recent_view_util from "./recent_view_util";
import * as resize from "./resize";
import * as search from "./search";
import {web_mark_read_on_scroll_policy_values} from "./settings_config";
import * as spectators from "./spectators";
import * as stream_data from "./stream_data";
import * as stream_list from "./stream_list";
import * as topic_generator from "./topic_generator";
import * as typing_events from "./typing_events";
import * as unread from "./unread";
import * as unread_ops from "./unread_ops";
import * as unread_ui from "./unread_ui";
import {user_settings} from "./user_settings";
import * as util from "./util";
import * as widgetize from "./widgetize";

const LARGER_THAN_MAX_MESSAGE_ID = 10000000000000000;

export function save_pre_narrow_offset_for_reload() {
    if (message_lists.current.selected_id() !== -1) {
        if (message_lists.current.selected_row().length === 0) {
            blueslip.debug("narrow.activate missing selected row", {
                selected_id: message_lists.current.selected_id(),
                selected_idx: message_lists.current.selected_idx(),
                selected_idx_exact: message_lists.current
                    .all_messages()
                    .indexOf(message_lists.current.get(message_lists.current.selected_id())),
                render_start: message_lists.current.view._render_win_start,
                render_end: message_lists.current.view._render_win_end,
            });
        }
        message_lists.current.pre_narrow_offset = message_lists.current
            .selected_row()
            .get_offset_to_window().top;
    }
}

export let has_shown_message_list_view = false;

export function compute_narrow_title(filter) {
    if (filter === undefined) {
        // "All messages" and "Recent conversations" views have
        // an `undefined` filter.
        if (recent_view_util.is_visible()) {
            return $t({defaultMessage: "Recent conversations"});
        }

        if (inbox_util.is_visible()) {
            return $t({defaultMessage: "Inbox"});
        }

        return $t({defaultMessage: "All messages"});
    }

    const filter_title = filter.get_title();

    if (filter_title === undefined) {
        // Default result for uncommon narrow/search views.
        return $t({defaultMessage: "Search results"});
    }

    if (filter.has_operator("stream")) {
        if (!filter._sub) {
            // The stream is not set because it does not currently
            // exist (possibly due to a stream name change), or it
            // is a private stream and the user is not subscribed.
            return filter_title;
        }
        if (filter.has_operator("topic")) {
            const topic_name = filter.operands("topic")[0];
            return "#" + filter_title + " > " + topic_name;
        }
        return "#" + filter_title;
    }

    if (filter.has_operator("dm")) {
        const emails = filter.operands("dm")[0];
        const user_ids = people.emails_strings_to_user_ids_string(emails);

        if (user_ids !== undefined) {
            return people.get_recipients(user_ids);
        }
        if (emails.includes(",")) {
            return $t({defaultMessage: "Invalid users"});
        }
        return $t({defaultMessage: "Invalid user"});
    }

    if (filter.has_operator("sender")) {
        const user = people.get_by_email(filter.operands("sender")[0]);
        if (user) {
            if (people.is_my_user_id(user.user_id)) {
                return $t({defaultMessage: "Messages sent by you"});
            }
            return $t(
                {defaultMessage: "Messages sent by {sender}"},
                {
                    sender: user.full_name,
                },
            );
        }
        return $t({defaultMessage: "Invalid user"});
    }

    return filter_title;
}

export let narrow_title = "home";
export function update_narrow_title(filter) {
    narrow_title = compute_narrow_title(filter);
    notifications.redraw_title();
}

export function reset_ui_state() {
    // Resets the state of various visual UI elements that are
    // a function of the current narrow.
    narrow_banner.hide_empty_narrow_message();
    message_feed_top_notices.hide_top_of_narrow_notices();
    message_feed_loading.hide_indicators();
    unread_ui.reset_unread_banner();
}

export function handle_middle_pane_transition() {
    if (compose_state.composing) {
        compose_recipient.update_narrow_to_recipient_visibility();
    }
}

export function activate(raw_operators, opts) {
    /* Main entry point for switching to a new view / message list.
       Note that for historical reasons related to the current
       client-side caching structure, the "All messages"/message_lists.home
       view is reached via `narrow.deactivate()`.

       The name is based on "narrowing to a subset of the user's
       messages.".  Supported parameters:

       raw_operators: Narrowing/search operators; used to construct
       a Filter object that decides which messages belong in the
       view.  Required (See the above note on how `message_lists.home` works)

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

    const was_narrowed_already = narrow_state.active();

    // Since narrow.activate is called directly from various
    // places in our code without passing through hashchange,
    // we need to check if the narrow is allowed for spectator here too.
    if (
        page_params.is_spectator &&
        raw_operators.length &&
        raw_operators.some(
            (raw_operator) => !hash_util.allowed_web_public_narrows.includes(raw_operator.operator),
        )
    ) {
        spectators.login_to_access();
        return;
    }

    const coming_from_recent_view = recent_view_util.is_visible();
    const coming_from_inbox = inbox_util.is_visible();

    // The empty narrow is the home view; so deactivate any narrow if
    // no operators were specified. Take us to all messages when this
    // happens from Recent Conversations view.
    if (raw_operators.length === 0) {
        browser_history.go_to_location("#all_messages");
        return;
    }

    opts = {
        then_select_id: -1,
        then_select_offset: undefined,
        change_hash: true,
        trigger: "unknown",
        ...opts,
    };

    const existing_span = Sentry.getCurrentHub().getScope().getSpan();
    const span_data = {
        op: "function",
        description: "narrow",
        data: {was_narrowed_already, raw_operators, trigger: opts.trigger},
    };
    let span;
    if (!existing_span) {
        span = Sentry.startTransaction({...span_data, name: "narrow"});
    } else {
        span = existing_span.startChild(span_data);
    }
    let do_close_span = true;
    try {
        const scope = Sentry.getCurrentHub().pushScope();
        scope.setSpan(span);

        const id_info = {
            target_id: undefined,
            local_select_id: undefined,
            final_select_id: undefined,
        };

        const filter = new Filter(raw_operators);
        const operators = filter.operators();

        // These two narrowing operators specify what message should be
        // selected and should be the center of the narrow.
        if (filter.has_operator("near")) {
            id_info.target_id = Number.parseInt(filter.operands("near")[0], 10);
        }
        if (filter.has_operator("id")) {
            id_info.target_id = Number.parseInt(filter.operands("id")[0], 10);
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
        if (id_info.target_id && filter.has_operator("stream") && filter.has_operator("topic")) {
            const target_message = message_store.get(id_info.target_id);

            function adjusted_operators_if_moved(operators, message) {
                const adjusted_operators = [];
                let operators_changed = false;

                for (const operator of operators) {
                    const adjusted_operator = {...operator};
                    if (
                        operator.operator === "stream" &&
                        !util.lower_same(operator.operand, message.display_recipient)
                    ) {
                        adjusted_operator.operand = message.display_recipient;
                        operators_changed = true;
                    }

                    if (
                        operator.operator === "topic" &&
                        !util.lower_same(operator.operand, message.topic)
                    ) {
                        adjusted_operator.operand = message.topic;
                        operators_changed = true;
                    }

                    adjusted_operators.push(adjusted_operator);
                }

                if (!operators_changed) {
                    return null;
                }

                return adjusted_operators;
            }

            if (target_message) {
                // If we have the target message ID for the narrow in our
                // local cache, and the target message has been moved from
                // the stream/topic pair that was requested to some other
                // location, then we should retarget this narrow operation
                // to where the message is located now.
                const narrow_topic = filter.operands("topic")[0];
                const narrow_stream_name = filter.operands("stream")[0];
                const narrow_stream_id = stream_data.get_sub(narrow_stream_name).stream_id;
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
                const narrow_matches_target_message = util.same_stream_and_topic(
                    target_message,
                    narrow_dict,
                );

                if (
                    !narrow_matches_target_message &&
                    (narrow_exists_in_edit_history || !page_params.realm_allow_edit_history)
                ) {
                    const adjusted_operators = adjusted_operators_if_moved(
                        raw_operators,
                        target_message,
                    );
                    if (adjusted_operators !== null) {
                        activate(adjusted_operators, {
                            ...opts,
                            // Update the URL fragment to reflect the redirect.
                            change_hash: true,
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
                    success(data) {
                        // After the message is fetched, we make the
                        // message locally available and then call
                        // narrow.activate recursively, setting a flag to
                        // indicate we've already done this.
                        message_helper.process_new_message(data.message);
                        activate(raw_operators, {
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
                        // narrow.activate recursively.
                        activate(raw_operators, {
                            fetched_target_message: true,
                            ...opts,
                        });
                    },
                });

                // The channel.get will call narrow.activate recursively
                // from a continuation unconditionally; the correct thing
                // to do here is return.
                return;
            }
        }

        // IMPORTANT: No code that modifies UI state should appear above
        // this point. This is important to prevent calling such functions
        // more than once in the event that we call narrow.activate
        // recursively.
        reset_ui_state();

        if (coming_from_recent_view) {
            recent_view_ui.hide();
        } else if (coming_from_inbox) {
            inbox_ui.hide();
        } else {
            // We must instead be switching from another message view.
            // Save the scroll position in that message list, so that
            // we can restore it if/when we later navigate back to that view.
            save_pre_narrow_offset_for_reload();
        }

        // most users aren't going to send a bunch of a out-of-narrow messages
        // and expect to visit a list of narrows, so let's get these out of the way.
        compose_banner.clear_message_sent_banners();

        // Open tooltips are only interesting for current narrow,
        // so hide them when activating a new one.
        $(".tooltip").hide();

        update_narrow_title(filter);

        blueslip.debug("Narrowed", {
            operators: operators.map((e) => e.operator),
            trigger: opts ? opts.trigger : undefined,
            previous_id: message_lists.current.selected_id(),
        });

        if (opts.then_select_id > 0) {
            // We override target_id in this case, since the user could be
            // having a near: narrow auto-reloaded.
            id_info.target_id = opts.then_select_id;
            if (opts.then_select_offset === undefined) {
                const $row = message_lists.current.get_row(opts.then_select_id);
                if ($row.length > 0) {
                    opts.then_select_offset = $row.get_offset_to_window().top;
                }
            }
        }

        if (!was_narrowed_already) {
            unread.set_messages_read_in_narrow(false);
        }

        // IMPORTANT!  At this point we are heavily committed to
        // populating the new narrow, so we update our narrow_state.
        // From here on down, any calls to the narrow_state API will
        // reflect the upcoming narrow.
        has_shown_message_list_view = true;
        narrow_state.set_current_filter(filter);

        const excludes_muted_topics = narrow_state.excludes_muted_topics();

        let msg_data = new MessageListData({
            filter: narrow_state.filter(),
            excludes_muted_topics,
        });

        // Populate the message list if we can apply our filter locally (i.e.
        // with no backend help) and we have the message we want to select.
        // Also update id_info accordingly.
        // original back.
        maybe_add_local_messages({
            id_info,
            msg_data,
        });

        if (!id_info.local_select_id) {
            // If we're not actually read to select an ID, we need to
            // trash the `MessageListData` object that we just constructed
            // and pass an empty one to MessageList, because the block of
            // messages in the MessageListData built inside
            // maybe_add_local_messages is likely not be contiguous with
            // the block we're about to request from the server instead.
            msg_data = new MessageListData({
                filter: narrow_state.filter(),
                excludes_muted_topics,
            });
        }

        const msg_list = new message_list.MessageList({
            data: msg_data,
            table_name: "zfilt",
        });

        // Show the new set of messages.  It is important to set message_lists.current to
        // the view right as it's being shown, because we rely on message_lists.current
        // being shown for deciding when to condense messages.
        $("body").addClass("narrowed_view");
        $("#zfilt").addClass("focused-message-list");
        $("#zhome").removeClass("focused-message-list");

        message_lists.set_current(msg_list);

        let then_select_offset;
        if (id_info.target_id === id_info.final_select_id) {
            then_select_offset = opts.then_select_offset;
        }

        const select_immediately = id_info.local_select_id !== undefined;

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
                cont() {
                    if (!select_immediately) {
                        update_selection({
                            id_info,
                            select_offset: then_select_offset,
                            msg_list: message_lists.current,
                        });
                    }
                },
                msg_list,
            });
        }

        if (select_immediately) {
            update_selection({
                id_info,
                select_offset: then_select_offset,
                msg_list: message_lists.current,
            });
        }

        // Put the narrow operators in the URL fragment.
        // Disabled when the URL fragment was the source
        // of this narrow.
        if (opts.change_hash) {
            hashchange.save_narrow(operators);
        }

        if (filter.contains_only_private_messages()) {
            compose_closed_ui.update_buttons_for_private();
        } else {
            compose_closed_ui.update_buttons_for_stream();
        }
        compose_closed_ui.update_reply_recipient_label();

        compose_actions.on_narrow(opts);

        const current_filter = narrow_state.filter();

        left_sidebar_navigation_area.handle_narrow_activated(current_filter);
        pm_list.handle_narrow_activated(current_filter);
        stream_list.handle_narrow_activated(current_filter);
        typing_events.render_notifications_for_narrow();
        message_view_header.render_title_area();
        unread_ui.update_unread_banner();

        // It is important to call this after other important updates
        // like narrow filter and compose recipients happen.
        handle_middle_pane_transition();

        const post_span = span.startChild({
            op: "function",
            description: "post-narrow busy time",
        });
        do_close_span = false;
        span.setStatus("ok");
        setTimeout(() => {
            resize.resize_stream_filters_container();
            post_span.finish();
            span.finish();
        }, 0);
    } catch {
        span.setStatus("unknown_error");
    } finally {
        if (do_close_span) {
            span.finish();
        }
        Sentry.getCurrentHub().popScope();
    }
}

function min_defined(a, b) {
    if (a === undefined) {
        return b;
    }
    if (b === undefined) {
        return a;
    }
    return a < b ? a : b;
}

function load_local_messages(msg_data) {
    // This little helper loads messages into our narrow message
    // data and returns true unless it's visibly empty.  We use this for
    // cases when our local cache (all_messages_data) has at least
    // one message the user will expect to see in the new narrow.

    const in_msgs = all_messages_data.all_messages();
    msg_data.add_messages(in_msgs);

    return !msg_data.visibly_empty();
}

export function maybe_add_local_messages(opts) {
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
    const unread_info = narrow_state.get_first_unread_info();

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
    if (!id_info.target_id && !narrow_state.filter().allow_use_first_unread_when_narrowing()) {
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

    // We can now assume narrow_state.filter().can_apply_locally(),
    // because !can_apply_locally => cannot_compute

    if (
        unread_info.flavor === "found" &&
        narrow_state.filter().allow_use_first_unread_when_narrowing()
    ) {
        // We have at least one unread message in this narrow, and the
        // narrow is one where we use the first unread message in
        // narrowing positioning decisions.  So either we aim for the
        // first unread message, or the target_id (if any), whichever
        // is earlier.  See #2091 for a detailed explanation of why we
        // need to look at unread here.
        id_info.final_select_id = min_defined(id_info.target_id, unread_info.msg_id);

        if (!load_local_messages(msg_data)) {
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

        if (!all_messages_data.fetch_status.has_found_newest()) {
            // If all_messages_data is not caught up, then we cannot
            // populate the latest messages for the target narrow
            // correctly from there, so we must go to the server.
            return;
        }
        if (!load_local_messages(msg_data)) {
            return;
        }
        // Otherwise, we have matching messages, and all_messages_data
        // is caught up, so the last message in our now-populated
        // msg_data object must be the last message matching the
        // narrow the server could give us, so we can render locally.
        // and use local latest message id instead of max_int if set earlier.
        const last_msg = msg_data.last();
        id_info.final_select_id = last_msg.id;
        id_info.local_select_id = id_info.final_select_id;
        return;
    }

    // We have a target_id and no unread messages complicating things,
    // so we definitely want to land on the target_id message.
    id_info.final_select_id = id_info.target_id;

    // TODO: We could improve on this next condition by considering
    // cases where
    // `all_messages_data.fetch_status.has_found_oldest()`; which
    // would come up with e.g. `near: 0` in a small organization.
    //
    // And similarly for `near: max_int` with has_found_newest.
    if (
        all_messages_data.visibly_empty() ||
        id_info.target_id < all_messages_data.first().id ||
        id_info.target_id > all_messages_data.last().id
    ) {
        // If the target message is outside the range that we had
        // available for local population, we must go to the server.
        return;
    }
    if (!load_local_messages(msg_data)) {
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

export function update_selection(opts) {
    if (message_lists.current !== opts.msg_list) {
        // If we navigated away from a view while we were fetching
        // messages for it, don't attempt to move the currently
        // selected message.
        return;
    }

    if (message_lists.current.visibly_empty()) {
        // There's nothing to select if there are no messages.
        return;
    }

    const id_info = opts.id_info;
    const select_offset = opts.select_offset;

    let msg_id = id_info.final_select_id;
    if (msg_id === undefined) {
        msg_id = message_lists.current.first_unread_message_id();
    }

    const preserve_pre_narrowing_screen_position =
        message_lists.current.get(msg_id) !== undefined && select_offset !== undefined;

    const then_scroll = !preserve_pre_narrowing_screen_position;

    message_lists.current.select_id(msg_id, {
        then_scroll,
        use_closest: true,
        force_rerender: true,
    });

    if (preserve_pre_narrowing_screen_position) {
        // Scroll so that the selected message is in the same
        // position in the viewport as it was prior to
        // narrowing
        message_lists.current.view.set_message_offset(select_offset);
    }
    unread_ops.process_visible();
    narrow_history.save_narrow_state_and_flush();
}

export function activate_stream_for_cycle_hotkey(stream_name) {
    // This is the common code for A/D hotkeys.
    const filter_expr = [{operator: "stream", operand: stream_name}];
    activate(filter_expr, {});
}

export function stream_cycle_backward() {
    const curr_stream = narrow_state.stream_name();

    if (!curr_stream) {
        return;
    }

    const stream_name = topic_generator.get_prev_stream(curr_stream);

    if (!stream_name) {
        return;
    }

    activate_stream_for_cycle_hotkey(stream_name);
}

export function stream_cycle_forward() {
    const curr_stream = narrow_state.stream_name();

    if (!curr_stream) {
        return;
    }

    const stream_name = topic_generator.get_next_stream(curr_stream);

    if (!stream_name) {
        return;
    }

    activate_stream_for_cycle_hotkey(stream_name);
}

export function narrow_to_next_topic(opts = {}) {
    const curr_info = {
        stream: narrow_state.stream_name(),
        topic: narrow_state.topic(),
    };

    const next_narrow = topic_generator.get_next_topic(curr_info.stream, curr_info.topic);

    if (!next_narrow) {
        return;
    }

    const filter_expr = [
        {operator: "stream", operand: next_narrow.stream},
        {operator: "topic", operand: next_narrow.topic},
    ];

    activate(filter_expr, opts);
}

export function narrow_to_next_pm_string(opts = {}) {
    const current_direct_message = narrow_state.pm_ids_string();

    const next_direct_message = topic_generator.get_next_unread_pm_string(current_direct_message);

    if (!next_direct_message) {
        return;
    }

    // Hopefully someday we can narrow by user_ids_string instead of
    // mapping back to emails.
    const direct_message = people.user_ids_string_to_emails_string(next_direct_message);

    const filter_expr = [{operator: "dm", operand: direct_message}];

    // force_close parameter is true to not auto open compose_box
    const updated_opts = {
        ...opts,
        force_close: true,
    };

    activate(filter_expr, updated_opts);
}

// Activate narrowing with a single operator.
// This is just for syntactic convenience.
export function by(operator, operand, opts) {
    activate([{operator, operand}], opts);
}

export function by_topic(target_id, opts) {
    // don't use message_lists.current as it won't work for muted messages or for out-of-narrow links
    const original = message_store.get(target_id);
    if (original.type !== "stream") {
        // Only stream messages have topics, but the
        // user wants us to narrow in some way.
        by_recipient(target_id, opts);
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

    const stream_name = stream_data.get_stream_name_from_id(original.stream_id);
    const search_terms = [
        {operator: "stream", operand: stream_name},
        {operator: "topic", operand: original.topic},
    ];
    opts = {then_select_id: target_id, ...opts};
    activate(search_terms, opts);
}

export function by_recipient(target_id, opts) {
    opts = {then_select_id: target_id, ...opts};
    // don't use message_lists.current as it won't work for muted messages or for out-of-narrow links
    const message = message_store.get(target_id);

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
            by("dm", message.reply_to, opts);
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
            by("stream", stream_data.get_stream_name_from_id(message.stream_id), opts);
            break;
    }
}

// Called by the narrow_to_compose_target hotkey.
export function to_compose_target() {
    if (!compose_state.composing()) {
        return;
    }

    const opts = {
        trigger: "narrow_to_compose_target",
    };

    if (compose_state.get_message_type() === "stream") {
        const stream_id = compose_state.stream_id();
        if (!stream_id) {
            return;
        }
        const stream_name = stream_data.get_sub_by_id(stream_id).name;
        // If we are composing to a new topic, we narrow to the stream but
        // grey-out the message view instead of narrowing to an empty view.
        const operators = [{operator: "stream", operand: stream_name}];
        const topic = compose_state.topic();
        if (topic !== "") {
            operators.push({operator: "topic", operand: topic});
        }
        activate(operators, opts);
        return;
    }

    if (compose_state.get_message_type() === "private") {
        const recipient_string = compose_state.private_message_recipient();
        const emails = util.extract_pm_recipients(recipient_string);
        const invalid = emails.filter((email) => !people.is_valid_email_for_compose(email));
        // If there are no recipients or any recipient is
        // invalid, narrow to all direct messages.
        if (emails.length === 0 || invalid.length > 0) {
            by("is", "dm", opts);
            return;
        }
        by("dm", util.normalize_recipients(recipient_string), opts);
    }
}

function handle_post_narrow_deactivate_processes() {
    compose_fade.update_message_list();

    left_sidebar_navigation_area.handle_narrow_deactivated();
    pm_list.handle_narrow_deactivated();
    stream_list.handle_narrow_deactivated();
    compose_closed_ui.update_buttons_for_stream();
    message_edit.handle_narrow_deactivated();
    widgetize.set_widgets_for_list();
    typing_events.render_notifications_for_narrow();
    message_view_header.render_title_area();
    update_narrow_title(narrow_state.filter());
    message_feed_top_notices.update_top_of_narrow_notices(message_lists.home);
}

export function deactivate(coming_from_all_messages = true, is_actively_scrolling = false) {
    // NOTE: Never call this function independently,
    // always use browser_history.go_to_location("#all_messages") to
    // activate All message narrow.
    /*
      Switches message_lists.current from narrowed_msg_list to
      message_lists.home ("All messages"), ending the current narrow.  This
      is a very fast operation, because we keep message_lists.home's data
      cached and updated in the DOM at all times, making it suitable
      for rapid access via keyboard shortcuts.

      Long-term, we will likely want to make `message_lists.home` not
      special in any way, and instead just have a generic
      message_list_data structure caching system that happens to have
      message_lists.home in it.
     */
    search.clear_search_form();
    // Both All messages and Recent Conversations have `undefined` filter.
    // Return if already in the All message narrow.
    if (narrow_state.filter() === undefined && coming_from_all_messages) {
        return;
    }
    blueslip.debug("Unnarrowed");

    if (is_actively_scrolling) {
        // There is no way to intercept in-flight scroll events, and they will
        // cause you to end up in the wrong place if you are actively scrolling
        // on an unnarrow. Wait a bit and try again once the scrolling is over.
        setTimeout(deactivate, 50);
        return;
    }

    const existing_span = Sentry.getCurrentHub().getScope().getSpan();
    const span_data = {op: "function", description: "unnarrow"};
    let span;
    if (!existing_span) {
        span = Sentry.startTransaction({...span_data, name: "unnarrow"});
    } else {
        span = existing_span.startChild(span_data);
    }
    let do_close_span = true;
    try {
        const scope = Sentry.getCurrentHub().pushScope();
        scope.setSpan(span);

        if (!compose_state.has_message_content() && !compose_state.is_recipient_edited_manually()) {
            compose_actions.cancel();
        }

        narrow_state.reset_current_filter();
        has_shown_message_list_view = true;

        $("body").removeClass("narrowed_view");
        $("#zfilt").removeClass("focused-message-list");
        $("#zhome").addClass("focused-message-list");
        message_lists.set_current(message_lists.home);
        message_lists.current.resume_reading();
        condense.condense_and_collapse($("#zhome div.message_row"));

        reset_ui_state();
        handle_middle_pane_transition();
        hashchange.save_narrow();

        if (message_lists.current.selected_id() !== -1) {
            const preserve_pre_narrowing_screen_position =
                message_lists.current.selected_row().length > 0 &&
                message_lists.current.pre_narrow_offset !== undefined;
            let message_id_to_select;
            const select_opts = {
                then_scroll: true,
                use_closest: true,
                empty_ok: true,
            };

            // We fall back to the closest selected id, if the user has removed a
            // stream from the home view since leaving it the old selected id might
            // no longer be there
            // Additionally, we pass empty_ok as the user may have removed **all** streams
            // from their home view
            if (unread.messages_read_in_narrow) {
                // We read some unread messages in a narrow. Instead of going back to
                // where we were before the narrow, go to our first unread message (or
                // the bottom of the feed, if there are no unread messages).
                message_id_to_select = message_lists.current.first_unread_message_id();
            } else {
                // We narrowed, but only backwards in time (ie no unread were read). Try
                // to go back to exactly where we were before narrowing.
                if (preserve_pre_narrowing_screen_position) {
                    // We scroll the user back to exactly the offset from the selected
                    // message that they were at the time that they narrowed.
                    // TODO: Make this correctly handle the case of resizing while narrowed.
                    select_opts.target_scroll_offset = message_lists.current.pre_narrow_offset;
                }
                message_id_to_select = message_lists.current.selected_id();
            }
            message_lists.current.select_id(message_id_to_select, select_opts);
        }

        handle_post_narrow_deactivate_processes();

        const post_span = span.startChild({
            op: "function",
            description: "post-unnarrow busy time",
        });
        do_close_span = false;
        span.setStatus("ok");
        setTimeout(() => {
            resize.resize_stream_filters_container();
            post_span.finish();
            span.finish();
        });
    } catch (error) {
        span.setStatus("unknown_error");
        throw error;
    } finally {
        if (do_close_span) {
            span.finish();
        }
        Sentry.getCurrentHub().popScope();
    }
}
