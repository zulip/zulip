import assert from "minimalistic-assert";

import * as blueslip from "./blueslip.ts";
import {ConversationParticipants} from "./conversation_participants.ts";
import {FetchStatus} from "./fetch_status.ts";
import type {Filter} from "./filter.ts";
import type {Message} from "./message_store.ts";
import * as muted_users from "./muted_users.ts";
import {current_user} from "./state_data.ts";
import * as user_topics from "./user_topics.ts";
import * as util from "./util.ts";

export class MessageListData {
    // The Filter object defines which messages match the narrow,
    // and defines most of the configuration for the MessageListData.
    filter: Filter;
    // The FetchStatus object keeps track of our understanding of
    // to what extent this MessageListData has all the messages
    // that the server possesses matching this narrow, and whether
    // we're in the progress of fetching more.
    fetch_status: FetchStatus;
    // _all_items is a sorted list of all message objects that
    // match this.filter, regardless of muting.
    //
    // Most code will instead use _items, which contains
    // only messages that should be displayed after excluding
    // muted topics and messages sent by muted users.
    _all_items: Message[];
    _items: Message[];
    // _hash contains the same messages as _all_items, mapped by
    // message ID. It's used to efficiently query if a given
    // message is present.
    _hash: Map<number, Message>;
    // Some views exclude muted topics.
    //
    // TODO: Refactor this to be a property of Filter, rather than
    // a parameter that needs to be passed into the constructor.
    excludes_muted_topics: boolean;
    // Tracks any locally echoed messages, which we know aren't present on the server.
    _local_only: Set<number>;
    // The currently selected message ID. The special value -1
    // there is no selected message. A common situation is when
    // there are no messages matching the current filter.
    _selected_id: number;
    predicate?: (message: Message) => boolean;
    // This is a callback that is called when messages are added to the message list.
    add_messages_callback?: (messages: Message[], recipient_order_changed: boolean) => void;

    // ID of the MessageList for which this MessageListData is the data.
    // Using ID instead of the MessageList object itself to avoid circular dependencies
    // and to allow MessageList objects to be easily garbage collected.
    rendered_message_list_id: number | undefined;

    // TODO: Use it as source of participants data in buddy list.
    participants: ConversationParticipants;
    // MessageListData is a core data structure for keeping track of a
    // contiguous block of messages matching a given narrow that can
    // be displayed in a Zulip message feed.
    //
    // See also MessageList and MessageListView, which are important
    // to actually display a message list.

    constructor({excludes_muted_topics, filter}: {excludes_muted_topics: boolean; filter: Filter}) {
        this.filter = filter;
        this.fetch_status = new FetchStatus();
        this.participants = new ConversationParticipants([]);
        this._all_items = [];
        this._items = [];
        this._hash = new Map();
        this.excludes_muted_topics = excludes_muted_topics;
        this._local_only = new Set();
        this._selected_id = -1;
    }

    set_rendered_message_list_id(rendered_message_list_id: number | undefined): void {
        this.rendered_message_list_id = rendered_message_list_id;
    }

    set_add_messages_callback(
        callback: (messages: Message[], rows_order_changed: boolean) => void,
    ): void {
        this.add_messages_callback = callback;
    }

    all_messages(): Message[] {
        return this._items;
    }

    num_items(): number {
        return this._items.length;
    }

    // The message list is completely empty.
    empty(): boolean {
        return this._all_items.length === 0;
    }

    // The message list appears empty, but might contain messages that hidden by muting.
    visibly_empty(): boolean {
        return this._items.length === 0;
    }

    first(): Message | undefined {
        return this._items[0];
    }

    first_including_muted(): Message | undefined {
        return this._all_items[0];
    }

    last(): Message | undefined {
        return this._items.at(-1);
    }

    last_including_muted(): Message | undefined {
        return this._all_items.at(-1);
    }

    msg_id_in_fetched_range(msg_id: number): boolean {
        if (this.empty()) {
            return false;
        }

        return this.first()!.id <= msg_id && msg_id <= this.last()!.id;
    }

    select_idx(): number | undefined {
        if (this._selected_id === -1) {
            return undefined;
        }
        const ids = this._items.map((message) => message.id);

        const i = ids.indexOf(this._selected_id);
        if (i === -1) {
            return undefined;
        }
        return i;
    }

    prev(): number | undefined {
        const i = this.select_idx();

        if (i === undefined) {
            return undefined;
        }
        return this._items[i - 1]?.id;
    }

    next(): number | undefined {
        const i = this.select_idx();

        if (i === undefined) {
            return undefined;
        }
        return this._items[i + 1]?.id;
    }

    is_at_end(): boolean {
        if (this._selected_id === -1) {
            return false;
        }
        return this.last()?.id === this._selected_id;
    }

