function MessageListView(list, table_name, collapse_messages) {
    this.list = list;
    this.collapse_messages = collapse_messages;
    this._rows = {};
    this.table_name = table_name;
    if (this.table_name) {
        this.clear_table();
    }
    this._message_groups = [];

    // Half-open interval of the indices that define the current render window
    this._render_win_start = 0;
    this._render_win_end = 0;
}

(function () {

function stringify_time(time) {
    if (feature_flags.twenty_four_hour_time) {
        return time.toString('HH:mm');
    }
    return time.toString('h:mm TT');
}

function same_day(earlier_msg, later_msg) {
    var earlier_time = new XDate(earlier_msg.timestamp * 1000);
    var later_time = new XDate(later_msg.timestamp * 1000);

    return earlier_time.toDateString() === later_time.toDateString();
}

function add_display_time(group, message, prev) {
    var time = new XDate(message.timestamp * 1000);

    if (prev !== undefined) {
        var prev_time = new XDate(prev.timestamp * 1000);
        if (time.toDateString() !== prev_time.toDateString()) {
            // NB: show_date is HTML, inserted into the document without escaping.
            group.show_date = (timerender.render_date(time, prev_time))[0].outerHTML;
        }
    } else {
        group.show_date = (timerender.render_date(time))[0].outerHTML;
    }

    if (message.timestr === undefined) {
        message.timestr = stringify_time(time);
    }
}

MessageListView.prototype = {
    // Number of messages to render at a time
    _RENDER_WINDOW_SIZE: 400,
    // Number of messages away from edge of render window at which we
    // trigger a re-render
    _RENDER_THRESHOLD: 50,

    render: function MessageListView__render(messages, where, messages_are_new) {
        var list = this.list; // for convenience

        // This function processes messages into chunks with separators between them,
        // and templates them to be inserted as table rows into the DOM.

        if (messages.length === 0 || this.table_name === undefined) {
            return;
        }

        function start_group() {
            return {messages: []};
        }

        var table_name = this.table_name;
        var table = rows.get_table(table_name);
        // we we record if last_message_was_selected before updating the table
        var last_message_was_selected = rows.id(rows.last_visible()) === list.selected_id();
        var ids_where_next_is_same_sender = {};
        var prev;
        var orig_scrolltop_offset, last_message_id;
        var combined_messages, first_msg, last_msg;

        var current_group = start_group();
        var new_message_groups = [];

        var self = this;

        if (where === "bottom") {
            // Remove the trailing bookend; it'll be re-added after we do our rendering
            self.clear_trailing_bookend();
        } else if (self.selected_row().length > 0) {
            orig_scrolltop_offset = self.selected_row().offset().top;
        }

        if (where === 'top' && self.collapse_messages && this._message_groups.length > 0) {
            // Remove the top date_row, we'll re-add it after rendering
            $('.date_row:first', table).remove();

            // Delete the current top message group, and add it back in with these
            // messages, in order to collapse properly.
            //
            // This means we redraw the entire view on each backfill-update when narrowed by
            // subject, which could be a problem down the line.  For now we hope
            // that subject views will not be very big.
            var top_group = self._message_groups[0];
            rows.get_message_recipient_row(this.get_row(top_group.messages[0].id)).remove();
            messages = messages.concat(top_group.messages);
        }

        if (where !== 'top') {
            var last_row = table.find('div[zid]:last');
            last_message_id = rows.id(last_row);
            prev = self.get_message(last_message_id);
        }

        function set_template_properties(message) {
            if (message.is_stream) {
                message.background_color = stream_data.get_color(message.stream);
                message.color_class = stream_color.get_color_class(message.background_color);
                message.invite_only = stream_data.get_invite_only(message.stream);
            }
        }

        function add_message_to_group(message) {
            current_group.messages.push(message);
        }

        function finish_group() {
            if (current_group.messages.length > 0) {
                var first_message = current_group.messages[0];

                current_group.message_ids = _.pluck(current_group.messages, 'id');

                current_group.is_stream = first_message.is_stream;
                current_group.is_private = first_message.is_private;

                if (current_group.is_stream) {
                    current_group.background_color = stream_data.get_color(first_message.stream);
                    current_group.invite_only = stream_data.get_invite_only(first_message.stream);
                    current_group.subject = first_message.subject;
                } else if (current_group.is_private) {
                    current_group.pm_with_url = first_message.pm_with_url;
                    current_group.display_reply_to = first_message.display_reply_to;
                }
                current_group.display_recipient = first_message.display_recipient;
                current_group.always_visible_topic_edit = first_message.always_visible_topic_edit;
                current_group.subject_links = first_message.subject_links;

                current_group.messages[current_group.messages.length - 1].include_footer = true;

                new_message_groups.push(current_group);
            }
        }

        function add_subscription_marker(group, last_msg, first_msg) {
            if (last_msg !== undefined &&
                first_msg.historical !== last_msg.historical) {
                group.bookend_top = true;
                if (first_msg.historical) {
                    group.unsubscribed = first_msg.stream;
                    group.bookend_content = self.list.unsubscribed_bookend_content(first_msg.stream);
                } else {
                    group.subscribed = first_msg.stream;
                    group.bookend_content = self.list.subscribed_bookend_content(first_msg.stream);
                }
            }
        }

        _.each(messages, function (message) {
            message.include_recipient = false;
            message.include_footer    = false;

            if (util.same_recipient(prev, message) && self.collapse_messages &&
               prev.historical === message.historical && same_day(prev, message)) {
                add_message_to_group(message);
            } else {
                finish_group();
                current_group = start_group();
                add_message_to_group(message);

                message.include_recipient = true;
                message.subscribed = false;
                message.unsubscribed = false;

                // This home_msg_list condition can be removed
                // once we filter historical messages from the
                // home view on the server side (which requires
                // having an index on UserMessage.flags)
                if (self.list !== home_msg_list) {
                    add_subscription_marker(current_group, prev, message);
                }

                if (message.stream) {
                    message.stream_url = narrow.by_stream_uri(message.stream);
                    message.topic_url = narrow.by_stream_subject_uri(message.stream, message.subject);
                } else {
                    message.pm_with_url = narrow.pm_with_uri(message.reply_to);
                }
            }

            add_display_time(current_group, message, prev);

            message.include_sender = true;
            if (!message.include_recipient &&
                !prev.status_message &&
                util.same_sender(prev, message)) {
                message.include_sender = false;
                ids_where_next_is_same_sender[prev.id] = true;
            }

            self._add_msg_timestring(message);

            message.dom_id = table_name + message.id;

            message.small_avatar_url = ui.small_avatar_url(message);

            set_template_properties(message);

            message.contains_mention = notifications.speaking_at_me(message);
            message.unread = unread.message_unread(message);

            if (message.is_me_message) {
                // Slice the '<p>/me ' off the front, and '</p>' off the end
                message.status_message = message.content.slice(4 + 3, -4);
                message.include_sender = true;
            }
            else {
                message.status_message = false;
            }

            prev = message;
            // This home_msg_list condition can be removed
            // once we filter historical messages from the
            // home view on the server side (which requires
            // having an index on UserMessage.flags)
            if (self.list !== home_msg_list) {
                list.last_message_historical = message.historical;
            }
        });

        finish_group();

        if (new_message_groups.length === 0 ||
            new_message_groups[new_message_groups.length - 1].messages.length === 0) {
            return;
        }

        if (where === 'top') {
            // If we prepended messages that are historical, show the subscription message
            if (self._message_groups.length === 0 ||
                (prev.historical !== self._message_groups[0].messages[0].historical)) {
                if (self.list !== home_msg_list) {
                    current_group.bookend_bottom = true;
                    add_subscription_marker(current_group, prev, self._message_groups[0].messages[0]);
                }
            }
        }

        var rendered_groups = $(templates.render('message_group', {
            message_groups: new_message_groups
        }));

        var rendered_messages = [];
        _.each(rendered_groups, function (group) {
            _.each($('div.message_row', group), function (message_row) {
                var row = $(message_row);

                // Save DOM elements by id into self._rows for O(1) lookup
                if (row.hasClass('message_row')) {
                    self._rows[row.attr('zid')] = message_row;
                }

                if (row.hasClass('mention')) {
                    row.find('.user-mention').each(function () {
                        var email = $(this).attr('data-user-email');
                        if (email === '*' || email === page_params.email) {
                            $(this).addClass('user-mention-me');
                        }
                    });
                }

                rendered_messages.push(message_row);
            });
        });

        // The message that was last before this batch came in has to be
        // handled specially because we didn't just render it and
        // therefore have to lookup its associated element
        // If the previous message was part of the same block but
        // had a footer, we need to remove it.
        if (last_message_id !== undefined) {
            var row = self.get_row(last_message_id);
            if (ids_where_next_is_same_sender[last_message_id]) {
                row.find('.messagebox').addClass("next_is_same_sender");
            }
        }

        _.each(rendered_messages, function (elem){
            var e = $.Event('message_rendered.zulip', {target: elem});
            $(document).trigger(e);
        });


        function first_group_message(groups) {
            var first_group = groups[0];
            return first_group.messages[0];
        }

        function last_group_message(groups) {
            var last_group = groups[groups.length - 1];
            return last_group.messages[last_group.messages.length - 1];
        }

        function combine_adjacent_groups(before_list, after_list) {
            // Given two lists of message groups,
            // returns: one list that has the abutting groups' message list messages
            var combined_messages = before_list[before_list.length - 1].messages.concat(after_list[0].messages);

            before_list[before_list.length - 1].messages = combined_messages;

            return before_list.concat(after_list.slice(1));
        }

        if (self._message_groups.length === 0) {
            self._message_groups = new_message_groups;
            table.append(rendered_groups);
        } else {
            if (where === 'top') {
                self._message_groups = new_message_groups.concat(self._message_groups);
                table.prepend(rendered_groups);
            } else {
                // When appending messages, since we're not re-rendering the whole existing last block of messages,
                // we may have to insert the messages in the existing block. We do this if the messages would normally
                // have been in the same group originally
                last_msg = last_group_message(self._message_groups);
                first_msg = first_group_message(new_message_groups);

                if (self.collapse_messages && util.same_recipient(last_msg, first_msg) && same_day(last_msg, first_msg)) {
                    self._message_groups = combine_adjacent_groups(self._message_groups, new_message_groups);

                    // Pluck the merged messages out of our rendered group list, and insert them
                    // into the existing group div
                    var last_group = rows.get_message_recipient_row(self._rows[last_msg.id]);
                    last_group.append($('.message_row', rendered_groups[0]).remove());
                    rendered_groups.splice(0, 1);
                } else {
                    self._message_groups = self._message_groups.concat(new_message_groups);
                }

                // append the rest of the groups
                table.append(rendered_groups);
            }
        }

        list.update_trailing_bookend();

        _.each(rendered_messages, function (elem) {
            var row = $(elem);
            var id = rows.id(row);
            message_edit.maybe_show_edit(row, id);
        });

        // Must happen after the elements are inserted into the document for
        // getBoundingClientRect to work.
        // Also, the list must actually be visible.
        if (list === current_msg_list) {
            ui.condense_and_collapse(rendered_messages);
        }

        // Must happen after anything that changes the height of messages has
        // taken effect.
        if (where === 'top' && list === current_msg_list && orig_scrolltop_offset !== undefined) {
            // Restore the selected row to its original position in
            // relation to the top of the window
            viewport.set_message_offset(orig_scrolltop_offset);
            list.reselect_selected_id();
        }

        if (list === current_msg_list) {
            // Update the fade.

            var get_elements = function (message) {
                // We don't have a Message class, but we can at least hide the messy details
                // of rows.js from compose_fade.  We provide a callback function to be lazy--
                // compose_fade may not actually need the elements depending on its internal
                // state.
                var message_row = self.get_row(message.id);
                var lst = [message_row];
                if (message.include_recipient) {
                    lst.unshift(message_row.prev('.recipient_row'));
                }
                return lst;
            };

            compose_fade.update_rendered_messages(messages, get_elements);
        }

        if (list === current_msg_list && messages_are_new) {
            self._maybe_autoscroll(rendered_messages, last_message_was_selected);
        }
    },

    _add_msg_timestring: function MessageListView__add_msg_timestring(message) {
        if (message.last_edit_timestamp !== undefined) {
            // Add or update the last_edit_timestr
            var last_edit_time = new XDate(message.last_edit_timestamp * 1000);
            message.last_edit_timestr =
                (timerender.render_date(last_edit_time))[0].innerText
                + " at " + stringify_time(last_edit_time);
        }
    },

    _maybe_autoscroll: function MessageListView__maybe_autoscroll(rendered_elems, last_message_was_selected) {
        // If we are near the bottom of our feed (the bottom is visible) and can
        // scroll up without moving the pointer out of the viewport, do so, by
        // up to the amount taken up by the new message.
        var new_messages_height = 0;
        var distance_to_last_message_sent_by_me = 0;
        var id_of_last_message_sent_by_us = -1;

        // C++ iterators would have made this less painful
        _.each(rendered_elems.reverse(), function (elem) {
            // Sometimes there are non-DOM elements in rendered_elems; only
            // try to get the heights of actual trs.
            if ($(elem).is("div")) {
                new_messages_height += elem.offsetHeight;
                // starting from the last message, ignore message heights that weren't sent by me.
                if(id_of_last_message_sent_by_us > -1) {
                    distance_to_last_message_sent_by_me += elem.offsetHeight;
                    return;
                }
                var row_id = rows.id($(elem));
                // check for `row_id` NaN in case we're looking at a date row or bookend row
                if (row_id > -1 &&
                    this.get_message(row_id).sender_email === page_params.email)
                {
                    distance_to_last_message_sent_by_me += elem.offsetHeight;
                    id_of_last_message_sent_by_us = rows.id($(elem));
                }
            }
        }, this);

        // autoscroll_forever: if we're on the last message, keep us on the last message
        if (last_message_was_selected && page_params.autoscroll_forever) {
            this.list.select_id(this.list.last().id, {from_rendering: true});
            scroll_to_selected();
            this.list.reselect_selected_id();
            return;
        }

        var selected_row = this.selected_row();
        var last_visible = rows.last_visible();

        // Make sure we have a selected row and last visible row. (defensive)
        if (!(selected_row && (selected_row.length > 0) && last_visible)) {
            return;
        }

        var selected_row_offset = selected_row.offset().top;
        var info = viewport.message_viewport_info();
        var available_space_for_scroll = selected_row_offset - info.visible_top;

        // autoscroll_forever: if we've sent a message, move pointer at least that far.
        if (page_params.autoscroll_forever && id_of_last_message_sent_by_us > -1 && (rows.last_visible().offset().top - this.list.selected_row().offset().top) < (viewport.height())) {
            this.list.select_id(id_of_last_message_sent_by_us, {from_rendering: true});
            scroll_to_selected();
            return;
        }

        // Don't scroll if we can't move the pointer up.
        if (available_space_for_scroll <= 0) {
            return;
        }

        if (new_messages_height <= 0) {
            return;
        }

        // This next decision is fairly debatable.  For a big message that
        // would push the pointer off the screen, we do a partial autoscroll,
        // which has the following implications:
        //    a) user sees scrolling (good)
        //    b) user's pointer stays on screen (good)
        //    c) scroll amount isn't really tied to size of new messages (bad)
        //    d) all the bad things about scrolling for users who want messages
        //       to stay on the screen
        var scroll_amount = new_messages_height;

        if (scroll_amount > available_space_for_scroll) {
            scroll_amount = available_space_for_scroll;
        }

        // Let's work our way back to whether the user was already dealing
        // with messages off the screen, in which case we shouldn't autoscroll.
        var bottom_last_visible = last_visible.offset().top + last_visible.height();
        var bottom_old_last_visible = bottom_last_visible - new_messages_height;
        var bottom_viewport = info.visible_top + info.visible_height;

        // Exit if the user was already past the bottom.
        if (bottom_old_last_visible > bottom_viewport) {
            return;
        }

        // Ok, we are finally ready to actually scroll.
        viewport.system_initiated_animate_scroll(scroll_amount);
    },


    clear_rendering_state: function MessageListView__clear_rendering_state(clear_table) {
        this._message_groups = [];
        if (clear_table) {
            this.clear_table();
        }
        this.list.last_message_historical = false;

        this._render_win_start = 0;
        this._render_win_end = 0;
    },

    update_render_window: function MessageListView__update_render_window(selected_idx, check_for_changed) {
        var new_start = Math.max(selected_idx - this._RENDER_WINDOW_SIZE / 2, 0);
        if (check_for_changed && new_start === this._render_win_start) {
            return false;
        }

        this._render_win_start = new_start;
        this._render_win_end = Math.min(this._render_win_start + this._RENDER_WINDOW_SIZE,
                                        this.list.num_items());
        return true;
    },


    maybe_rerender: function MessageListView__maybe_rerender() {
        if (this.table_name === undefined) {
            return false;
        }

        var selected_idx = this.list.selected_idx();

        // We rerender under the following conditions:
        // * The selected message is within this._RENDER_THRESHOLD messages
        //   of the top of the currently rendered window and the top
        //   of the window does not abut the beginning of the message
        //   list
        // * The selected message is within this._RENDER_THRESHOLD messages
        //   of the bottom of the currently rendered window and the
        //   bottom of the window does not abut the end of the
        //   message list
        if (! (((selected_idx - this._render_win_start < this._RENDER_THRESHOLD)
                && (this._render_win_start !== 0)) ||
               ((this._render_win_end - selected_idx <= this._RENDER_THRESHOLD)
                && (this._render_win_end !== this.list.num_items()))))
        {
            return false;
        }

        if (!this.update_render_window(selected_idx, true)) {
            return false;
        }

        this.rerender_preserving_scrolltop();
        return true;
    },

    rerender_preserving_scrolltop: function MessageListView__rerender_preserving_scrolltop() {
        // scrolltop_offset is the number of pixels between the top of the
        // viewable window and the newly selected message
        var scrolltop_offset;
        var selected_row = this.selected_row();
        var selected_in_view = (selected_row.length > 0);
        if (selected_in_view) {
            scrolltop_offset = viewport.scrollTop() - selected_row.offset().top;
        }

        this.clear_table();
        this.render(this.list.all().slice(this._render_win_start,
                                          this._render_win_end), 'bottom');

        // If we could see the newly selected message, scroll the
        // window such that the newly selected message is at the
        // same location as it would have been before we
        // re-rendered.
        if (selected_in_view) {
            // Must get this.list.selected_row() again since it is now a new DOM element
            viewport.scrollTop(this.selected_row().offset().top + scrolltop_offset);
        }
    },

    rerender_message: function MessageListView__rerender_message(message) {
        var row = this.get_row(message.id);

        if (row === undefined) {
            blueslip.error("Cannot rerender a message that's not in this list!");
            return;
        }

        // Re-render just this one message
        var rendered_msg = $(templates.render('single_message', message));
        this._rows[message.id] = rendered_msg;
        row.replaceWith(rendered_msg);
    },

    rerender_messages: function MessageListView__rerender_messages(messages) {
        var self = this;
        _.each(messages, function (message) {
            self.rerender_message(message);
        });
    },

    append: function MessageListView__append(messages, messages_are_new) {
        var cur_window_size = this._render_win_end - this._render_win_start;
        if (cur_window_size < this._RENDER_WINDOW_SIZE) {
            var slice_to_render = messages.slice(0, this._RENDER_WINDOW_SIZE - cur_window_size);
            this.render(slice_to_render, 'bottom', messages_are_new);
            this._render_win_end += slice_to_render.length;
        }

        // If the pointer is high on the page such that there is a
        // lot of empty space below and the render window is full, a
        // newly recieved message should trigger a rerender so that
        // the new message, which will appear in the viewable area,
        // is rendered.
        this.maybe_rerender();
    },

    prepend: function MessageListView__prepend(messages) {
        this._render_win_start += messages.length;
        this._render_win_end += messages.length;

        var cur_window_size = this._render_win_end - this._render_win_start;
        if (cur_window_size < this._RENDER_WINDOW_SIZE) {
            var msgs_to_render_count = this._RENDER_WINDOW_SIZE - cur_window_size;
            var slice_to_render = messages.slice(messages.length - msgs_to_render_count);
            this.render(slice_to_render, 'top', false);
            this._render_win_start -= slice_to_render.length;
        }
    },

    rerender_the_whole_thing: function MessageListView__rerender_the_whole_thing(messages) {
        // TODO: Figure out if we can unify this with this.list.rerender().

        this.clear_rendering_state(true);

        this.update_render_window(this.list.selected_idx(), false);

        this.render(this.list.all().slice(this._render_win_start,
                                          this._render_win_end), 'bottom');
    },

    clear_table: function MessageListView_clear_table() {
        // We do not want to call .empty() because that also clears
        // jQuery data.  This does mean, however, that we need to be
        // mindful of memory leaks.
        rows.get_table(this.table_name).children().detach();
        this._rows = {};
    },

    get_row: function MessageListView_get_row(id) {
        return $(this._rows[id]);
    },

    clear_trailing_bookend: function MessageListView_clear_trailing_bookend() {
        var trailing_bookend = rows.get_table(this.table_name).find('.trailing_bookend');
        trailing_bookend.remove();
    },

    render_trailing_bookend: function MessageListView_render_trailing_bookend(trailing_bookend_content) {
        var rendered_trailing_bookend = $(templates.render('bookend', {
            bookend_content: trailing_bookend_content,
            trailing: true
        }));
        rows.get_table(this.table_name).append(rendered_trailing_bookend);
    },

    selected_row: function MessageListView_selected_row() {
        return this.get_row(this.list.selected_id());
    },

    get_message: function MessageListView_get_message(id) {
        return this.list.get(id);
    },

    change_message_id: function MessageListView_change_message_id(old_id, new_id) {
        if (this._rows[old_id] !== undefined) {
            var row = this._rows[old_id];
            delete this._rows[old_id];

            var prev_recipient_row = $(row).prev('.recipient_row');
            if (prev_recipient_row.length > 0 &&
                parseFloat(prev_recipient_row.attr('zid')) === old_id) {
                prev_recipient_row.attr('zid', new_id);

                var messages = prev_recipient_row.attr('data-messages').split();
                var fixed_messages = _.map(messages, function (msgid) {
                    if (parseFloat(msgid) === old_id) {
                        return String(new_id);
                    }
                });
                prev_recipient_row.attr('data-messages', fixed_messages.join(" "));

            }
            row.setAttribute('zid', new_id);
            row.setAttribute('id', this.table_name + new_id);
            $(row).removeClass('local');
            this._rows[new_id] = row;
        }
    }
};

}());

if (typeof module !== 'undefined') {
    module.exports = MessageListView;
}
