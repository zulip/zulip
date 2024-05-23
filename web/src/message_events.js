import $ from "jquery";
import assert from "minimalistic-assert";

import * as alert_words from "./alert_words";
import {all_messages_data} from "./all_messages_data";
import * as blueslip from "./blueslip";
import * as channel from "./channel";
import * as compose_fade from "./compose_fade";
import * as compose_notifications from "./compose_notifications";
import * as compose_state from "./compose_state";
import * as compose_validate from "./compose_validate";
import * as drafts from "./drafts";
import * as huddle_data from "./huddle_data";
import * as message_edit from "./message_edit";
import * as message_edit_history from "./message_edit_history";
import * as message_helper from "./message_helper";
import * as message_lists from "./message_lists";
import * as message_notifications from "./message_notifications";
import * as message_store from "./message_store";
import * as message_util from "./message_util";
import * as narrow from "./narrow";
import * as narrow_state from "./narrow_state";
import * as pm_list from "./pm_list";
import * as recent_senders from "./recent_senders";
import * as recent_view_ui from "./recent_view_ui";
import * as recent_view_util from "./recent_view_util";
import * as starred_messages from "./starred_messages";
import * as starred_messages_ui from "./starred_messages_ui";
import {realm} from "./state_data";
import * as stream_list from "./stream_list";
import * as stream_topic_history from "./stream_topic_history";
import * as sub_store from "./sub_store";
import * as unread from "./unread";
import * as unread_ops from "./unread_ops";
import * as unread_ui from "./unread_ui";
import * as util from "./util";

function maybe_add_narrowed_messages(messages, msg_list, callback, attempt = 1) {
    const ids = [];

    for (const elem of messages) {
        ids.push(elem.id);
    }

    channel.get({
        url: "/json/messages/matches_narrow",
        data: {
            msg_ids: JSON.stringify(ids),
            narrow: JSON.stringify(narrow_state.public_search_terms()),
        },
        timeout: 5000,
        success(data) {
            if (!narrow_state.is_message_feed_visible() || msg_list !== message_lists.current) {
                // We unnarrowed or moved to Recent Conversations in the meantime.
                return;
            }

            let new_messages = [];
            const elsewhere_messages = [];

            for (const elem of messages) {
                if (Object.hasOwn(data.messages, elem.id)) {
                    util.set_match_data(elem, data.messages[elem.id]);
                    new_messages.push(elem);
                } else {
                    elsewhere_messages.push(elem);
                }
            }

            // This second call to process_new_message in the
            // insert_new_messages code path is designed to replace
            // our slightly stale message object with the latest copy
            // from the message_store. This helps in very rare race
            // conditions, where e.g. the current user's name was
            // edited in between when they sent the message and when
            // we hear back from the server and can echo the new
            // message.
            new_messages = new_messages.map((message) =>
                message_helper.process_new_message(message),
            );

            callback(new_messages, msg_list);
            unread_ops.process_visible();
            compose_notifications.notify_messages_outside_current_search(elsewhere_messages);
        },
        error(xhr) {
            if (!narrow_state.is_message_feed_visible() || msg_list !== message_lists.current) {
                return;
            }
            if (xhr.status === 400) {
                // This narrow was invalid -- don't retry it, and don't display the message.
                return;
            }
            if (attempt >= 5) {
                // Too many retries -- bail out.  However, this means the `messages` are potentially
                // missing from the search results view.  Since this is a very unlikely circumstance
                // (Tornado is up, Django is down for 5 retries, user is in a search view that it
                // cannot apply itself) and the failure mode is not bad (it will simply fail to
                // include live updates of new matching messages), just log an error.
                blueslip.error(
                    "Failed to determine if new message matches current narrow, after 5 tries",
                );
                return;
            }
            // Backoff on retries, with full jitter: up to 2s, 4s, 8s, 16s, 32s
            const delay = Math.random() * 2 ** attempt * 2000;
            setTimeout(() => {
                if (msg_list === message_lists.current) {
                    // Don't actually try again if we un-narrowed
                    // while waiting
                    maybe_add_narrowed_messages(messages, msg_list, callback, attempt + 1);
                }
            }, delay);
        },
    });
}

