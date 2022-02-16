import $ from "jquery";

import * as alert_words from "./alert_words";
import {all_messages_data} from "./all_messages_data";
import * as channel from "./channel";
import * as compose_fade from "./compose_fade";
import * as compose_state from "./compose_state";
import * as compose_validate from "./compose_validate";
import * as condense from "./condense";
import * as huddle_data from "./huddle_data";
import * as message_edit from "./message_edit";
import * as message_edit_history from "./message_edit_history";
import * as message_helper from "./message_helper";
import * as message_list from "./message_list";
import * as message_lists from "./message_lists";
import * as message_store from "./message_store";
import * as message_util from "./message_util";
import * as narrow from "./narrow";
import * as narrow_state from "./narrow_state";
import * as notifications from "./notifications";
import {page_params} from "./page_params";
import * as pm_list from "./pm_list";
import * as recent_senders from "./recent_senders";
import * as recent_topics_ui from "./recent_topics_ui";
import * as resize from "./resize";
import * as stream_list from "./stream_list";
import * as stream_topic_history from "./stream_topic_history";
import * as sub_store from "./sub_store";
import * as unread from "./unread";
import * as unread_ops from "./unread_ops";
import * as unread_ui from "./unread_ui";
import * as util from "./util";

function maybe_add_narrowed_messages(messages, msg_list, callback) {
    const ids = [];

    for (const elem of messages) {
        ids.push(elem.id);
    }

    channel.get({
        url: "/json/messages/matches_narrow",
        data: {
            msg_ids: JSON.stringify(ids),
            narrow: JSON.stringify(narrow_state.public_operators()),
        },
        timeout: 5000,
        success(data) {
            if (msg_list !== message_lists.current) {
                // We unnarrowed in the mean time
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
            // insert_new_messages code path helps in very rare race
            // conditions, where e.g. the current user's name was
            // edited in between when they sent the message and when
            // we hear back from the server and can echo the new
            // message.  Arguably, it's counterproductive complexity.
            new_messages = new_messages.map((message) =>
                message_helper.process_new_message(message),
            );

            callback(new_messages, msg_list);
            unread_ops.process_visible();
            notifications.notify_messages_outside_current_search(elsewhere_messages);
        },
        error() {
            // We might want to be more clever here
            setTimeout(() => {
                if (msg_list === message_lists.current) {
                    // Don't actually try again if we unnarrowed
                    // while waiting
                    maybe_add_narrowed_messages(messages, msg_list, callback);
                }
            }, 5000);
        },
    });
}

export function insert_new_messages(messages, sent_by_this_client) {
    messages = messages.map((message) => message_helper.process_new_message(message));

    unread.process_loaded_messages(messages);
    huddle_data.process_loaded_messages(messages);

    // all_messages_data is the data that we use to populate
    // other lists, so we always update this
    message_util.add_new_messages_data(messages, all_messages_data);

    let render_info;

    if (narrow_state.active()) {
        // We do this NOW even though the home view is not active,
        // because we want the home view to load fast later.
        message_util.add_new_messages(messages, message_lists.home);

        if (narrow_state.filter().can_apply_locally()) {
            render_info = message_util.add_new_messages(messages, message_list.narrowed);
        } else {
            // if we cannot apply locally, we have to wait for this callback to happen to notify
            maybe_add_narrowed_messages(
                messages,
                message_list.narrowed,
                message_util.add_new_messages,
            );
        }
    } else {
        // we're in the home view, so update its list
        render_info = message_util.add_new_messages(messages, message_lists.home);
    }

    if (sent_by_this_client) {
        const need_user_to_scroll = render_info && render_info.need_user_to_scroll;
        // sent_by_this_client will be true if ANY of the messages
        // were sent by this client; notifications.notify_local_mixes
        // will filter out any not sent by us.
        notifications.notify_local_mixes(messages, need_user_to_scroll);
    }

    unread_ui.update_unread_counts();
    resize.resize_page_components();

    unread_ops.process_visible();
    notifications.received_messages(messages);
    stream_list.update_streams_sidebar();
    pm_list.update_private_messages();
    recent_topics_ui.process_messages(messages);
}

export function update_messages(events) {
    const msgs_to_rerender = [];
    let topic_edited = false;
    let changed_narrow = false;
    let changed_compose = false;
    let message_content_edited = false;
    let stream_changed = false;
    let stream_archived = false;

    for (const event of events) {
        const msg = message_store.get(event.message_id);
        if (msg === undefined) {
            continue;
        }

        delete msg.local_edit_timestamp;

        msgs_to_rerender.push(msg);

        message_store.update_booleans(msg, event.flags);

        unread.update_message_for_mention(msg);

        condense.un_cache_message_content_height(msg.id);

        if (event.rendered_content !== undefined) {
            msg.content = event.rendered_content;
        }

        if (event.is_me_message !== undefined) {
            msg.is_me_message = event.is_me_message;
        }

        const row = message_lists.current.get_row(event.message_id);
        if (row.length > 0) {
            message_edit.end_message_row_edit(row);
        }

        const new_topic = util.get_edit_event_topic(event);

        const new_stream_id = event.new_stream_id;

        const old_stream = sub_store.get(event.stream_id);

        // A topic edit may affect multiple messages, listed in
        // event.message_ids. event.message_id is still the first message
        // where the user initiated the edit.
        topic_edited = new_topic !== undefined;
        stream_changed = new_stream_id !== undefined;
        stream_archived = old_stream === undefined;
        if (topic_edited || stream_changed) {
            const going_forward_change = ["change_later", "change_all"].includes(
                event.propagate_mode,
            );

            const stream_name = stream_archived ? undefined : old_stream.name;
            const compose_stream_name = compose_state.stream_name();
            const orig_topic = util.get_edit_event_orig_topic(event);

            const current_filter = narrow_state.filter();
            const current_selected_id = message_lists.current.selected_id();
            const selection_changed_topic = event.message_ids.includes(current_selected_id);
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
                stream_name &&
                compose_stream_name &&
                stream_name.toLowerCase() === compose_stream_name.toLowerCase() &&
                orig_topic === compose_state.topic()
            ) {
                changed_compose = true;
                compose_state.topic(new_topic);
                compose_validate.warn_if_topic_resolved();
                compose_fade.set_focused_recipient("stream");
            }

            for (const msg of event_messages) {
                if (page_params.realm_allow_edit_history) {
                    /* Simulate the format of server-generated edit
                     * history events. This logic ensures that all
                     * messages that were moved are displayed as such
                     * without a browser reload. */
                    const edit_history_entry = {
                        edited_by: event.edited_by,
                        prev_topic: orig_topic,
                        prev_stream: event.stream_id,
                        timestamp: event.edit_timestamp,
                    };
                    if (msg.edit_history === undefined) {
                        msg.edit_history = [];
                    }
                    msg.edit_history = [edit_history_entry].concat(msg.edit_history);
                }
                msg.last_edit_timestamp = event.edit_timestamp;
                delete msg.last_edit_timestr;

                // Remove the recent topics entry for the old topics;
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
                    stream_id: msg.stream_id,
                    topic_name: msg.topic,
                    num_messages: 1,
                    max_removed_msg_id: msg.id,
                });

                // Update the unread counts; again, this must be called
                // before we modify the topic field on the message.
                unread.update_unread_topics(msg, event);

                // Now edit the attributes of our message object.
                if (topic_edited) {
                    msg.topic = new_topic;
                    msg.topic_links = event.topic_links;
                }
                if (stream_changed) {
                    const new_stream_name = sub_store.get(new_stream_id).name;
                    msg.stream_id = event.new_stream_id;
                    msg.stream = new_stream_name;
                    msg.display_recipient = new_stream_name;
                }

                // Add the recent topics entry for the new stream/topics.
                stream_topic_history.add_message({
                    stream_id: msg.stream_id,
                    topic_name: msg.topic,
                    message_id: msg.id,
                });
            }

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
                current_filter.has_topic(stream_name, orig_topic)
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
                        operator: "stream",
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
                    const operators = new_filter.operators();
                    const opts = {
                        trigger: "stream/topic change",
                        then_select_id: current_selected_id,
                    };
                    narrow.activate(operators, opts);
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
            if (!changed_narrow) {
                let message_ids_to_remove = [];
                if (current_filter && current_filter.can_apply_locally()) {
                    const predicate = current_filter.predicate();
                    message_ids_to_remove = event_messages.filter((msg) => !predicate(msg));
                    message_ids_to_remove = message_ids_to_remove.map((msg) => msg.id);
                }
                // We filter out messages that do not belong to the message
                // list and then pass these to the remove messages codepath.
                // While we can pass all our messages to the add messages
                // codepath as the filtering is done within the method.
                message_lists.current.remove_and_rerender(message_ids_to_remove);
                message_lists.current.add_messages(event_messages);
            }
        }

        if (event.orig_content !== undefined) {
            if (page_params.realm_allow_edit_history) {
                // Note that we do this for topic edits separately, above.
                // If an event changed both content and topic, we'll generate
                // two client-side events, which is probably good for display.
                const edit_history_entry = {
                    edited_by: event.edited_by,
                    prev_content: event.orig_content,
                    prev_rendered_content: event.orig_rendered_content,
                    prev_rendered_content_version: event.prev_rendered_content_version,
                    timestamp: event.edit_timestamp,
                };
                // Add message's edit_history in message dict
                // For messages that are edited, edit_history needs to
                // be added to message in frontend.
                if (msg.edit_history === undefined) {
                    msg.edit_history = [];
                }
                msg.edit_history = [edit_history_entry].concat(msg.edit_history);
            }
            message_content_edited = true;

            // Update raw_content, so that editing a few times in a row is fast.
            msg.raw_content = event.content;
        }

        msg.last_edit_timestamp = event.edit_timestamp;
        delete msg.last_edit_timestr;

        notifications.received_messages([msg]);
        alert_words.process_message(msg);

        if (topic_edited || stream_changed) {
            // if topic is changed
            let pre_edit_topic = util.get_edit_event_orig_topic(event);
            let post_edit_topic = new_topic;

            if (!topic_edited) {
                pre_edit_topic = msg.topic;
                post_edit_topic = pre_edit_topic;
            }

            // new_stream_id is undefined if this is only a topic edit.
            const post_edit_stream_id = new_stream_id || event.stream_id;

            const args = [event.stream_id, pre_edit_topic, post_edit_topic, post_edit_stream_id];
            recent_senders.process_topic_edit({
                message_ids: event.message_ids,
                old_stream_id: event.stream_id,
                old_topic: pre_edit_topic,
                new_stream_id: post_edit_stream_id,
                new_topic: post_edit_topic,
            });
            recent_topics_ui.process_topic_edit(...args);
        }

        // Rerender "Message edit history" if it was open to the edited message.
        if (
            $("#message-edit-history").parents(".micromodal").hasClass("modal--open") &&
            msg.id === Number.parseInt($("#message-history").attr("data-message-id"), 10)
        ) {
            message_edit_history.fetch_and_render_message_history(msg);
        }
    }

    // If a topic was edited, we re-render the whole view to get any
    // propagated edits to be updated (since the topic edits can have
    // changed the correct grouping of messages).
    if (topic_edited || stream_changed) {
        message_lists.home.update_muting_and_rerender();
        // However, we don't need to rerender message_list.narrowed if
        // we just changed the narrow earlier in this function.
        //
        // TODO: We can potentially optimize this logic to avoid
        // calling `update_muting_and_rerender` if the muted
        // messages would not match the view before or after this
        // edit.  Doing so could save significant work, since most
        // topic edits will not match the current topic narrow in
        // large organizations.
        if (!changed_narrow && message_lists.current === message_list.narrowed) {
            message_list.narrowed.update_muting_and_rerender();
        }
    } else {
        // If the content of the message was edited, we do a special animation.
        message_lists.current.view.rerender_messages(msgs_to_rerender, message_content_edited);
        if (message_lists.current === message_list.narrowed) {
            message_lists.home.view.rerender_messages(msgs_to_rerender);
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
    for (const list of [message_lists.home, message_list.narrowed]) {
        if (list === undefined) {
            continue;
        }
        list.remove_and_rerender(message_ids);
    }
    recent_senders.update_topics_of_deleted_message_ids(message_ids);
    recent_topics_ui.update_topics_of_deleted_message_ids(message_ids);
}