    clear(): void {
        this._all_items = [];
        this._items = [];
        this._hash.clear();
        this.participants = new ConversationParticipants([]);
    }

    // TODO(typescript): Ideally this should only take a number.
    get(id: number | string): Message | undefined {
        const number_id = typeof id === "number" ? id : Number.parseFloat(id);
        if (Number.isNaN(number_id)) {
            return undefined;
        }
        return this._hash.get(number_id);
    }

    clear_selected_id(): void {
        this._selected_id = -1;
    }

    selected_id(): number {
        return this._selected_id;
    }

    set_selected_id(id: number): void {
        this._selected_id = id;
    }

    selected_idx(): number {
        return this._lower_bound(this._selected_id);
    }

    reset_select_to_closest(): void {
        this._selected_id = this.closest_id(this._selected_id);
    }

    is_keyword_search(): boolean {
        return this.filter.is_keyword_search();
    }
    can_mark_messages_read(): boolean {
        return this.filter.can_mark_messages_read();
    }
    _get_predicate(): (message: Message) => boolean {
        // We cache this.
        this.predicate ??= this.filter.predicate();
        return this.predicate;
    }

    valid_non_duplicated_messages(messages: Message[]): Message[] {
        const predicate = this._get_predicate();
        return messages.filter((msg) => this.get(msg.id) === undefined && predicate(msg));
    }

    messages_filtered_for_topic_mutes(messages: Message[]): Message[] {
        if (!this.excludes_muted_topics) {
            return [...messages];
        }

        return messages.filter((message) => {
            if (message.type !== "stream") {
                return true;
            }

            // TODO: Widen this if check to include other narrows as well.
            if (this.filter.is_in_home()) {
                return user_topics.is_topic_visible_in_home(message.stream_id, message.topic);
            }

            return (
                !user_topics.is_topic_muted(message.stream_id, message.topic) || message.mentioned
            );
        });
    }

    messages_filtered_for_user_mutes(messages: Message[]): Message[] {
        if (this.filter.is_non_group_direct_message()) {
            // We are in a 1:1 direct message narrow, so do not do any filtering.
            return [...messages];
        }

        return messages.filter((message) => {
            if (message.type !== "private") {
                return true;
            }
            const recipients = util.extract_pm_recipients(message.to_user_ids);
            if (recipients.length > 1) {
                // Direct message group message
                return true;
            }

            const recipient_id = Number.parseInt(util.the(recipients), 10);
            return (
                !muted_users.is_user_muted(recipient_id) &&
                !muted_users.is_user_muted(message.sender_id)
            );
        });
    }

    unmuted_messages(messages: Message[]): Message[] {
        return this.messages_filtered_for_topic_mutes(
            this.messages_filtered_for_user_mutes(messages),
        );
    }

    update_items_for_muting(): void {
        this._items = this.unmuted_messages(this._all_items);
        this.participants = new ConversationParticipants(this._items);
    }

    first_unread_message_id(): number | undefined {
        // NOTE: This function returns the first unread that was fetched and is not
        // necessarily the first unread for the narrow. There could be more unread messages.
        // See https://github.com/zulip/zulip/pull/30008#discussion_r1597279862 for how
        // ideas on how to possibly improve this.
        // before `first_unread` calculated below that we haven't fetched yet.
        const first_unread = this._items.find((message) => message.unread);

        if (first_unread) {
            return first_unread.id;
        }

        // If no unread, return the bottom message
        // NOTE: This is only valid if we have found the latest message for the narrow as
        // there could be more message that we haven't fetched yet.
        return this.last()?.id;
    }

    has_unread_messages(): boolean {
        return this._items.some((message) => message.unread);
    }

