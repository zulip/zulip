import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import * as resolved_topic from "../shared/src/resolved_topic.ts";

import * as activity from "./activity.ts";
import * as alert_words from "./alert_words.ts";
import * as channel from "./channel.ts";
import * as compose_fade from "./compose_fade.ts";
import * as compose_notifications from "./compose_notifications.ts";
import * as compose_recipient from "./compose_recipient.ts";
import * as compose_state from "./compose_state.ts";
import * as compose_validate from "./compose_validate.ts";
import * as direct_message_group_data from "./direct_message_group_data.ts";
import * as drafts from "./drafts.ts";
import * as echo from "./echo.ts";
import type {Filter} from "./filter.ts";
import * as lightbox from "./lightbox.ts";
import * as message_edit from "./message_edit.ts";
import * as message_edit_history from "./message_edit_history.ts";
import * as message_events_util from "./message_events_util.ts";
import * as message_helper from "./message_helper.ts";
import * as message_list_data_cache from "./message_list_data_cache.ts";
import * as message_lists from "./message_lists.ts";
import * as message_notifications from "./message_notifications.ts";
import * as message_parser from "./message_parser.ts";
import * as message_store from "./message_store.ts";
import {type Message, type RawMessage, raw_message_schema} from "./message_store.ts";
import * as message_view from "./message_view.ts";
import * as narrow_state from "./narrow_state.ts";
import * as pm_list from "./pm_list.ts";
import * as recent_senders from "./recent_senders.ts";
import * as recent_view_ui from "./recent_view_ui.ts";
import * as recent_view_util from "./recent_view_util.ts";
import type {UpdateMessageEvent} from "./server_event_types.ts";
import {message_edit_history_visibility_policy_values} from "./settings_config.ts";
import * as starred_messages from "./starred_messages.ts";
import * as starred_messages_ui from "./starred_messages_ui.ts";
import {realm} from "./state_data.ts";
import * as stream_list from "./stream_list.ts";
import * as stream_topic_history from "./stream_topic_history.ts";
import * as sub_store from "./sub_store.ts";
import * as unread from "./unread.ts";
import * as unread_ui from "./unread_ui.ts";
import * as util from "./util.ts";

function filter_has_term_type(filter: Filter, term_type: string): boolean {
    return (
        filter.sorted_term_types().includes(term_type) ||
        filter.sorted_term_types().includes(`not-${term_type}`)
    );
}

export function discard_cached_lists_with_term_type(term_type: string): void {
    // Discards cached MessageList and MessageListData which have
    // `term_type` and `not-term_type`.
    assert(!term_type.includes("not-"));

    // We loop over rendered message lists and cached message data separately since
    // they are separately maintained and can have different items.
    for (const msg_list of message_lists.all_rendered_message_lists()) {
        // We never want to discard the current message list.
        if (msg_list === message_lists.current) {
            continue;
        }

        const filter = msg_list.data.filter;
        if (filter_has_term_type(filter, term_type)) {
            message_lists.delete_message_list(msg_list);
            message_list_data_cache.remove(filter);
        }
    }

    for (const msg_list_data of message_lists.non_rendered_data()) {
        const filter = msg_list_data.filter;
        if (filter_has_term_type(filter, term_type)) {
            message_list_data_cache.remove(filter);
        }
    }
}

export function update_current_view_for_topic_visibility(): boolean {
    // If we have rendered message list / cached data based on topic
    // visibility policy, we need to rerender it to reflect the changes. It
    // is easier to just load the narrow from scratch, instead of asking server
    // for relevant messages in the updated topic.
    const filter = message_lists.current?.data.filter;
    if (filter !== undefined && filter_has_term_type(filter, "is-followed")) {
        // Use `set_timeout to call after we update the topic
        // visibility policy locally.
        // Calling this outside `user_topics_ui` to avoid circular imports.
        assert(message_lists.current !== undefined);
        const msg_list_id = message_lists.current.id;
        setTimeout(() => {
            assert(message_lists.current !== undefined);
            if (message_lists.current.id !== msg_list_id) {
                // Check if the message list is still the same.
                return;
            }

            message_view.show(filter.terms(), {
                then_select_id: message_lists.current.selected_id(),
                trigger: "topic visibility policy change",
                force_rerender: true,
            });
        }, 0);
        return true;
    }
    return false;
}

