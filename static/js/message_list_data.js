function MessageListData(opts) {
    this.muting_enabled = opts.muting_enabled;
    if (this.muting_enabled) {
        this._all_items = [];
    }
    this._items = [];
    this._hash = {};
    this._local_only = {};
    this._selected_id = -1;

    var filter = opts.filter;
    if (filter === undefined) {
        filter = new Filter();
    }

    this.filter = filter;
}

MessageListData.prototype = {
    all_messages: function () {
        return this._items;
    },

    num_items: function () {
        return this._items.length;
    },

    empty: function () {
        return this._items.length === 0;
    },

    first: function () {
        return this._items[0];
    },

    last: function () {
        return this._items[this._items.length - 1];
    },

    select_idx: function () {
        if (this._selected_id === -1) {
            return;
        }
        var ids = _.pluck(this._items, 'id');

        var i = ids.indexOf(this._selected_id);
        if (i === -1) {
            return;
        }
        return i;
    },

    prev: function () {
        var i = this.select_idx();

        if (i === undefined) {
            return;
        }

        if (i === 0) {
            return;
        }

        return this._items[i - 1].id;
    },

    next: function () {
        var i = this.select_idx();

        if (i === undefined) {
            return;
        }

        if (i + 1 >= this._items.length) {
            return;
        }

        return this._items[i + 1].id;
    },

    is_at_end: function () {
        if (this._selected_id === -1) {
            return false;
        }

        var n = this._items.length;

        if (n === 0) {
            return false;
        }

        var last_msg = this._items[n - 1];

        return last_msg.id === this._selected_id;
    },

    nth_most_recent_id: function (n) {
        var i = this._items.length - n;
        if (i < 0) {
            return -1;
        }
        return this._items[i].id;
    },

    clear: function () {
        if (this.muting_enabled) {
            this._all_items = [];
        }

        this._items = [];
        this._hash = {};
    },

    get: function (id) {
        id = parseFloat(id);
        if (isNaN(id)) {
            return;
        }
        return this._hash[id];
    },

    clear_selected_id: function () {
        this._selected_id = -1;
    },

    selected_id: function () {
        return this._selected_id;
    },

    set_selected_id: function (id) {
        this._selected_id = id;
    },

    selected_idx: function () {
        return this._lower_bound(this._selected_id);
    },

    reset_select_to_closest: function () {
        this._selected_id = this.closest_id(this._selected_id);
    },

    is_search: function () {
        return this.filter.is_search();
    },

    _get_predicate: function () {
        // We cache this.
        if (!this.predicate) {
            this.predicate = this.filter.predicate();
        }
        return this.predicate;
    },

    valid_non_duplicated_messages: function (messages) {
        var predicate = this._get_predicate();
        var self = this;
        return _.filter(messages, function (msg) {
            return self.get(msg.id) === undefined && predicate(msg);
        });
    },

    filter_incoming: function (messages) {
        var predicate = this._get_predicate();
        return _.filter(messages, predicate);
    },

    unmuted_messages: function (messages) {
        return _.reject(messages, function (message) {
            return muting.is_topic_muted(message.stream_id, util.get_message_topic(message)) &&
                   !message.mentioned;
        });
    },

    update_items_for_muting: function () {
        if (!this.muting_enabled) {
            return;
        }
        this._items = this.unmuted_messages(this._all_items);
    },

    first_unread_message_id: function () {
        var first_unread = _.find(this._items, function (message) {
            return unread.message_unread(message);
        });

        if (first_unread) {
            return first_unread.id;
        }

        // if no unread, return the bottom message
        return this.last().id;
    },

    update_user_full_name: function (user_id, full_name) {
        _.each(this._items, function (item) {
            if (item.sender_id && item.sender_id === user_id) {
                item.sender_full_name = full_name;
            }
        });
    },

    update_user_avatar: function (user_id, avatar_url) {
        // TODO:
        // We may want to de-dup some logic with update_user_full_name,
        // especially if we want to optimize this with some kind of
        // hash that maps sender_id -> messages.
        _.each(this._items, function (item) {
            if (item.sender_id && item.sender_id === user_id) {
                item.small_avatar_url = avatar_url;
            }
        });
    },

    update_stream_name: function (stream_id, new_stream_name) {
        _.each(this._items, function (item) {
            if (item.stream_id && item.stream_id === stream_id) {
                item.display_recipient = new_stream_name;
                item.stream = new_stream_name;
            }
        });
    },

    add_messages: function (messages) {
        var self = this;
        var top_messages = [];
        var bottom_messages = [];
        var interior_messages = [];

        // If we're initially populating the list, save the messages in
        // bottom_messages regardless
        if (self.selected_id() === -1 && self.empty()) {
            var narrow_messages = self.filter_incoming(messages);
            bottom_messages = _.reject(narrow_messages, function (msg) {
                return self.get(msg.id);
            });
        } else {
            // Filter out duplicates that are already in self, and all messages
            // that fail our filter predicate
            messages = self.valid_non_duplicated_messages(messages);

            _.each(messages, function (msg) {
                // Put messages in correct order on either side of the
                // message list.  This code path assumes that messages
                // is a (1) sorted, and (2) consecutive block of
                // messages that belong in this message list; those
                // facts should be ensured by the caller.
                if (self.empty() || msg.id > self.last().id) {
                    bottom_messages.push(msg);
                } else if (msg.id < self.first().id) {
                    top_messages.push(msg);
                } else {
                    interior_messages.push(msg);
                }
            });
        }

        if (interior_messages.length > 0) {
            interior_messages = self.add_anywhere(interior_messages);
        }

        if (top_messages.length > 0) {
            top_messages = self.prepend(top_messages);
        }

        if (bottom_messages.length > 0) {
            bottom_messages = self.append(bottom_messages);
        }

        var info = {
            top_messages: top_messages,
            bottom_messages: bottom_messages,
            interior_messages: interior_messages,
        };

        return info;
    },

    add_anywhere: function (messages) {
        // Caller should have already filtered messages.
        // This should be used internally when we have
        // "interior" messages to add and can't optimize
        // things by only doing prepend or only doing append.
        var viewable_messages;
        if (this.muting_enabled) {
            this._all_items = messages.concat(this._all_items);
            this._all_items.sort(function (a, b) {return a.id - b.id;});

            viewable_messages = this.unmuted_messages(messages);
            this._items = viewable_messages.concat(this._items);

        } else {
            viewable_messages = messages;
            this._items = messages.concat(this._items);
        }

        this._items.sort(function (a, b) {return a.id - b.id;});
        this._add_to_hash(messages);
        return viewable_messages;
    },

    append: function (messages) {
        // Caller should have already filtered
        var viewable_messages;
        if (this.muting_enabled) {
            this._all_items = this._all_items.concat(messages);
            viewable_messages = this.unmuted_messages(messages);
        } else {
            viewable_messages = messages;
        }
        this._items = this._items.concat(viewable_messages);
        this._add_to_hash(messages);
        return viewable_messages;
    },

    prepend: function (messages) {
        // Caller should have already filtered
        var viewable_messages;
        if (this.muting_enabled) {
            this._all_items = messages.concat(this._all_items);
            viewable_messages = this.unmuted_messages(messages);
        } else {
            viewable_messages = messages;
        }
        this._items = viewable_messages.concat(this._items);
        this._add_to_hash(messages);
        return viewable_messages;
    },

    remove: function (messages) {
        var self = this;
        _.each(messages, function (message) {
            var stored_message = self._hash[message.id];
            if (stored_message !== undefined) {
                delete self._hash[stored_message];
            }
            delete self._local_only[message.id];
        });

        var msg_ids_to_remove = {};
        _.each(messages, function (message) {
            msg_ids_to_remove[message.id] = true;
        });
        this._items = _.filter(this._items, function (message) {
            return !msg_ids_to_remove.hasOwnProperty(message.id);
        });
        if (this.muting_enabled) {
            this._all_items = _.filter(this._all_items, function (message) {
                return !msg_ids_to_remove.hasOwnProperty(message.id);
            });
        }
    },

    // Returns messages from the given message list in the specified range, inclusive
    message_range: function (start, end) {
        if (start === -1) {
            blueslip.error("message_range given a start of -1");
        }

        var start_idx = this._lower_bound(start);
        var end_idx   = this._lower_bound(end);
        return this._items.slice(start_idx, end_idx + 1);
    },

    // Returns the index where you could insert the desired ID
    // into the message list, without disrupting the sort order
    // This takes into account the potentially-unsorted
    // nature of local message IDs in the message list
    _lower_bound: function (id) {
        var self = this;
        function less_func(msg, ref_id, a_idx) {
            if (self._is_localonly_id(msg.id)) {
                // First non-local message before this one
                var effective = self._next_nonlocal_message(self._items, a_idx,
                                                            function (idx) { return idx - 1; });
                if (effective) {
                    // Turn the 10.02 in [11, 10.02, 12] into 11.02
                    var decimal = parseFloat((msg.id % 1).toFixed(0.02));
                    var effective_id = effective.id + decimal;
                    return effective_id < ref_id;
                }
            }
            return msg.id < ref_id;
        }

        return util.lower_bound(self._items, id, less_func);
    },

    closest_id: function (id) {
        // We directly keep track of local-only messages,
        // so if we're asked for one that we know we have,
        // just return it directly
        if (this._local_only.hasOwnProperty(id)) {
            return id;
        }

        var items = this._items;

        if (items.length === 0) {
            return -1;
        }

        var closest = this._lower_bound(id);

        if (closest < items.length && id === items[closest].id) {
            return items[closest].id;
        }

        var potential_closest_matches = [];
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
            potential_closest_matches.unshift(_.last(potential_closest_matches) - 1);
            var best_match = items[closest].id;

            _.each(potential_closest_matches, function (potential_idx) {
                if (potential_idx < 0) {
                    return;
                }
                var item = items[potential_idx];

                if (item === undefined) {
                    blueslip.warn('Invalid potential_idx: ' + potential_idx);
                    return;
                }

                var potential_match = item.id;
                // If the potential id is the closest to the requested, save that one
                if (Math.abs(id - potential_match) < Math.abs(best_match - id)) {
                    best_match = potential_match;
                    closest = potential_idx;
                }
            });
        }
        return items[closest].id;
    },

    advance_past_messages: function (msg_ids) {
        // Start with the current pointer, but then keep advancing the
        // pointer while the next message's id is in msg_ids.  See trac #1555
        // for more context, but basically we are skipping over contiguous
        // messages that we have recently visited.
        var next_msg_id = 0;

        var id_set = {};

        _.each(msg_ids, function (msg_id) {
            id_set[msg_id] = true;
        });

        var idx = this.selected_idx() + 1;
        while (idx < this._items.length) {
            var msg_id = this._items[idx].id;
            if (!id_set[msg_id]) {
                break;
            }
            next_msg_id = msg_id;
            idx += 1;
        }

        if (next_msg_id > 0) {
            this.set_selected_id(next_msg_id);
        }
    },

    _add_to_hash: function (messages) {
        var self = this;
        messages.forEach(function (elem) {
            var id = parseFloat(elem.id);
            if (isNaN(id)) {
                blueslip.fatal("Bad message id");
            }
            if (self._is_localonly_id(id)) {
                self._local_only[id] = elem;
            }
            if (self._hash[id] !== undefined) {
                blueslip.error("Duplicate message added to MessageListData");
                return;
            }
            self._hash[id] = elem;
        });
    },

    _is_localonly_id: function (id) {
        return id % 1 !== 0;
    },

    _next_nonlocal_message: function (item_list, start_index, op) {
        var cur_idx = start_index;
        do {
            cur_idx = op(cur_idx);
        } while (item_list[cur_idx] !== undefined && this._is_localonly_id(item_list[cur_idx].id));
        return item_list[cur_idx];
    },

    change_message_id: function (old_id, new_id, opts) {
        // Update our local cache that uses the old id to the new id
        function message_sort_func(a, b) {return a.id - b.id;}

        if (this._hash.hasOwnProperty(old_id)) {
            var msg = this._hash[old_id];
            delete this._hash[old_id];
            this._hash[new_id] = msg;
        } else {
            return;
        }

        if (this._local_only.hasOwnProperty(old_id)) {
            if (this._is_localonly_id(new_id)) {
                this._local_only[new_id] = this._local_only[old_id];
            }
            delete this._local_only[old_id];
        }

        if (this._selected_id === old_id) {
            this._selected_id = new_id;
        }

        // If this message is now out of order, re-order and re-render
        var self = this;
        setTimeout(function () {
            var current_message = self._hash[new_id];
            var index = self._items.indexOf(current_message);

            if (index === -1) {
                if (!self.muting_enabled && opts.is_current_list()) {
                    blueslip.error("Trying to re-order message but can't find message with new_id in _items!");
                }
                return;
            }

            var next = self._next_nonlocal_message(self._items, index,
                                                   function (idx) { return idx + 1; });
            var prev = self._next_nonlocal_message(self._items, index,
                                                   function (idx) { return idx - 1; });

            if (next !== undefined && current_message.id > next.id ||
                prev !== undefined && current_message.id < prev.id) {
                blueslip.debug("Changed message ID from server caused out-of-order list, reordering");
                self._items.sort(message_sort_func);
                if (self.muting_enabled) {
                    self._all_items.sort(message_sort_func);
                }

                opts.re_render();
            }
        }, 0);
    },

    get_last_message_sent_by_me: function () {
        var msg_index = _.findLastIndex(this._items, {sender_id: page_params.user_id});
        if (msg_index === -1) {
            return;
        }
        var msg = this._items[msg_index];
        return msg;
    },
};

if (typeof module !== 'undefined') {
    module.exports = MessageListData;
}

window.MessageListData = MessageListData;