    add_messages(
        messages: Message[],
        is_contiguous_history = false,
    ): {
        top_messages: Message[];
        bottom_messages: Message[];
        interior_messages: Message[];
    } {
        let top_messages = [];
        let bottom_messages = [];
        let interior_messages = [];

        // Filter out duplicates that are already in self, and all messages
        // that fail our filter predicate
        messages = this.valid_non_duplicated_messages(messages);

        for (const msg of messages) {
            // Put messages in correct order on either side of the
            // message list.  This code path assumes that messages
            // is a (1) sorted, and (2) consecutive block of
            // messages that belong in this message list; those
            // facts should be ensured by the caller.
            const last = this.last_including_muted();
            if (last === undefined || msg.id > last.id) {
                bottom_messages.push(msg);
            } else if (msg.id < this.first_including_muted()!.id) {
                top_messages.push(msg);
            } else {
                interior_messages.push(msg);
            }
        }

        if (interior_messages.length > 0) {
            interior_messages = this.add_anywhere(interior_messages);
        }

        if (top_messages.length > 0) {
            top_messages = this.prepend(top_messages);
        }

        if (!is_contiguous_history && !this.fetch_status.has_found_newest()) {
            // Don't add messages at the bottom if we haven't found
            // the latest message to avoid non-contiguous message history.
            this.fetch_status.update_expected_max_message_id(bottom_messages);
            bottom_messages = [];
        }

        if (bottom_messages.length > 0) {
            bottom_messages = this.append(bottom_messages);
        }

        if (this.add_messages_callback) {
            // If we only added old messages, last message for any of the existing recipients didn't change.
            // Although, it maybe have resulted in new recipients being added which should be handled by the caller.
            const recipient_order_changed = !(
                top_messages.length > 0 &&
                bottom_messages.length === 0 &&
                interior_messages.length === 0
            );
            this.add_messages_callback(messages, recipient_order_changed);
        }

        const info = {
            top_messages,
            bottom_messages,
            interior_messages,
        };

        return info;
    }

    add_anywhere(messages: Message[]): Message[] {
        // Caller should have already filtered messages.
        // This should be used internally when we have
        // "interior" messages to add and can't optimize
        // things by only doing prepend or only doing append.

        const viewable_messages = this.unmuted_messages(messages);

        this._all_items = [...messages, ...this._all_items];
        this._all_items.sort((a, b) => a.id - b.id);

        this._items = [...viewable_messages, ...this._items];
        this._items.sort((a, b) => a.id - b.id);

        this.participants.add_from_messages(viewable_messages);

        this._add_to_hash(messages);
        return viewable_messages;
    }

    append(messages: Message[]): Message[] {
        // Caller should have already filtered
        const viewable_messages = this.unmuted_messages(messages);

        this._all_items = [...this._all_items, ...messages];
        this._items = [...this._items, ...viewable_messages];

        this.participants.add_from_messages(viewable_messages);

        this._add_to_hash(messages);
        return viewable_messages;
    }

    prepend(messages: Message[]): Message[] {
        // Caller should have already filtered
        const viewable_messages = this.unmuted_messages(messages);

        this._all_items = [...messages, ...this._all_items];
        this._items = [...viewable_messages, ...this._items];

        this.participants.add_from_messages(viewable_messages);

        this._add_to_hash(messages);
        return viewable_messages;
    }

    remove(message_ids: number[]): boolean {
        const msg_ids_to_remove = new Set(message_ids);
        let found_any_msgs_to_remove = false;
        for (const id of msg_ids_to_remove) {
            const found_in_hash = this._hash.delete(id);
            const found_in_local_only = this._local_only.delete(id);

            if (!found_any_msgs_to_remove && (found_in_hash || found_in_local_only)) {
                found_any_msgs_to_remove = true;
            }
        }

        this._items = this._items.filter((msg) => !msg_ids_to_remove.has(msg.id));
        this._all_items = this._all_items.filter((msg) => !msg_ids_to_remove.has(msg.id));
        this.participants = new ConversationParticipants(this._items);
        return found_any_msgs_to_remove;
    }

    // Returns messages from the given message list in the specified range, inclusive
    message_range(start: number, end: number): Message[] {
        if (start === -1) {
            blueslip.error("message_range given a start of -1");
        }

        const start_idx = this._lower_bound(start);
        const end_idx = this._lower_bound(end);
        return this._items.slice(start_idx, end_idx + 1);
    }

    // Returns the index where you could insert the desired ID
    // into the message list, without disrupting the sort order
    // This takes into account the potentially-unsorted
    // nature of local message IDs in the message list
    _lower_bound(id: number): number {
        const less_func = (msg: Message, ref_id: number, a_idx: number): boolean => {
            if (this._is_localonly_id(msg.id)) {
                // First non-local message before this one
                const effective = this._next_nonlocal_message(this._items, a_idx, (idx) => idx - 1);
                if (effective) {
                    // Turn the 10.02 in [11, 10.02, 12] into 11.02
                    const decimal = Number.parseFloat((msg.id % 1).toFixed(0.02));
                    const effective_id = effective.id + decimal;
                    return effective_id < ref_id;
                }
            }
            return msg.id < ref_id;
        };

        return util.lower_bound(this._items, id, less_func);
    }