export function insert_new_messages(messages, sent_by_this_client) {
    messages = messages.map((message) => message_helper.process_new_message(message));

    const any_untracked_unread_messages = unread.process_loaded_messages(messages, false);
    huddle_data.process_loaded_messages(messages);

    // all_messages_data is the data that we use to populate
    // other lists, so we always update this
    message_util.add_new_messages_data(messages, all_messages_data);

    let need_user_to_scroll = false;
    for (const list of message_lists.all_rendered_message_lists()) {
        if (!list.data.filter.can_apply_locally()) {
            // If we cannot locally calculate whether the new messages
            // match the message list, we ask the server whether the
            // new messages match the narrow, and use that to
            // determine which new messages to add to the current
            // message list (or display a notification).
            maybe_add_narrowed_messages(messages, list, message_util.add_new_messages);
            continue;
        }

        // Update the message list's rendering for the newly arrived messages.
        const render_info = message_util.add_new_messages(messages, list);

        // The render_info.need_user_to_scroll calculation, which
        // looks at message feed scroll positions to see whether the
        // newly arrived message will be visible, is only valid if
        // this message list is the currently visible message list.
        const is_currently_visible =
            narrow_state.is_message_feed_visible() && list === message_lists.current;
        if (is_currently_visible && render_info && render_info.need_user_to_scroll) {
            need_user_to_scroll = true;
        }
    }

    // sent_by_this_client will be true if ANY of the messages
    // were sent by this client; notifications.notify_local_mixes
    // will filter out any not sent by us.
    if (sent_by_this_client) {
        compose_notifications.notify_local_mixes(messages, need_user_to_scroll);
    }

    if (any_untracked_unread_messages) {
        unread_ui.update_unread_counts();
    }

    unread_ops.process_visible();
    message_notifications.received_messages(messages);
    stream_list.update_streams_sidebar();
    pm_list.update_private_messages();
}