export let update_views_filtered_on_message_property = (
    message_ids: number[],
    property_term_type: string,
    property_value: boolean,
): void => {
    // NOTE: Call this function after updating the message property locally.
    assert(!property_term_type.includes("not-"));

    // List of narrow terms where the message list doesn't get
    // automatically updated elsewhere when the property changes, but
    // we can apply locally if we have the message.
    //
    // is:followed is handled via update_current_view_for_topic_visibility.
    const supported_term_types = [
        "has-image",
        "has-link",
        "has-reaction",
        "has-attachment",
        "is-starred",
        "is-unread",
        "is-mentioned",
        "is-alerted",
    ];

    if (message_ids.length === 0 || !supported_term_types.includes(property_term_type)) {
        return;
    }

    for (const msg_list of message_lists.all_rendered_message_lists()) {
        const filter = msg_list.data.filter;
        const filter_term_types = filter.sorted_term_types();
        if (
            // Check if current filter relies on the changed message property.
            !filter_term_types.includes(property_term_type) &&
            !filter_term_types.includes(`not-${property_term_type}`)
        ) {
            continue;
        }

        // We need the message objects to determine if they match the filter.
        const messages_to_fetch: number[] = [];
        const messages: Message[] = [];
        for (const message_id of message_ids) {
            const message = message_store.get(message_id);
            if (message !== undefined) {
                messages.push(message);
            } else {
                if (
                    (filter_term_types.includes(property_term_type) && !property_value) ||
                    (filter_term_types.includes(`not-${property_term_type}`) && property_value)
                ) {
                    // If the message is not cached, that means it is not present in the message list.
                    // Also, the message is not supposed to be in the message list as per the filter and
                    // it's property value. So, we don't need to fetch the message.
                    continue;
                }

                const first_message = msg_list.first();
                assert(first_message !== undefined);
                const first_id = first_message.id;
                const last_message = msg_list.last();
                assert(last_message !== undefined);
                const last_id = last_message.id;
                const has_found_newest = msg_list.data.fetch_status.has_found_newest();
                const has_found_oldest = msg_list.data.fetch_status.has_found_oldest();

                if (message_id > first_id && message_id < last_id) {
                    // Need to insert message middle of the list.
                    messages_to_fetch.push(message_id);
                } else if (message_id < first_id && has_found_oldest) {
                    // Need to insert message at the start of list.
                    messages_to_fetch.push(message_id);
                } else if (message_id > last_id && has_found_newest) {
                    // Need to insert message at the end of list.
                    messages_to_fetch.push(message_id);
                }
            }
        }

        if (!filter.can_apply_locally()) {
            channel.get({
                url: "/json/messages",
                data: {
                    message_ids: JSON.stringify(message_ids),
                    narrow: JSON.stringify(filter.terms()),
                    allow_empty_topic_name: true,
                },
                success(data) {
                    const messages_to_add: Message[] = [];
                    const messages_to_remove = new Set(message_ids);
                    for (const raw_message of z
                        .object({messages: z.array(raw_message_schema)})
                        .parse(data).messages) {
                        messages_to_remove.delete(raw_message.id);
                        const message = message_store.get(raw_message.id);
                        messages_to_add.push(
                            message ?? message_helper.process_new_message(raw_message),
                        );
                    }
                    msg_list.data.remove([...messages_to_remove]);
                    msg_list.data.add_messages(messages_to_add);
                    msg_list.rerender();
                },
            });
        } else if (messages_to_fetch.length > 0) {
            // Fetch the message and update the view.
            channel.get({
                url: "/json/messages",
                data: {
                    message_ids: JSON.stringify(messages_to_fetch),
                    allow_empty_topic_name: true,
                    // We don't filter by narrow here since we can
                    // apply the filter locally and the fetched message
                    // can be used to update other message lists and
                    // cached message data structures as well.
                },
                // eslint-disable-next-line @typescript-eslint/no-loop-func
                success(data) {
                    const parsed_data = z
                        .object({
                            messages: z.array(raw_message_schema),
                        })
                        .parse(data);
                    // `messages_to_fetch` might already be cached locally when
                    // we reach here but `message_helper.process_new_message`
                    // already handles that case.
                    for (const raw_message of parsed_data.messages) {
                        message_helper.process_new_message(raw_message);
                    }
                    update_views_filtered_on_message_property(
                        message_ids,
                        property_term_type,
                        property_value,
                    );
                },
            });
        } else {
            // We have all the messages locally, so we can update the view.
            //
            // Special case: For starred messages view, we don't remove
            // messages that are no longer starred to avoid
            // implementing an undo mechanism for that view.
            // TODO: A cleaner way to implement this might be to track which things
            // have been unstarred in the starred messages view in this visit
            // to the view, and have those stay.
            if (
                property_term_type === "is-starred" &&
                _.isEqual(filter.sorted_term_types(), ["is-starred"])
            ) {
                msg_list.add_messages(messages);
                continue;
            }

            // In most cases, we are only working to update a single message.
            if (messages.length === 1) {
                const message = messages[0]!;
                if (filter.predicate()(message)) {
                    msg_list.add_messages(messages);
                } else {
                    msg_list.remove_and_rerender(message_ids);
                }
            } else {
                msg_list.data.remove(message_ids);
                msg_list.data.add_messages(messages);
                msg_list.rerender();
            }
        }
    }
};