    closest_id(id: number): number {
        // We directly keep track of local-only messages,
        // so if we're asked for one that we know we have,
        // just return it directly
        if (this._local_only.has(id)) {
            return id;
        }

        const items = this._items;

        if (items.length === 0) {
            return -1;
        }

        let closest = this._lower_bound(id);

        if (id === items[closest]?.id) {
            return id;
        }

        const potential_closest_matches = [];
        let prev_item;
        while (
            (prev_item = items[closest - 1]) !== undefined &&
            this._is_localonly_id(prev_item.id)
        ) {
            // Since we treated all blocks of local ids as their left-most-non-local message
            // for lower_bound purposes, find the real leftmost index (first non-local id)
            potential_closest_matches.push(closest);
            closest -= 1;
        }
        potential_closest_matches.push(closest);

        let item = items[closest];
        if (item === undefined) {
            item = items[closest - 1];
        } else {
            // Any of the ids that we skipped over (due to them being local-only) might be the
            // closest ID to the desired one, in case there is no exact match.
            potential_closest_matches.unshift(closest - 1);
            let best_match = item.id;

            for (const potential_idx of potential_closest_matches) {
                if (potential_idx < 0) {
                    continue;
                }
                const potential_item = items[potential_idx];

                if (potential_item === undefined) {
                    blueslip.warn("Invalid potential_idx: " + potential_idx);
                    continue;
                }

                const potential_match = potential_item.id;
                // If the potential id is the closest to the requested, save that one
                if (Math.abs(id - potential_match) < Math.abs(best_match - id)) {
                    best_match = potential_match;
                    item = potential_item;
                }
            }
        }
        assert(item !== undefined);
        return item.id;
    }

    advance_past_messages(msg_ids: number[]): void {
        // Start with the current pointer, but then keep advancing the
        // pointer while the next message's id is in msg_ids.  See trac #1555
        // for more context, but basically we are skipping over contiguous
        // messages that we have recently visited.
        let next_msg_id = 0;

        const id_set = new Set(msg_ids);

        let idx = this.selected_idx() + 1;
        while (idx < this._items.length) {
            const msg_id = this._items[idx]!.id;
            if (!id_set.has(msg_id)) {
                break;
            }
            next_msg_id = msg_id;
            idx += 1;
        }

        if (next_msg_id > 0) {
            this.set_selected_id(next_msg_id);
        }
    }

    _add_to_hash(messages: Message[]): void {
        for (const elem of messages) {
            const id = elem.id;
            if (this._is_localonly_id(id)) {
                this._local_only.add(id);
            }
            if (this._hash.has(id)) {
                blueslip.error("Duplicate message added to MessageListData");
                continue;
            }
            this._hash.set(id, elem);
        }
    }

    _is_localonly_id(id: number): boolean {
        return id % 1 !== 0;
    }

    _next_nonlocal_message(
        item_list: Message[],
        start_index: number,
        op: (idx: number) => number,
    ): Message | undefined {
        let cur_idx = start_index;
        let message;
        do {
            cur_idx = op(cur_idx);
            message = item_list[cur_idx];
        } while (message !== undefined && this._is_localonly_id(message.id));
        return message;
    }

    change_message_id(old_id: number, new_id: number): boolean {
        // Update our local cache that uses the old id to the new id
        const msg = this._hash.get(old_id);
        if (msg !== undefined) {
            this._hash.delete(old_id);
            this._hash.set(new_id, msg);
        } else {
            return false;
        }

        if (this._local_only.has(old_id)) {
            if (this._is_localonly_id(new_id)) {
                this._local_only.add(new_id);
            }
            this._local_only.delete(old_id);
        }

        if (this._selected_id === old_id) {
            this._selected_id = new_id;
        }

        return this.reorder_messages(new_id);
    }

    reorder_messages(new_id: number): boolean {
        const message_sort_func = (a: Message, b: Message): number => a.id - b.id;
        // If this message is now out of order, re-order and re-render
        const current_message = this._hash.get(new_id);
        if (current_message === undefined) {
            return false;
        }
        const index = this._items.indexOf(current_message);

        const next = this._next_nonlocal_message(this._items, index, (idx) => idx + 1);
        const prev = this._next_nonlocal_message(this._items, index, (idx) => idx - 1);

        if (
            (next !== undefined && current_message.id > next.id) ||
            (prev !== undefined && current_message.id < prev.id)
        ) {
            blueslip.debug("Changed message ID from server caused out-of-order list, reordering");
            this._items.sort(message_sort_func);
            this._all_items.sort(message_sort_func);
            return true;
        }

        return false;
    }

    get_messages_sent_by_user(user_id: number): Message[] {
        const msgs = this._items.filter((msg) => msg.sender_id === user_id);
        if (msgs.length === 0) {
            return [];
        }
        return msgs;
    }

    get_last_message_sent_by_me(): Message | undefined {
        const msg_index = this._items.findLastIndex(
            (msg) => msg.sender_id === current_user.user_id,
        );
        if (msg_index === -1) {
            return undefined;
        }
        const msg = this._items[msg_index];
        return msg;
    }
}
