/*jslint nomen: true */
function MessageList(table_name, filter, opts) {
    _.extend(this, {
        collapse_messages: true,
        muting_enabled: true,
        summarize_read: false
    }, opts);
    this.view = new MessageListView(this, table_name, this.collapse_messages);

    if (this.muting_enabled) {
        this._all_items = [];
    }
    this._items = [];
    this._hash = {};
    this.table_name = table_name;
    this.filter = filter;
    this._selected_id = -1;

    if (this.filter === undefined) {
        this.filter = new Filter();
    }
    this.narrowed = false;
    if (this.table_name === "zfilt") {
        this.narrowed = true;
    }

    this.num_appends = 0;
    this.min_id_exempted_from_summaries = -1;
    return this;
}

(function () {

MessageList.prototype = {
    add_messages: function MessageList_add_messages(messages, messages_are_new) {
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
            self.append(bottom_messages, messages_are_new);
        }

        if ((self === narrowed_msg_list) && !self.empty() &&
            (self.selected_id() === -1)) {
            // If adding some new messages to the message tables caused
            // our current narrow to no longer be empty, hide the empty
            // feed placeholder text.
            narrow.hide_empty_narrow_message();
            // And also select the newly arrived message.
            self.select_id(self.selected_id(), {then_scroll: true, use_closest: true});
        }
    },

    get: function MessageList_get(id) {
        id = parseInt(id, 10);
        if (isNaN(id)) {
            return undefined;
        }
        return this._hash[id];
    },

    get_messages: function MessageList_get_mesages() {
        return this._items;
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
        } else {
            return this._items[i].id;
        }
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
                use_closest: false,
                mark_read: true
            }, opts, {
                id: id,
                msg_list: this,
                previously_selected: this._selected_id
            });

        id = parseInt(id, 10);
        if (isNaN(id)) {
            blueslip.fatal("Bad message id");
        }

        var closest_id = this.closest_id(id);

        // The name "use_closest" option is a bit legacy.  We
        // are always gonna move to the closest visible id; the flag
        // just says whether we call blueslip.error or not.  The caller
        // sets use_closest to true when it expects us to move the
        // pointer as needed, so only generate an error if the flag is
        // false.
        if (!opts.use_closest && closest_id !== id) {
            blueslip.error("Selected message id not in MessageList",
                           {table_name: this.table_name, id: id});
        }

        if (closest_id === -1) {
            blueslip.fatal("Cannot select id -1", {table_name: this.table_name});
        }

        id = closest_id;
        opts.id = id;
        this._selected_id = id;

        if (!opts.from_rendering) {
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

    on_expandable_row: function MessageList_on_expandable_row() {
        return this.view.is_expandable_row(this.selected_row());
    },

    closest_id: function MessageList_closest_id(id) {
        var items = this._items;

        if (items.length === 0) {
            return -1;
        }

        var closest = util.lower_bound(items, id,
                                       function (a, b) {
                                           return a.id < b;
                                       });

        if (closest === items.length
            || (closest !== 0
                && (id - items[closest - 1].id <
                    items[closest].id - id)))
        {
            closest = closest - 1;
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
            ++idx;
        }

        if (next_msg_id > 0) {
            this._selected_id = next_msg_id;
        }
    },

    _add_to_hash: function MessageList__add_to_hash(messages) {
        var self = this;
        messages.forEach(function (elem) {
            var id = parseInt(elem.id, 10);
            if (isNaN(id)) {
                blueslip.fatal("Bad message id");
            }
            if (self._hash[id] !== undefined) {
                blueslip.error("Duplicate message added to MessageList");
                return;
            }
            self._hash[id] = elem;
        });
    },

    is_summarized_message: function (message) {
        if (!feature_flags.summarize_read_while_narrowed ||
            message === undefined || message.flags === undefined) {
            return false;
        }
        if (message.id >= this.min_id_exempted_from_summaries) {
            return false;
        }
        if (this.summarize_read === 'home') {
            return message.flags.indexOf('summarize_in_home') !== -1;
        } else if (this.summarize_read === 'stream' ) {
            return message.flags.indexOf('summarize_in_stream') !== -1;
        } else {
            return false;
        }
    },

    summary_adjective: function (message) {
        if (_.contains(message.flags, 'force_collapse')) {
            return 'collapsed';
        } else if (!_.contains(message.flags, 'force_expand')) {
            if (this.is_summarized_message(message)) {
                return 'read';
            }
        }
        return null;
    },

    selected_idx: function MessageList_selected_idx() {
        return util.lower_bound(this._items, this._selected_id,
                                function (a, b) { return a.id < b; });
    },

    // Maintains a trailing bookend element explaining any changes in
    // your subscribed/unsubscribed status at the bottom of the
    // message list.
    update_trailing_bookend: function MessageList_update_trailing_bookend() {
        this.view.clear_trailing_bookend();
        if (!this.narrowed) {
            return;
        }
        var stream = narrow.stream();
        if (stream === undefined) {
            return;
        }
        var trailing_bookend_content, subscribed = stream_data.is_subscribed(stream);
        if (subscribed) {
            if (this.last_message_historical) {
                trailing_bookend_content = "--- Subscribed to stream " + stream + " ---";
            }
        } else {
            if (!this.last_message_historical) {
                trailing_bookend_content = "--- Unsubscribed from stream " + stream + " ---";
            } else {
                trailing_bookend_content = "--- Not subscribed to stream " + stream + " ---";
            }
        }
        if (trailing_bookend_content !== undefined) {
            this.view.render_trailing_bookend(trailing_bookend_content);
        }
    },

    start_summary_exemption: function MessageList_start_summary_exemption() {
        var num_exempt = 8;
        this.min_id_exempted_from_summaries = this.nth_most_recent_id(num_exempt);
    },

    unmuted_messages: function MessageList_unmuted_messages(messages) {
        return _.reject(messages, function (message) {
            return muting.is_topic_muted(message.stream, message.subject);
        });
    },

    append: function MessageList_append(messages, messages_are_new) {
        var viewable_messages;
        if (this.muting_enabled) {
            this._all_items = this._all_items.concat(messages);
            viewable_messages = this.unmuted_messages(messages);
        } else {
            viewable_messages = messages;
        }
        this._items = this._items.concat(viewable_messages);

        if (this.num_appends === 0) {
            // We can't figure out which messages need to be exempt from
            // summarization until we get the first batch of messages.
            this.start_summary_exemption();
        }
        this.num_appends += 1;

        this._add_to_hash(messages);

        this.view.append(viewable_messages, messages_are_new);
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

    show_edit_message: function MessageList_show_edit_message(row, edit_obj) {
        row.find(".message_edit_form").empty().append(edit_obj.form);
        row.find(".message_content").hide();
        row.find(".message_edit").show();
        row.find(".message_edit_content").autosize();
    },

    hide_edit_message: function MessageList_hide_edit_message(row) {
        row.find(".message_content").show();
        row.find(".message_edit").hide();
    },

    show_edit_topic: function MessageList_show_edit_topic(recipient_row, form) {
        recipient_row.find(".topic_edit_form").empty().append(form);
        recipient_row.find(".stream_topic").hide();
        recipient_row.find(".topic_edit").show();
    },

    hide_edit_topic: function MessageList_hide_edit_topic(recipient_row) {
        recipient_row.find(".stream_topic").show();
        recipient_row.find(".topic_edit").hide();
    },

    show_message_as_read: function (message, options) {
        var row = this.get_row(message.id);
        if (options.from === 'pointer' && feature_flags.mark_read_at_bottom) {
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

    all: function MessageList_all() {
        return this._items;
    },

    get_row: function (id) {
        return this.view.get_row(id);
    },

    change_display_recipient: function MessageList_change_display_recipient(old_recipient,
                                                                            new_recipient) {
        // This method only works for streams.
        _.each(this._items, function (item) {
            if (item.display_recipient === old_recipient) {
                item.display_recipient = new_recipient;
                item.stream = new_recipient;
            }
        });
        this.view.rerender_the_whole_thing();
    }
};

// We stop autoscrolling when the user is clearly in the middle of
// doing something.  Be careful, though, if you try to capture
// mousemove, then you will have to contend with the autoscroll
// itself generating mousemove events.
$(document).on('message_selected.zulip hashchange.zulip mousewheel', function (event) {
    viewport.stop_auto_scrolling();
});
}());
/*jslint nomen: false */
if (typeof module !== 'undefined') {
    module.exports = MessageList;
}