export function rewire_update_views_filtered_on_message_property(
    value: typeof update_views_filtered_on_message_property,
): void {
    update_views_filtered_on_message_property = value;
}

export function insert_new_messages(
    raw_messages: RawMessage[],
    sent_by_this_client: boolean,
    deliver_locally: boolean,
): Message[] {
    const messages = raw_messages.map((raw_message) =>
        message_helper.process_new_message(raw_message, deliver_locally),
    );

    const any_untracked_unread_messages = unread.process_loaded_messages(messages, false);
    direct_message_group_data.process_loaded_messages(messages);

    let need_user_to_scroll = false;
    for (const list of message_lists.all_rendered_message_lists()) {
        if (!list.data.filter.can_apply_locally()) {
            // If we cannot locally calculate whether the new messages
            // match the message list, we ask the server whether the
            // new messages match the narrow, and use that to
            // determine which new messages to add to the current
            // message list (or display a notification).

            if (deliver_locally) {
                // However, this is a local echo attempt, we can't ask
                // the server about the match, since we don't have a
                // final message ID. In that situation, we do nothing
                // and echo.process_from_server will call
                // message_events_util.maybe_add_narrowed_messages
                // once the message is fully delivered.
                continue;
            }

            const messages_are_new = true;
            message_events_util.maybe_add_narrowed_messages(messages, list, messages_are_new);
            continue;
        }

        // Update the message list's rendering for the newly arrived messages.
        const render_info = list.add_messages(messages, {messages_are_new: true});

        // The render_info.need_user_to_scroll calculation, which
        // looks at message feed scroll positions to see whether the
        // newly arrived message will be visible, is only valid if
        // this message list is the currently visible message list.
        const is_currently_visible =
            narrow_state.is_message_feed_visible() && list === message_lists.current;
        if (is_currently_visible && render_info?.need_user_to_scroll) {
            need_user_to_scroll = true;
        }
    }

    for (const msg_list_data of message_lists.non_rendered_data()) {
        if (!msg_list_data.filter.can_apply_locally()) {
            // Ideally we would ask server to if messages matches filter
            // but it is not worth doing so for every new message.
            message_list_data_cache.remove(msg_list_data.filter);
        } else {
            msg_list_data.add_messages(messages);
        }
    }

    // sent_by_this_client will be true if ANY of the messages
    // were sent by this client; notifications.notify_local_mixes
    // will filter out any not sent by us.
    if (sent_by_this_client) {
        compose_notifications.notify_local_mixes(messages, need_user_to_scroll, {
            narrow_to_recipient(message_id) {
                message_view.narrow_by_topic(message_id, {trigger: "outside_current_view"});
            },
        });
    }

    if (any_untracked_unread_messages) {
        unread_ui.update_unread_counts();
    }

    // Messages being locally echoed need must be inserted into this
    // tracking before we update the stream sidebar, to take advantage
    // of how stream_topic_history uses the echo data structures.
    if (deliver_locally) {
        for (const message of messages) {
            echo.track_local_message(message);
        }
    }

    activity.set_received_new_messages(true);
    message_notifications.received_messages(messages);
    stream_list.update_streams_sidebar();
    pm_list.update_private_messages();

    return messages;
}

function topic_resolve_toggled(new_topic: string, original_topic: string): boolean {
    if (resolved_topic.is_resolved(new_topic) && new_topic.slice(2) === original_topic) {
        return true;
    }
    if (resolved_topic.is_resolved(original_topic) && original_topic.slice(2) === new_topic) {
        return true;
    }
    return false;
}

