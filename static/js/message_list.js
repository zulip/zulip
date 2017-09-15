var message_list = (function () {

var exports = {};

exports.narrowed = undefined;

exports.MessageList = function (table_name, filter, opts) {
    _.extend(this, {
        collapse_messages: true,
        muting_enabled: true,
    }, opts);
    this.view = new MessageListView(this, table_name, this.collapse_messages);

    if (this.muting_enabled) {
        this._all_items = [];
    }
    this._items = [];
    this._hash = {};
    this._local_only = {};
    this.table_name = table_name;
    this.filter = filter;
    this._selected_id = -1;

    if (this.filter === undefined) {
        this.filter = new Filter();
    }

    this.narrowed = this.table_name === "zfilt";

    this.num_appends = 0;

    return this;
};

exports.MessageList.prototype = {
    add_messages: function MessageList_add_messages(messages, opts) {
        var self = this;
        var predicate = self.filter.predicate();
        var top_messages = [];
        var bottom_messages = [];
        var interior_messages = [];

        // If we're initially populating the list, save the messages in
        // bottom_messages regardless
        if (self.selected_id() === -1 && self.empty()) {
            var narrow_messages = _.filter(messages, predicate);
            bottom_messages = _.reject(narrow_messages, function (msg) {
                return self.get(msg.id);
            });
        } else {
            _.each(messages, function (msg) {
                // Filter out duplicates that are already in self, and all messages
                // that fail our filter predicate
                if (! (self.get(msg.id) === undefined && predicate(msg))) {
                    return;
                }

                // Put messages in correct order on either side of the message list
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
            self.add_and_rerender(top_messages.concat(interior_messages).concat(bottom_messages));
            return true;
        }
        if (top_messages.length > 0) {
            self.prepend(top_messages);
        }
        if (bottom_messages.length > 0) {
            self.append(bottom_messages, opts);
        }

        if ((self === exports.narrowed) && !self.empty()) {
            // If adding some new messages to the message tables caused
            // our current narrow to no longer be empty, hide the empty
            // feed placeholder text.
            narrow.hide_empty_narrow_message();
        }

        if ((self === exports.narrowed) && !self.empty() &&
            (self.selected_id() === -1) && !opts.delay_render) {
            // And also select the newly arrived message.
            self.select_id(self.selected_id(), {then_scroll: true, use_closest: true});
        }
    },

    get: function MessageList_get(id) {
        id = parseFloat(id);
        if (isNaN(id)) {
            return undefined;
        }
        return this._hash[id];
    },

    num_items: function MessageList_num_items() {
        return this._items.length;
    },

    empty: function MessageList_empty() {
        return this._items.length === 0;
    },

    first: function MessageList_first() {
        return this._items[0];
    },

    last: function MessageList_last() {
        return this._items[this._items.length - 1];
    },

    nth_most_recent_id: function MessageList_nth_most_recent_id(n) {
        var i = this._items.length - n;
        if (i < 0) {
            return -1;
        }
        return this._items[i].id;
    },

    clear: function  MessageList_clear(opts) {
        opts = _.extend({clear_selected_id: true}, opts);

        if (this.muting_enabled) {
            this._all_items = [];
        }

        this._items = [];
        this._hash = {};
        this.view.clear_rendering_state(true);

        if (opts.clear_selected_id) {
            this._selected_id = -1;
        }
    },

    selected_id: function MessageList_selected_id() {
        return this._selected_id;
    },

    select_id: function MessageList_select_id(id, opts) {
        opts = _.extend({
                then_scroll: false,
                target_scroll_offset: undefined,
                use_closest: false,
                empty_ok: false,
                mark_read: true,
                force_rerender: false,
            }, opts, {
                id: id,
                msg_list: this,
                previously_selected: this._selected_id,
            });

        function convert_id(str_id) {
            var id = parseFloat(str_id);
            if (isNaN(id)) {
                blueslip.fatal("Bad message id " + str_id);
            }
            return id;
        }

        id = convert_id(id);

        var closest_id = this.closest_id(id);

        var error_data;

        // The name "use_closest" option is a bit legacy.  We
        // are always gonna move to the closest visible id; the flag
        // just says whether we call blueslip.error or not.  The caller
        // sets use_closest to true when it expects us to move the
        // pointer as needed, so only generate an error if the flag is
        // false.
        if (!opts.use_closest && closest_id !== id) {
            error_data = {
                table_name: this.table_name,
                id: id,
                closest_id: closest_id,
            };
            blueslip.error("Selected message id not in MessageList",
                           error_data);
        }

        if (closest_id === -1 && !opts.empty_ok) {
            error_data = {
                table_name: this.table_name,
                id: id,
                items_length: this._items.length,
            };
            blueslip.fatal("Cannot select id -1", error_data);
        }

        id = closest_id;
        opts.id = id;
        this._selected_id = id;

        if (opts.force_rerender) {
            this.rerender();
        } else if (!opts.from_rendering) {
            this.view.maybe_rerender();
        }

        $(document).trigger($.Event('message_selected.zulip', opts));
    },

    reselect_selected_id: function MessageList_select_closest_id() {
        this.select_id(this._selected_id, {from_rendering: true});
    },

    selected_message: function MessageList_selected_message() {
        return this.get(this._selected_id);
    },

    selected_row: function MessageList_selected_row() {
        return this.get_row(this._selected_id);
    },

    // Returns the index where you could insert the desired ID
    // into the message list, without disrupting the sort order
    // This takes into account the potentially-unsorted
    // nature of local message IDs in the message list
    _lower_bound: function MessageList__lower_bound(id) {
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

    closest_id: function MessageList_closest_id(id) {
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

    advance_past_messages: function MessageList_advance_past_messages(msg_ids) {
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
            this._selected_id = next_msg_id;
        }
    },

    _add_to_hash: function MessageList__add_to_hash(messages) {
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
                blueslip.error("Duplicate message added to MessageList");
                return;
            }
            self._hash[id] = elem;
        });
    },

    selected_idx: function MessageList_selected_idx() {
        return this._lower_bound(this._selected_id);
    },

    subscribed_bookend_content: function (stream_name) {
        return i18n.t("You subscribed to stream __stream__",
                      {stream: stream_name});
    },

    unsubscribed_bookend_content: function (stream_name) {
        return i18n.t("You unsubscribed from stream __stream__",
                      {stream: stream_name});
    },

    not_subscribed_bookend_content: function (stream_name) {
        return i18n.t("You are not subscribed to stream __stream__",
                      {stream: stream_name});
    },

    // Maintains a trailing bookend element explaining any changes in
    // your subscribed/unsubscribed status at the bottom of the
    // message list.
    update_trailing_bookend: function MessageList_update_trailing_bookend() {
        this.view.clear_trailing_bookend();
        if (!this.narrowed) {
            return;
        }
        var stream_name = narrow_state.stream();
        if (stream_name === undefined) {
            return;
        }
        var trailing_bookend_content;
        var show_button = true;
        var subscribed = stream_data.is_subscribed(stream_name);
        if (subscribed) {
            trailing_bookend_content = this.subscribed_bookend_content(stream_name);
        } else {
            if (!this.last_message_historical) {
                trailing_bookend_content = this.unsubscribed_bookend_content(stream_name);

                // For invite only streams or streams that no longer
                // exist, hide the resubscribe button
                var sub = stream_data.get_sub(stream_name);
                if (sub !== undefined) {
                    show_button = !sub.invite_only;
                } else {
                    show_button = false;
                }
            } else {
                trailing_bookend_content = this.not_subscribed_bookend_content(stream_name);
            }
        }
        if (trailing_bookend_content !== undefined) {
            this.view.render_trailing_bookend(trailing_bookend_content, subscribed, show_button);
        }
    },

    unmuted_messages: function MessageList_unmuted_messages(messages) {
        return _.reject(messages, function (message) {
            return muting.is_topic_muted(message.stream, message.subject) &&
                   !message.mentioned;
        });
    },

    append: function MessageList_append(messages, opts) {
        opts = _.extend({delay_render: false, messages_are_new: false}, opts);

        var viewable_messages;
        if (this.muting_enabled) {
            this._all_items = this._all_items.concat(messages);
            viewable_messages = this.unmuted_messages(messages);
        } else {
            viewable_messages = messages;
        }
        this._items = this._items.concat(viewable_messages);

        this.num_appends += 1;

        this._add_to_hash(messages);

        if (!opts.delay_render) {
            this.view.append(viewable_messages, opts.messages_are_new);
        }
    },

    prepend: function MessageList_prepend(messages) {
        var viewable_messages;
        if (this.muting_enabled) {
            this._all_items = messages.concat(this._all_items);
            viewable_messages = this.unmuted_messages(messages);
        } else {
            viewable_messages = messages;
        }
        this._items = viewable_messages.concat(this._items);
        this._add_to_hash(messages);
        this.view.prepend(viewable_messages);
    },

    add_and_rerender: function MessageList_add_and_rerender(messages) {
        // To add messages that might be in the interior of our
        // existing messages list, we just add the new messages and
        // then rerender the whole thing.

        var viewable_messages;
        if (this.muting_enabled) {
            this._all_items = messages.concat(this._all_items);
            this._all_items.sort(function (a, b) {return a.id - b.id;});

            viewable_messages = this.unmuted_messages(messages);
            this._items = viewable_messages.concat(this._items);

        } else {
            this._items = messages.concat(this._items);
        }

        this._items.sort(function (a, b) {return a.id - b.id;});
        this._add_to_hash(messages);

        this.view.rerender_the_whole_thing();
    },

    remove_and_rerender: function MessageList_remove_and_rerender(messages) {
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

        this.rerender();
    },

    show_edit_message: function MessageList_show_edit_message(row, edit_obj) {
        row.find(".message_edit_form").empty().append(edit_obj.form);
        row.find(".message_content, .status-message").hide();
        row.find(".message_edit").css("display", "block");
        row.find(".message_edit_content").autosize();
    },

    hide_edit_message: function MessageList_hide_edit_message(row) {
        row.find(".message_content, .status-message").show();
        row.find(".message_edit").hide();
        row.trigger("mouseleave");
    },

    show_edit_topic: function MessageList_show_edit_topic(recipient_row, form) {
        recipient_row.find(".topic_edit_form").empty().append(form);
        recipient_row.find('.icon-vector-pencil').hide();
        recipient_row.find(".stream_topic").hide();
        recipient_row.find(".topic_edit").show();
    },

    hide_edit_topic: function MessageList_hide_edit_topic(recipient_row) {
        recipient_row.find(".stream_topic").show();
        recipient_row.find('.icon-vector-pencil').show();
        recipient_row.find(".topic_edit").hide();
    },

    show_message_as_read: function (message, options) {
        var row = this.get_row(message.id);
        if ((options.from === 'pointer' && feature_flags.mark_read_at_bottom) ||
            options.from === "server") {
            row.find('.unread_marker').addClass('fast_fade');
        } else {
            row.find('.unread_marker').addClass('slow_fade');
        }
        row.removeClass('unread');
    },

    rerender: function MessageList_rerender() {
        // We need to clear the rendering state, rather than just
        // doing clear_table, since we want to potentially recollapse
        // things.
        this._selected_id = this.closest_id(this._selected_id);
        this.view.clear_rendering_state(false);
        this.view.update_render_window(this.selected_idx(), false);
        this.view.rerender_preserving_scrolltop();
        if (this._selected_id !== -1) {
            this.select_id(this._selected_id);
        }
    },

    rerender_after_muting_changes: function MessageList_rerender_after_muting_changes() {
        if (!this.muting_enabled) {
            return;
        }

        this._items = this.unmuted_messages(this._all_items);
        this.rerender();
    },

    all_messages: function MessageList_all_messages() {
        return this._items;
    },

    first_unread_message_id: function MessageList_first_unread_message_id() {
        var first_unread = _.find(this._items, function (message) {
            return unread.message_unread(message);
        });

        if (first_unread) {
            return first_unread.id;
        }

        // if no unread, return the bottom message
        return this.last().id;
    },

    // Returns messages from the given message list in the specified range, inclusive
    message_range: function MessageList_message_range(start, end) {
        if (start === -1) {
            blueslip.error("message_range given a start of -1");
        }

        var start_idx = this._lower_bound(start);
        var end_idx   = this._lower_bound(end);
        return this._items.slice(start_idx, end_idx + 1);
    },

    get_row: function (id) {
        return this.view.get_row(id);
    },

    _is_localonly_id: function MessageList__is_localonly_id(id) {
        return id % 1 !== 0;
    },

    _next_nonlocal_message: function MessageList__next_nonlocal_message(item_list,
                                                                        start_index, op) {
        var cur_idx = start_index;
        do {
            cur_idx = op(cur_idx);
        } while (item_list[cur_idx] !== undefined && this._is_localonly_id(item_list[cur_idx].id));
        return item_list[cur_idx];
    },

    update_user_full_name: function (user_id, full_name) {
        _.each(this._items, function (item) {
            if (item.sender_id && (item.sender_id === user_id)) {
                item.sender_full_name = full_name;
            }
        });
        this.view.rerender_the_whole_thing();
    },

    update_user_avatar: function (user_id, avatar_url) {
        // TODO:
        // We may want to de-dup some logic with update_user_full_name,
        // especially if we want to optimize this with some kind of
        // hash that maps sender_id -> messages.
        _.each(this._items, function (item) {
            if (item.sender_id && (item.sender_id === user_id)) {
                item.small_avatar_url = avatar_url;
            }
        });
        this.view.rerender_the_whole_thing();
    },

    update_stream_name: function MessageList_update_stream_name(stream_id,
                                                                new_stream_name) {
        _.each(this._items, function (item) {
            if (item.stream_id && (item.stream_id === stream_id)) {
                item.display_recipient = new_stream_name;
                item.stream = new_stream_name;
            }
        });
        this.view.rerender_the_whole_thing();
    },

    change_message_id: function MessageList_change_message_id(old_id, new_id) {
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
                if ( !self.muting_enabled && current_msg_list === self) {
                    blueslip.error("Trying to re-order message but can't find message with new_id in _items!");
                }
                return;
            }

            var next = self._next_nonlocal_message(self._items, index,
                                                   function (idx) { return idx + 1; });
            var prev = self._next_nonlocal_message(self._items, index,
                                                   function (idx) { return idx - 1; });

            if ((next !== undefined && current_message.id > next.id) ||
                (prev !== undefined && current_message.id < prev.id)) {
                blueslip.debug("Changed message ID from server caused out-of-order list, reordering");
                self._items.sort(message_sort_func);
                if (self.muting_enabled) {
                    self._all_items.sort(message_sort_func);
                }
                self.view.rerender_preserving_scrolltop();

                if (self._selected_id !== -1) {
                    self.select_id(self._selected_id);
                }
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

exports.all = new exports.MessageList(
    undefined, undefined,
    {muting_enabled: false}
);

// We stop autoscrolling when the user is clearly in the middle of
// doing something.  Be careful, though, if you try to capture
// mousemove, then you will have to contend with the autoscroll
// itself generating mousemove events.
$(document).on('message_selected.zulip zuliphashchange.zulip wheel', function () {
    message_viewport.stop_auto_scrolling();
});

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = message_list;
}
