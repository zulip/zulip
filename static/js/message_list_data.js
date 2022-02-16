import _ from "lodash";

import * as blueslip from "./blueslip";
import {FetchStatus} from "./fetch_status";
import {Filter} from "./filter";
import * as muted_topics from "./muted_topics";
import * as muted_users from "./muted_users";
import {page_params} from "./page_params";
import * as unread from "./unread";
import * as util from "./util";

export class MessageListData {
    constructor({excludes_muted_topics, filter = new Filter()}) {
        this.excludes_muted_topics = excludes_muted_topics;
        this._all_items = [];
        this._items = [];
        this._hash = new Map();
        this._local_only = new Set();
        this._selected_id = -1;

        this.filter = filter;
        this.fetch_status = new FetchStatus();
    }

    all_messages() {
        return this._items;
    }

    num_items() {
        return this._items.length;
    }

    empty() {
        return this._items.length === 0;
    }

    first() {
        return this._items[0];
    }

    last() {
        return this._items.at(-1);
    }

    select_idx() {
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

    prev() {
        const i = this.select_idx();

        if (i === undefined) {
            return undefined;
        }

        if (i === 0) {
            return undefined;
        }

        return this._items[i - 1].id;
    }

    next() {
        const i = this.select_idx();

        if (i === undefined) {
            return undefined;
        }

        if (i + 1 >= this._items.length) {
            return undefined;
        }

        return this._items[i + 1].id;
    }

    is_at_end() {
        if (this._selected_id === -1) {
            return false;
        }

        const n = this._items.length;

        if (n === 0) {
            return false;
        }

        const last_msg = this._items[n - 1];

        return last_msg.id === this._selected_id;
    }

    nth_most_recent_id(n) {
        const i = this._items.length - n;
        if (i < 0) {
            return -1;
        }
        return this._items[i].id;
    }

    clear() {
        this._all_items = [];
        this._items = [];
        this._hash.clear();
    }

    get(id) {
        id = Number.parseFloat(id);
        if (Number.isNaN(id)) {
            return undefined;
        }
        return this._hash.get(id);
    }

    clear_selected_id() {
        this._selected_id = -1;
    }

    selected_id() {
        return this._selected_id;
    }

    set_selected_id(id) {
        this._selected_id = id;
    }

    selected_idx() {
        return this._lower_bound(this._selected_id);
    }

    reset_select_to_closest() {
        this._selected_id = this.closest_id(this._selected_id);
    }

    is_search() {
        return this.filter.is_search();
    }
    can_mark_messages_read() {
        return this.filter.can_mark_messages_read();
    }
    _get_predicate() {
        // We cache this.
        if (!this.predicate) {
            this.predicate = this.filter.predicate();
        }
        return this.predicate;
    }

    valid_non_duplicated_messages(messages) {
        const predicate = this._get_predicate();
        return messages.filter((msg) => this.get(msg.id) === undefined && predicate(msg));
    }

    filter_incoming(messages) {
        const predicate = this._get_predicate();
        return messages.filter((message) => predicate(message));
    }

    messages_filtered_for_topic_mutes(messages) {
        if (!this.excludes_muted_topics) {
            return [...messages];
        }

        return messages.filter((message) => {
            if (message.type !== "stream") {
                return true;
            }
            return (
                !muted_topics.is_topic_muted(message.stream_id, message.topic) || message.mentioned
            );
        });
    }

    messages_filtered_for_user_mutes(messages) {
        if (this.filter.is_non_huddle_pm()) {
            // We are in a 1:1 PM narrow, so do not do any filtering.
            return [...messages];
        }

        return messages.filter((message) => {
            if (message.type !== "private") {
                return true;
            }
            const recipients = util.extract_pm_recipients(message.to_user_ids);
            if (recipients.length > 1) {
                // Huddle message
                return true;
            }

            const recipient_id = Number.parseInt(recipients[0], 10);
            return (
                !muted_users.is_user_muted(recipient_id) &&
                !muted_users.is_user_muted(message.sender_id)
            );
        });
    }

    unmuted_messages(messages) {
        return this.messages_filtered_for_topic_mutes(
            this.messages_filtered_for_user_mutes(messages),
        );
    }

    update_items_for_muting() {
        this._items = this.unmuted_messages(this._all_items);
    }

    first_unread_message_id() {
        const first_unread = this._items.find((message) => unread.message_unread(message));

        if (first_unread) {
            return first_unread.id;
        }

        // if no unread, return the bottom message
        return this.last().id;
    }

    has_unread_messages() {
        return this._items.some((message) => unread.message_unread(message));
    }

    add_messages(messages) {
        let top_messages = [];
        let bottom_messages = [];
        let interior_messages = [];

        // If we're initially populating the list, save the messages in
        // bottom_messages regardless
        if (this.selected_id() === -1 && this.empty()) {
            const narrow_messages = this.filter_incoming(messages);
            bottom_messages = narrow_messages.filter((msg) => !this.get(msg.id));
        } else {
            // Filter out duplicates that are already in self, and all messages
            // that fail our filter predicate
            messages = this.valid_non_duplicated_messages(messages);

            for (const msg of messages) {
                // Put messages in correct order on either side of the
                // message list.  This code path assumes that messages
                // is a (1) sorted, and (2) consecutive block of
                // messages that belong in this message list; those
                // facts should be ensured by the caller.
                if (this.empty() || msg.id > this.last().id) {
                    bottom_messages.push(msg);
                } else if (msg.id < this.first().id) {
                    top_messages.push(msg);
                } else {
                    interior_messages.push(msg);
                }
            }
        }

        if (interior_messages.length > 0) {
            interior_messages = this.add_anywhere(interior_messages);
        }

        if (top_messages.length > 0) {
            top_messages = this.prepend(top_messages);
        }

        if (bottom_messages.length > 0) {
            bottom_messages = this.append(bottom_messages);
        }

        const info = {
            top_messages,
            bottom_messages,
            interior_messages,
        };

        return info;
    }

    add_anywhere(messages) {
        // Caller should have already filtered messages.
        // This should be used internally when we have
        // "interior" messages to add and can't optimize
        // things by only doing prepend or only doing append.

        const viewable_messages = this.unmuted_messages(messages);

        this._all_items = messages.concat(this._all_items);
        this._all_items.sort((a, b) => a.id - b.id);

        this._items = viewable_messages.concat(this._items);
        this._items.sort((a, b) => a.id - b.id);

        this._add_to_hash(messages);
        return viewable_messages;
    }

    append(messages) {
        // Caller should have already filtered
        const viewable_messages = this.unmuted_messages(messages);

        this._all_items = this._all_items.concat(messages);
        this._items = this._items.concat(viewable_messages);

        this._add_to_hash(messages);
        return viewable_messages;
    }

    prepend(messages) {
        // Caller should have already filtered
        const viewable_messages = this.unmuted_messages(messages);

        this._all_items = messages.concat(this._all_items);
        this._items = viewable_messages.concat(this._items);

        this._add_to_hash(messages);
        return viewable_messages;
    }

    remove(message_ids) {
        const msg_ids_to_remove = new Set(message_ids);
        for (const id of msg_ids_to_remove) {
            this._hash.delete(id);
            this._local_only.delete(id);
        }

        this._items = this._items.filter((msg) => !msg_ids_to_remove.has(msg.id));
        this._all_items = this._all_items.filter((msg) => !msg_ids_to_remove.has(msg.id));
    }

    // Returns messages from the given message list in the specified range, inclusive
    message_range(start, end) {
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
    _lower_bound(id) {
        const less_func = (msg, ref_id, a_idx) => {
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

    closest_id(id) {
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

        if (closest < items.length && id === items[closest].id) {
            return items[closest].id;
        }

        const potential_closest_matches = [];
        if (closest > 0 && this._is_localonly_id(items[closest - 1].id)) {
            // Since we treated all blocks of local ids as their left-most-non-local message
            // for lower_bound purposes, find the real leftmost index (first non-local id)
            do {
                potential_closest_matches.push(closest);
                closest -= 1;
            } while (closest > 0 && this._is_localonly_id(items[closest - 1].id));
        }
        potential_closest_matches.push(closest);

        if (closest === items.length) {
            closest = closest - 1;
        } else {
            // Any of the ids that we skipped over (due to them being local-only) might be the
            // closest ID to the desired one, in case there is no exact match.
            potential_closest_matches.unshift(closest - 1);
            let best_match = items[closest].id;

            for (const potential_idx of potential_closest_matches) {
                if (potential_idx < 0) {
                    continue;
                }
                const item = items[potential_idx];

                if (item === undefined) {
                    blueslip.warn("Invalid potential_idx: " + potential_idx);
                    continue;
                }

                const potential_match = item.id;
                // If the potential id is the closest to the requested, save that one
                if (Math.abs(id - potential_match) < Math.abs(best_match - id)) {
                    best_match = potential_match;
                    closest = potential_idx;
                }
            }
        }
        return items[closest].id;
    }

    advance_past_messages(msg_ids) {
        // Start with the current pointer, but then keep advancing the
        // pointer while the next message's id is in msg_ids.  See trac #1555
        // for more context, but basically we are skipping over contiguous
        // messages that we have recently visited.
        let next_msg_id = 0;

        const id_set = new Set(msg_ids);

        let idx = this.selected_idx() + 1;
        while (idx < this._items.length) {
            const msg_id = this._items[idx].id;
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

    _add_to_hash(messages) {
        for (const elem of messages) {
            const id = Number.parseFloat(elem.id);
            if (Number.isNaN(id)) {
                throw new TypeError("Bad message id");
            }
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

    _is_localonly_id(id) {
        return id % 1 !== 0;
    }

    _next_nonlocal_message(item_list, start_index, op) {
        let cur_idx = start_index;
        do {
            cur_idx = op(cur_idx);
        } while (item_list[cur_idx] !== undefined && this._is_localonly_id(item_list[cur_idx].id));
        return item_list[cur_idx];
    }

    change_message_id(old_id, new_id) {
        // Update our local cache that uses the old id to the new id
        if (this._hash.has(old_id)) {
            const msg = this._hash.get(old_id);
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

    reorder_messages(new_id) {
        const message_sort_func = (a, b) => a.id - b.id;
        // If this message is now out of order, re-order and re-render
        const current_message = this._hash.get(new_id);
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

    get_messages_sent_by_user(user_id) {
        const msgs = _.filter(this._items, {sender_id: user_id});
        if (msgs.length === 0) {
            return [];
        }
        return msgs;
    }

    get_last_message_sent_by_me() {
        const msg_index = _.findLastIndex(this._items, {sender_id: page_params.user_id});
        if (msg_index === -1) {
            return undefined;
        }
        const msg = this._items[msg_index];
        return msg;
    }
}