export function update_messages(events: UpdateMessageEvent[]): void {
    const messages_to_rerender: Message[] = [];
    let changed_narrow = false;
    let refreshed_current_narrow = false;
    let changed_compose = false;
    let any_message_content_edited = false;
    let local_cache_missing_messages = false;

    // Clear message list data cache since the local data for the
    // filters might no longer be accurate.
    //
    // TODO: Add logic to update the message list data cache.
    // Special care needs to be taken to ensure that the cache is
    // updated correctly when the message is moved to a different
    // stream or topic. Also, we need to update message lists like
    // `is:starred`, `is:mentioned`, etc. when the message flags are
    // updated.
    message_list_data_cache.clear();

    for (const event of events) {
        const anchor_message = message_store.get(event.message_id);
        if (anchor_message !== undefined) {
            // Logic for updating the specific edited message only
            // needs to run if we had a local copy of the message.

            delete anchor_message.local_edit_timestamp;

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
                if (
                    realm.realm_message_edit_history_visibility_policy ===
                    message_edit_history_visibility_policy_values.always.code
                ) {
                    // Note that we do this for topic edits separately, below.
                    // If an event changed both content and topic, we'll generate
                    // two client-side events, which is probably good for display.
                    const edit_history_entry = {
                        user_id: event.user_id,
                        prev_content: event.orig_content,
                        prev_rendered_content: event.orig_rendered_content,
                        timestamp: event.edit_timestamp,
                    };
                    // Add message's edit_history in message dict
                    // For messages that are edited, edit_history needs to
                    // be added to message in frontend.
                    anchor_message.edit_history = [
                        edit_history_entry,
                        ...(anchor_message.edit_history ?? []),
                    ];
                }
                any_message_content_edited = true;

                // Update raw_content, so that editing a few times in a row is fast.
                anchor_message.raw_content = event.content;

                // Editing a message may change the titles for linked
                // media, so we must invalidate the asset map.
                lightbox.invalidate_asset_map_of_message(event.message_id);
            }

            if (unread.update_message_for_mention(anchor_message, any_message_content_edited)) {
                assert(anchor_message.type === "stream");
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
        const old_stream =
            event.stream_id === undefined ? undefined : sub_store.get(event.stream_id);

        // A topic or stream edit may affect multiple messages, listed in
        // event.message_ids. event.message_id is still the first message
        // where the user initiated the edit.
        const topic_edited = new_topic !== undefined;
        const stream_changed = new_stream_id !== undefined;
        const stream_archived = old_stream === undefined;

        if (!topic_edited && !stream_changed) {
            // If the topic or stream of the anchor message was changed,
            // it will be rerendered if present in any rendered list.
            //
            // But for content edits, we need to schedule it to be
            // rerendered, if we have a local copy of it.
            if (anchor_message !== undefined) {
                messages_to_rerender.push(anchor_message);
            }
        } else {
            // We must be moving stream messages.
            assert(old_stream_id !== undefined);
            const orig_topic = util.get_edit_event_orig_topic(event);
            assert(orig_topic !== undefined);

            const going_forward_change =
                event.propagate_mode !== undefined &&
                ["change_later", "change_all"].includes(event.propagate_mode);

            const compose_stream_id = compose_state.stream_id();
            const current_filter = narrow_state.filter();
            const current_selected_id = message_lists.current?.selected_id();
            const selection_changed_topic =
                message_lists.current !== undefined &&
                current_selected_id !== undefined &&
                event.message_ids.includes(current_selected_id);
            const event_messages: (Message & {type: "stream"})[] = [];
            for (const message_id of event.message_ids) {
                // We don't need to concern ourselves updating data structures
                // for messages we don't have stored locally.
                const message = message_store.get(message_id);
                if (message !== undefined) {
                    assert(message.type === "stream");
                    event_messages.push(message);
                } else {
                    // If we don't have the message locally, we need to
                    // refresh the current narrow after the update to fetch
                    // the updated messages.
                    local_cache_missing_messages = true;
                }
            }

            if (
                going_forward_change &&
                !stream_archived &&
                compose_stream_id &&
                old_stream.stream_id === compose_stream_id &&
                orig_topic === compose_state.topic()
            ) {
                changed_compose = true;
                compose_state.topic(new_topic);

                if (stream_changed) {
                    compose_state.set_stream_id(new_stream_id);
                    compose_recipient.on_compose_select_recipient_update();
                }

                compose_validate.warn_if_topic_resolved(true);
                compose_validate.inform_if_topic_is_moved(orig_topic, old_stream_id, event.user_id);
                compose_fade.set_focused_recipient("stream");
            }

            if (going_forward_change) {
                drafts.rename_stream_recipient(old_stream_id, orig_topic, new_stream_id, new_topic);
            }

            for (const moved_message of event_messages) {
                if (
                    realm.realm_message_edit_history_visibility_policy !==
                    message_edit_history_visibility_policy_values.never.code
                ) {
                    /* Simulate the format of server-generated edit
                     * history events. This logic ensures that all
                     * messages that were moved are displayed as such
                     * without a browser reload. */
                    const edit_history_entry: {
                        user_id: number | null;
                        timestamp: number;
                        stream?: number;
                        prev_stream?: number;
                        topic?: string;
                        prev_topic?: string;
                    } = {
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
                    moved_message.edit_history = [
                        edit_history_entry,
                        ...(moved_message.edit_history ?? []),
                    ];
                }

                if (stream_changed) {
                    moved_message.last_moved_timestamp = event.edit_timestamp;
                } else if (topic_edited) {
                    assert(new_topic !== undefined);
                    if (!topic_resolve_toggled(new_topic, orig_topic)) {
                        moved_message.last_moved_timestamp = event.edit_timestamp;
                    }
                }

                // Update the unread counts; again, this must be called
                // before we modify the topic field on the message.
                unread.update_unread_topics(moved_message, event);

                // Now edit the attributes of our message object.
                if (topic_edited) {
                    moved_message.topic = new_topic;
                    assert(event.topic_links !== undefined);
                    moved_message.topic_links = event.topic_links;
                }
                if (stream_changed) {
                    const new_stream = sub_store.get(new_stream_id);
                    assert(new_stream !== undefined);
                    const new_stream_name = new_stream.name;
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

            // Remove the stream_topic_entry for the old topics;
            // must be called after we call set message topic since
            // it calls `get_loaded_messages_in_topic` which thinks that
            // `topic` and `stream` of the messages are correctly set.
            const num_messages = event_messages.length;
            if (num_messages > 0) {
                stream_topic_history.remove_messages({
                    stream_id: old_stream_id,
                    topic_name: orig_topic,
                    num_messages,
                    max_removed_msg_id: event_messages[num_messages - 1]!.id,
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
                current_filter?.has_topic(old_stream_id, orig_topic)
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
                    new_filter = new_filter.filter_with_new_params({
                        operator: "channel",
                        operand: new_stream_id.toString(),
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
                    // Remove outdated cached data to avoid repopulating from it.
                    // We are yet to update the cached message list data for
                    // the moved topics.
                    // TODO: Update the cache instead of discarding it.
                    message_list_data_cache.remove(new_filter);
                    const terms = new_filter.terms();
                    const opts = {
                        trigger: "stream/topic change",
                        then_select_id: current_selected_id,
                    };
                    message_view.show(terms, opts);
                }
            }

            // If a message was moved to the current narrow and we don't have
            // the message cached, we need to refresh the narrow to display the message.
            if (!changed_narrow && local_cache_missing_messages && current_filter) {
                let moved_message_stream_id_str = old_stream_id.toString();
                let moved_message_topic = orig_topic;
                if (stream_changed) {
                    const new_stream = sub_store.get(new_stream_id);
                    assert(new_stream !== undefined);
                    moved_message_stream_id_str = new_stream.stream_id.toString();
                }

                if (topic_edited) {
                    moved_message_topic = new_topic;
                }

                if (
                    current_filter.can_newly_match_moved_messages(
                        moved_message_stream_id_str,
                        moved_message_topic,
                    )
                ) {
                    refreshed_current_narrow = true;
                    message_view.show(current_filter.terms(), {
                        then_select_id: current_selected_id,
                        trigger: "stream/topic change",
                        force_rerender: true,
                    });
                }
            }

            // Ensure messages that are no longer part of this
            // narrow are deleted and messages that are now part
            // of this narrow are added to the message_list.
            //
            // TODO: Update cached message list data objects as well.
            for (const list of message_lists.all_rendered_message_lists()) {
                if (
                    list === message_lists.current &&
                    (changed_narrow || refreshed_current_narrow)
                ) {
                    continue;
                }

                const event_msg_ids = event_messages.map((msg) => msg.id);
                if (list.data.filter.can_apply_locally()) {
                    // Remove add messages and add them back to the list to
                    // allow event muted messages which were previously part
                    // of the message list but hidden could be rerendered again.
                    list.data.remove(event_msg_ids);
                    list.data.add_messages(event_messages);
                    list.rerender();
                } else {
                    // Remove existing message that were updated, since
                    // they may not be a part of the filter now. Also,
                    // this will help us rerender them via
                    // maybe_add_narrowed_messages, if they were
                    // simply updated.
                    list.remove_and_rerender(event_msg_ids);
                    // For filters that cannot be processed locally, ask server.
                    message_events_util.maybe_add_narrowed_messages(event_messages, list);
                }
            }
        }

        if (anchor_message !== undefined) {
            // Mark the message as edited for the UI. The rendering_only
            // flag is used to indicated update_message events that are
            // triggered by server latency optimizations, not user
            // interactions; these should not generate edit history updates.
            if (!event.rendering_only && any_message_content_edited) {
                anchor_message.last_edit_timestamp = event.edit_timestamp;
            }

            message_notifications.received_messages([anchor_message]);
            alert_words.process_message(anchor_message);
        }

        if (topic_edited || stream_changed) {
            // We must be moving stream messages.
            assert(old_stream_id !== undefined);
            let pre_edit_topic = util.get_edit_event_orig_topic(event);
            assert(pre_edit_topic !== undefined);

            let post_edit_topic: string;
            if (topic_edited) {
                assert(new_topic !== undefined);
                post_edit_topic = new_topic;
            } else {
                if (anchor_message !== undefined) {
                    assert(anchor_message.type === "stream");
                    pre_edit_topic = anchor_message.topic;
                }
                post_edit_topic = pre_edit_topic;
            }

            // new_stream_id is undefined if this is only a topic edit.
            const post_edit_stream_id = new_stream_id ?? old_stream_id;

            recent_senders.process_topic_edit({
                message_ids: event.message_ids,
                old_stream_id,
                old_topic: pre_edit_topic,
                new_stream_id: post_edit_stream_id,
                new_topic: post_edit_topic,
            });
            unread.clear_and_populate_unread_mentions();
            recent_view_ui.process_topic_edit(
                old_stream_id,
                pre_edit_topic,
                post_edit_topic,
                post_edit_stream_id,
            );
        }

        // Rerender "Message edit history" if it was open to the edited message.
        if (
            anchor_message !== undefined &&
            $("#message-edit-history").parents(".micromodal").hasClass("modal--open") &&
            anchor_message.id ===
                Number.parseInt($("#message-history").attr("data-message-id")!, 10)
        ) {
            message_edit_history.fetch_and_render_message_history(anchor_message);
        }

        if (event.rendered_content !== undefined) {
            // It is fine to call this in a loop since most of the time we are
            // only working with a single message content edit.
            update_views_filtered_on_message_property(
                [event.message_id],
                "has-image",
                message_parser.message_has_image(event.rendered_content),
            );
            update_views_filtered_on_message_property(
                [event.message_id],
                "has-link",
                message_parser.message_has_link(event.rendered_content),
            );
            update_views_filtered_on_message_property(
                [event.message_id],
                "has-attachment",
                message_parser.message_has_attachment(event.rendered_content),
            );

            const is_mentioned = event.flags.some((flag) =>
                ["mentioned", "stream_wildcard_mentioned", "topic_wildcard_mentioned"].includes(
                    flag,
                ),
            );
            update_views_filtered_on_message_property(
                [event.message_id],
                "is-mentioned",
                is_mentioned,
            );
            const is_alerted = event.flags.includes("has_alert_word");
            update_views_filtered_on_message_property([event.message_id], "is-alerted", is_alerted);
        }
    }

    if (messages_to_rerender.length > 0) {
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

export function remove_messages(message_ids: number[]): void {
    // Update the rendered data first since it is most user visible.
    for (const list of message_lists.all_rendered_message_lists()) {
        list.remove_and_rerender(message_ids);
    }

    for (const msg_list_data of message_lists.non_rendered_data()) {
        msg_list_data.remove(message_ids);
    }

    recent_senders.update_topics_of_deleted_message_ids(message_ids);
    recent_view_ui.update_topics_of_deleted_message_ids(message_ids);
    starred_messages.remove(message_ids);
    starred_messages_ui.rerender_ui();
    message_store.remove(message_ids);
}