export function update_messages(events) {
    const messages_to_rerender = [];
    let any_topic_edited = false;
    let changed_narrow = false;
    let changed_compose = false;
    let any_message_content_edited = false;
    let any_stream_changed = false;

    for (const event of events) {
        const anchor_message = message_store.get(event.message_id);
        if (anchor_message !== undefined) {
            // Logic for updating the specific edited message only
            // needs to run if we had a local copy of the message.

            delete anchor_message.local_edit_timestamp;

            messages_to_rerender.push(anchor_message);

            message_store.update_booleans(anchor_message, event.flags);

            if (event.rendered_content !== undefined) {
                anchor_message.content = event.rendered_content;
            }

            if (event.is_me_message !== undefined) {
                anchor_message.is_me_message = event.is_me_message;
            }

            // mark the current message edit attempt as complete.
            message_edit.end_message_edit(event.message_id);

            // Save the content edit to the front end anchor_message.edit_history
            // before topic edits to ensure that combined topic / content
            // edits have edit_history logged for both before any
            // potential narrowing as part of the topic edit loop.
            if (event.orig_content !== undefined) {
                if (realm.realm_allow_edit_history) {
                    // Note that we do this for topic edits separately, below.
                    // If an event changed both content and topic, we'll generate
                    // two client-side events, which is probably good for display.
                    const edit_history_entry = {
                        user_id: event.user_id,
                        prev_content: event.orig_content,
                        prev_rendered_content: event.orig_rendered_content,
                        prev_rendered_content_version: event.prev_rendered_content_version,
                        timestamp: event.edit_timestamp,
                    };
                    // Add message's edit_history in message dict
                    // For messages that are edited, edit_history needs to
                    // be added to message in frontend.
                    if (anchor_message.edit_history === undefined) {
                        anchor_message.edit_history = [];
                    }
                    anchor_message.edit_history = [
                        edit_history_entry,
                        ...anchor_message.edit_history,
                    ];
                }
                any_message_content_edited = true;

                // Update raw_content, so that editing a few times in a row is fast.
                anchor_message.raw_content = event.content;
            }

            if (unread.update_message_for_mention(anchor_message, any_message_content_edited)) {
                const topic_key = recent_view_util.get_topic_key(
                    anchor_message.stream_id,
                    anchor_message.topic,
                );
                recent_view_ui.inplace_rerender(topic_key);
            }
        }

        // new_topic will be undefined if the topic is unchanged.
        const new_topic = util.get_edit_event_topic(event);
        // new_stream_id will be undefined if the stream is unchanged.
        const new_stream_id = event.new_stream_id;
        // old_stream_id will be present and valid for all stream messages.
        const old_stream_id = event.stream_id;
        // old_stream will be undefined if the message was moved from
        // a stream that the current user doesn't have access to.
        const old_stream = sub_store.get(event.stream_id);

        // A topic or stream edit may affect multiple messages, listed in
        // event.message_ids. event.message_id is still the first message
        // where the user initiated the edit.
        const topic_edited = new_topic !== undefined;
        const stream_changed = new_stream_id !== undefined;
        const stream_archived = old_stream === undefined;
        if (stream_changed) {
            any_stream_changed = true;
        }
        if (topic_edited) {
            any_topic_edited = true;
        }

        if (topic_edited || stream_changed) {
            const going_forward_change = ["change_later", "change_all"].includes(
                event.propagate_mode,
            );

            const compose_stream_id = compose_state.stream_id();
            const orig_topic = util.get_edit_event_orig_topic(event);

            const current_filter = narrow_state.filter();
            const current_selected_id = message_lists.current?.selected_id();
            const selection_changed_topic =
                message_lists.current !== undefined &&
                event.message_ids.includes(current_selected_id);
            const event_messages = [];
            for (const message_id of event.message_ids) {
                // We don't need to concern ourselves updating data structures
                // for messages we don't have stored locally.
                const message = message_store.get(message_id);
                if (message !== undefined) {
                    event_messages.push(message);
                }
            }
            // The event.message_ids received from the server are not in sorted order.
            event_messages.sort((a, b) => a.id - b.id);

            if (
                going_forward_change &&
                !stream_archived &&
                compose_stream_id &&
                old_stream.stream_id === compose_stream_id &&
                orig_topic === compose_state.topic()
            ) {
                changed_compose = true;
                compose_state.topic(new_topic);
                compose_validate.warn_if_topic_resolved(true);
                compose_fade.set_focused_recipient("stream");
            }

            if (going_forward_change) {
                drafts.rename_stream_recipient(old_stream_id, orig_topic, new_stream_id, new_topic);
            }

            for (const moved_message of event_messages) {
                if (realm.realm_allow_edit_history) {
                    /* Simulate the format of server-generated edit
                     * history events. This logic ensures that all
                     * messages that were moved are displayed as such
                     * without a browser reload. */
                    const edit_history_entry = {
                        user_id: event.user_id,
                        timestamp: event.edit_timestamp,
                    };
                    if (stream_changed) {
                        edit_history_entry.stream = new_stream_id;
                        edit_history_entry.prev_stream = old_stream_id;
                    }
                    if (topic_edited) {
                        edit_history_entry.topic = new_topic;
                        edit_history_entry.prev_topic = orig_topic;
                    }
                    if (moved_message.edit_history === undefined) {
                        moved_message.edit_history = [];
                    }
                    moved_message.edit_history = [
                        edit_history_entry,
                        ...moved_message.edit_history,
                    ];
                }
                moved_message.last_edit_timestamp = event.edit_timestamp;

                // Remove the Recent Conversations entry for the old topics;
                // must be called before we call set_message_topic.
                //
                // TODO: Use a single bulk request to do this removal.
                // Note that we need to be careful to only remove IDs
                // that were present in stream_topic_history data.
                // This may not be possible to do correctly without extra
                // complexity; the present loop assumes stream_topic_history has
                // only messages in message_store, but that's been false
                // since we added the server_history feature.
                stream_topic_history.remove_messages({
                    stream_id: moved_message.stream_id,
                    topic_name: moved_message.topic,
                    num_messages: 1,
                    max_removed_msg_id: moved_message.id,
                });

                // Update the unread counts; again, this must be called
                // before we modify the topic field on the message.
                unread.update_unread_topics(moved_message, event);

                // Now edit the attributes of our message object.
                if (topic_edited) {
                    moved_message.topic = new_topic;
                    moved_message.topic_links = event.topic_links;
                }
                if (stream_changed) {
                    const new_stream_name = sub_store.get(new_stream_id).name;
                    moved_message.stream_id = new_stream_id;
                    moved_message.display_recipient = new_stream_name;
                }

                // Add the Recent Conversations entry for the new stream/topics.
                stream_topic_history.add_message({
                    stream_id: moved_message.stream_id,
                    topic_name: moved_message.topic,
                    message_id: moved_message.id,
                });
            }

            const old_stream_name = stream_archived ? undefined : old_stream.name;
            if (
                going_forward_change &&
                // This logic is a bit awkward.  What we're trying to
                // accomplish is two things:
                //
                // * If we're currently narrowed to a topic that was just moved,
                //   renarrow to the new location.
                // * We determine whether enough of the topic was moved to justify
                //   renarrowing by checking if the currently selected message is moved.
                //
                // Corner cases around only moving some messages in a topic
                // need to be thought about carefully when making changes.
                //
                // Code further down takes care of the actual rerendering of
                // messages within a narrow.
                selection_changed_topic &&
                current_filter &&
                current_filter.has_topic(old_stream_name, orig_topic)
            ) {
                let new_filter = current_filter;
                if (new_filter && stream_changed) {
                    // TODO: This logic doesn't handle the
                    // case where we're a guest user and the
                    // message moves to a stream we cannot
                    // access, which would cause the
                    // stream_data lookup here to fail.
                    //
                    // The fix is likely somewhat involved, so punting for now.
                    const new_stream_name = sub_store.get(new_stream_id).name;
                    new_filter = new_filter.filter_with_new_params({
                        operator: "channel",
                        operand: new_stream_name,
                    });
                    changed_narrow = true;
                }

                if (new_filter && topic_edited) {
                    new_filter = new_filter.filter_with_new_params({
                        operator: "topic",
                        operand: new_topic,
                    });
                    changed_narrow = true;
                }
                // NOTE: We should always be changing narrows after we finish
                //       updating the local data and UI. This avoids conflict
                //       with data fetched from the server (which is already updated)
                //       when we move to new narrow and what data is locally available.
                if (changed_narrow) {
                    const terms = new_filter.terms();
                    const opts = {
                        trigger: "stream/topic change",
                        then_select_id: current_selected_id,
                    };
                    narrow.activate(terms, opts);
                }
            }

            // Ensure messages that are no longer part of this
            // narrow are deleted and messages that are now part
            // of this narrow are added to the message_list.
            //
            // Even if we end up renarrowing, the message_list_data
            // part of this is important for non-rendering message
            // lists, so we do this unconditionally.  Most correctly,
            // this should be a loop over all valid message_list_data
            // objects, without the rerender (which will naturally
            // happen in the following code).
            if (!changed_narrow && current_filter) {
                let message_ids_to_remove = [];
                if (current_filter.can_apply_locally()) {
                    const predicate = current_filter.predicate();
                    message_ids_to_remove = event_messages.filter((msg) => !predicate(msg));
                    message_ids_to_remove = message_ids_to_remove.map((msg) => msg.id);
                    // We filter out messages that do not belong to the message
                    // list and then pass these to the remove messages codepath.
                    // While we can pass all our messages to the add messages
                    // codepath as the filtering is done within the method.
                    assert(message_lists.current !== undefined);
                    message_lists.current.remove_and_rerender(message_ids_to_remove);
                    message_lists.current.add_messages(event_messages);
                } else if (message_lists.current !== undefined) {
                    // Remove existing message that were updated, since
                    // they may not be a part of the filter now. Also,
                    // this will help us rerender them via
                    // maybe_add_narrowed_messages, if they were
                    // simply updated.
                    const updated_messages = event_messages.filter(
                        (msg) => message_lists.current.data.get(msg.id) !== undefined,
                    );
                    message_lists.current.remove_and_rerender(
                        updated_messages.map((msg) => msg.id),
                    );
                    // For filters that cannot be processed locally, ask server.
                    maybe_add_narrowed_messages(
                        event_messages,
                        message_lists.current,
                        message_util.add_messages,
                    );
                }
            }
        }

        if (anchor_message !== undefined) {
            // Mark the message as edited for the UI. The rendering_only
            // flag is used to indicated update_message events that are
            // triggered by server latency optimizations, not user
            // interactions; these should not generate edit history updates.
            if (!event.rendering_only) {
                anchor_message.last_edit_timestamp = event.edit_timestamp;
            }

            message_notifications.received_messages([anchor_message]);
            alert_words.process_message(anchor_message);
        }

        if (topic_edited || stream_changed) {
            // if topic is changed
            let pre_edit_topic = util.get_edit_event_orig_topic(event);
            let post_edit_topic = new_topic;

            if (!topic_edited) {
                if (anchor_message !== undefined) {
                    pre_edit_topic = anchor_message.topic;
                }
                post_edit_topic = pre_edit_topic;
            }

            // new_stream_id is undefined if this is only a topic edit.
            const post_edit_stream_id = new_stream_id || old_stream_id;

            const args = [old_stream_id, pre_edit_topic, post_edit_topic, post_edit_stream_id];
            recent_senders.process_topic_edit({
                message_ids: event.message_ids,
                old_stream_id,
                old_topic: pre_edit_topic,
                new_stream_id: post_edit_stream_id,
                new_topic: post_edit_topic,
            });
            unread.clear_and_populate_unread_mention_topics();
            recent_view_ui.process_topic_edit(...args);
        }

        // Rerender "Message edit history" if it was open to the edited message.
        if (
            anchor_message !== undefined &&
            $("#message-edit-history").parents(".micromodal").hasClass("modal--open") &&
            anchor_message.id === Number.parseInt($("#message-history").attr("data-message-id"), 10)
        ) {
            message_edit_history.fetch_and_render_message_history(anchor_message);
        }
    }

    // If a topic was edited, we re-render the whole view to get any
    // propagated edits to be updated (since the topic edits can have
    // changed the correct grouping of messages).
    if (any_topic_edited || any_stream_changed) {
        // However, we don't need to rerender message_list if
        // we just changed the narrow earlier in this function.
        //
        // TODO: We can potentially optimize this logic to avoid
        // calling `update_muting_and_rerender` if the muted
        // messages would not match the view before or after this
        // edit.  Doing so could save significant work, since most
        // topic edits will not match the current topic narrow in
        // large organizations.

        for (const list of message_lists.all_rendered_message_lists()) {
            if (changed_narrow && list === message_lists.current) {
                // Avoid updating current message list if user switched to a different narrow and
                // we don't want to preserver the rendered state for the current one.
                continue;
            }

            list.view.rerender_messages(messages_to_rerender, any_message_content_edited);
        }
    } else {
        // If the content of the message was edited, we do a special animation.
        //
        // BUG: This triggers the "message edited" animation for every
        // message that was edited if any one of them had its content
        // edited. We should replace any_message_content_edited with
        // passing two sets to rerender_messages; the set of all that
        // are changed, and the set with content changes.
        for (const list of message_lists.all_rendered_message_lists()) {
            list.view.rerender_messages(messages_to_rerender, any_message_content_edited);
        }
    }

    if (changed_compose) {
        // We need to do this after we rerender the message list, to
        // produce correct results.
        compose_fade.update_message_list();
    }

    unread_ui.update_unread_counts();
    stream_list.update_streams_sidebar();
    pm_list.update_private_messages();
}

export function remove_messages(message_ids) {
    all_messages_data.remove(message_ids);
    for (const list of message_lists.all_rendered_message_lists()) {
        list.remove_and_rerender(message_ids);
    }
    recent_senders.update_topics_of_deleted_message_ids(message_ids);
    recent_view_ui.update_topics_of_deleted_message_ids(message_ids);
    starred_messages.remove(message_ids);
    starred_messages_ui.rerender_ui();
}
