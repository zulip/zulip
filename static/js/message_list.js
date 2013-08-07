/*jslint nomen: true */
function MessageList(table_name, filter, opts) {
    _.extend(this, {
        collapse_messages: true,
        summarize_read: false
    }, opts);

    this._items = [];
    this._hash = {};
    this.table_name = table_name;
    this.filter = filter;
    this._selected_id = -1;
    this._message_groups = [];
    // Half-open interval of the indices that define the current render window
    this._render_win_start = 0;
    this._render_win_end = 0;

    if (this.table_name) {
        this._clear_table();
    }
    if (this.filter === undefined) {
        this.filter = new narrow.Filter();
    }
    this.narrowed = false;
    if (this.table_name === "zfilt") {
        this.narrowed = true;
    }
    return this;
}

(function () {

function add_display_time(message, prev) {
    var time = new XDate(message.timestamp * 1000);
    var include_date = false;

    if (prev !== undefined) {
        var prev_time = new XDate(prev.timestamp * 1000);
        if (time.toDateString() !== prev_time.toDateString()) {
            include_date = true;
        }
    } else {
        include_date = true;
    }

    if (include_date) {
        // NB: show_date is HTML, inserted into the document without escaping.
        message.show_date = (timerender.render_date(time))[0].outerHTML;
    } else {
        // This is run on re-render, and must remove the date if a message
        // from the same day is added above this one when scrolling up.
        message.show_date = undefined;
    }

    if (message.timestr === undefined){
        message.timestr = time.toString("HH:mm");
    }
}

MessageList.prototype = {
    get: function MessageList_get(id) {
        id = parseInt(id, 10);
        if (isNaN(id)) {
            return undefined;
        }
        return this._hash[id];
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

    _clear_table: function MessageList__clear_table() {
        // We do not want to call .empty() because that also clears
        // jQuery data.  This does mean, however, that we need to be
        // mindful of memory leaks.
        rows.get_table(this.table_name).children().detach();
    },

    _clear_rendering_state: function MessageList__clear_rendering_state(clear_table) {
        this._message_groups = [];
        if (clear_table) {
            this._clear_table();
        }
        this.last_message_historical = false;

        this._render_win_start = 0;
        this._render_win_end = 0;
    },

    clear: function  MessageList_clear(opts) {
        opts = _.extend({clear_selected_id: true}, opts);

        this._items = [];
        this._hash = {};
        this._clear_rendering_state(true);

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

        if (this.get(id) === undefined) {
            if (!opts.use_closest) {
                blueslip.error("Selected message id not in MessageList",
                               {table_name: this.table_name, id: id});
            }
            id = this.closest_id(id);
            opts.id = id;
        }

        this._selected_id = id;
        if (!opts.from_rendering) {
            this._maybe_rerender();
        }

        $(document).trigger($.Event('message_selected.zulip', opts));
    },

    selected_message: function MessageList_selected_message() {
        return this.get(this._selected_id);
    },

    selected_row: function MessageList_selected_row() {
        return rows.get(this._selected_id, this.table_name);
    },

    summary_is_selected: function () {
        return this._is_summarized_message(this.selected_message());
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

        var idx = this._selected_idx() + 1;
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

    _is_summarized_message: function (message) {
        if (!feature_flags.summarize_read_while_narrowed ||
            message === undefined || message.flags === undefined) {
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

    // Number of messages to render at a time
    _RENDER_WINDOW_SIZE: 400,
    // Number of messages away from edge of render window at which we
    // trigger a re-render
    _RENDER_THRESHOLD: 50,

    _update_render_window: function MessageList__update_render_window(selected_idx, check_for_changed) {
        var new_start = Math.max(selected_idx - this._RENDER_WINDOW_SIZE / 2, 0);
        if (check_for_changed && new_start === this._render_win_start) {
            return false;
        }

        this._render_win_start = new_start;
        this._render_win_end = Math.min(this._render_win_start + this._RENDER_WINDOW_SIZE,
                                        this._items.length);
        return true;
    },

    _selected_idx: function MessageList__selected_idx() {
        return util.lower_bound(this._items, this._selected_id,
                                function (a, b) { return a.id < b; });
    },

    _maybe_rerender: function MessageList__maybe_rerender() {
        if (this.table_name === undefined) {
            return false;
        }

        var selected_idx = this._selected_idx();

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
                && (this._render_win_end !== this._items.length))))
        {
            return false;
        }

        if (!this._update_render_window(selected_idx, true)) {
            return false;
        }

        this._rerender_preserving_scrolltop();
        return true;
    },

    _rerender_preserving_scrolltop: function MessageList__rerender_preserving_scrolltop() {
        // scrolltop_offset is the number of pixels between the top of the
        // viewable window and the newly selected message
        var scrolltop_offset;
        var selected_row = rows.get(this._selected_id, this.table_name);
        var selected_in_view = (selected_row.length > 0);
        if (selected_in_view) {
            scrolltop_offset = viewport.scrollTop() - selected_row.offset().top;
        }

        this._clear_table();
        this._render(this._items.slice(this._render_win_start,
                                       this._render_win_end), 'bottom');

        // If we could see the newly selected message, scroll the
        // window such that the newly selected message is at the
        // same location as it would have been before we
        // re-rendered.
        if (selected_in_view) {
            viewport.scrollTop(rows.get(this._selected_id, this.table_name).offset().top + scrolltop_offset);
        }
    },

    _render: function MessageList__render(messages, where, messages_are_new) {
        // This function processes messages into chunks with separators between them,
        // and templates them to be inserted as table rows into the DOM.

        if (messages.length === 0 || this.table_name === undefined) {
            return;
        }

        var self = this;
        var table_name = this.table_name;
        var table = rows.get_table(table_name);
        var messages_to_render = [];
        var ids_where_next_is_same_sender = {};
        var prev;
        var orig_scrolltop_offset, last_message_id;

        var current_group = [];
        var new_message_groups = [];

        var summary_group = {};
        var has_summary = false;
        var summary_start_id = 0;

        if (where === "bottom") {
            // Remove the trailing bookend; it'll be re-added after we do our rendering
            this.clear_trailing_bookend();
        } else if (this.selected_row().length > 0) {
            orig_scrolltop_offset = this.selected_row().offset().top - viewport.scrollTop();
        }

        if (where === 'top' && this.collapse_messages && this._message_groups.length > 0) {
            // Delete the current top message group, and add it back in with these
            // messages, in order to collapse properly.
            //
            // This means we redraw the entire view on each update when narrowed by
            // subject, which could be a problem down the line.  For now we hope
            // that subject views will not be very big.

            var top_group = this._message_groups[0];
            var top_messages = [];
            _.each(top_group, function (id) {
                rows.get(id, table_name).remove();
                // Remove any date row headers for these messages
                $('.date_row[data-zid=' + id + ']').remove();
                top_messages.push(self.get(id));
            });
            messages = messages.concat(top_messages);

            // Delete the leftover recipient label.
            table.find('.recipient_row:first').remove();
        } else {
            var last_row = table.find('tr[zid]:last');
            last_message_id = rows.id(last_row);
            prev = this.get(last_message_id);

            if (last_row.is('.summary_row')) {
                // Don't group with a summary, but don't put separators before the new message
                prev = _.pick(prev, 'timestamp', 'historical');
            }
        }

        function set_template_properties(message) {
            if (message.is_stream) {
                message.background_color = subs.get_color(message.stream);
                message.color_class = subs.get_color_class(message.background_color);
                message.invite_only = subs.get_invite_only(message.stream);
            }
        }

        function finish_summary() {
            var first = true;

            _.each(summary_group, function (summary_row) {
                summary_row.count = summary_row.messages.length;
                summary_row.message_ids = _.pluck(summary_row.messages, 'id').join(' ');
                if (first) {
                    summary_row.include_bookend = true;
                    first = false;
                }
                set_template_properties(summary_row);
                messages_to_render.push(summary_row);
                prev = summary_row;
            });

            prev.include_footer = true;

            has_summary = false;
            summary_group = {};
            prev = _.pick(prev, 'timestamp', 'historical');
        }

        _.each(messages, function (message) {
            message.include_recipient = false;
            message.include_bookend   = false;
            message.include_footer    = false;

            add_display_time(message, prev);

            if (has_summary && message.show_date) {
                finish_summary();
            }

            if (self._is_summarized_message(message)) {
                if (prev) {
                    prev.include_footer = true;
                }

                var key = util.recipient_key(message);
                if (summary_group[key] === undefined) {
                    // Start building a new summary row for messages from this recipient.
                    //
                    // Ugly: handlebars renderer only takes messages. We don't want to modify
                    // the original message, so we make a fake message based on the real one
                    // that will trigger the right part of the handlebars template and won't
                    // show the content, date, etc. from the real message.
                    summary_group[key] = $.extend({}, message, {
                        first_message_id: message.id,
                        is_summary: true,
                        include_recipient: true,
                        include_sender: false,
                        messages: [message]
                    });
                } else {
                    summary_group[key].messages.push(message);
                }
                has_summary = true;
                prev = message;
                return;
            } else if (has_summary) {
                finish_summary();
            }

            if (util.same_recipient(prev, message) && self.collapse_messages &&
               prev.historical === message.historical && !message.show_date) {
                current_group.push(message.id);
                // prev is no longer the last element in this block
                prev.include_footer = false;
            } else {
                if (current_group.length > 0) {
                    new_message_groups.push(current_group);
                }
                current_group = [message.id];

                // Add a space to the table, but not for the first element.
                message.include_recipient = true;
                message.include_bookend   = (prev !== undefined);
                if (prev !== undefined) {
                    prev.include_footer = true;
                }
                message.subscribed = false;
                message.unsubscribed = false;
                if (message.include_bookend && message.historical !== prev.historical) {
                    if (message.historical) {
                        message.unsubscribed = message.stream;
                    } else {
                        message.subscribed = message.stream;
                    }
                }
            }

            message.include_sender = true;
            if (!message.include_recipient &&
                util.same_sender(prev, message)) {
                message.include_sender = false;
                ids_where_next_is_same_sender[prev.id] = true;
            }

            if (message.last_edit_timestamp !== undefined) {
                // Add or update the last_edit_timestr
                var last_edit_time = new XDate(message.last_edit_timestamp * 1000);
                message.last_edit_timestr =
                    (timerender.render_date(last_edit_time))[0].outerHTML
                    + " " + last_edit_time.toString("HH:mm");
            }

            message.dom_id = table_name + message.id;

            message.small_avatar_url = ui.small_avatar_url(message);

            set_template_properties(message);

            message.contains_mention = notifications.speaking_at_me(message);
            message.unread = unread.message_unread(message);

            messages_to_render.push(message);
            prev = message;
            self.last_message_historical = message.historical;
        });

        if (prev) {
            prev.include_footer = true;
        }
        if (messages_to_render.length === 0) {
            return;
        }

        if (has_summary) {
            finish_summary();
        }

        if (current_group.length > 0) {
            new_message_groups.push(current_group);
        }

        if (where === 'top') {
            this._message_groups = new_message_groups.concat(this._message_groups);
        } else {
            this._message_groups = this._message_groups.concat(new_message_groups);
        }

        var rendered_elems = $(templates.render('message', {
            messages: messages_to_render,
            include_layout_row: (table.find('tr:first').length === 0),
            use_match_properties: this.filter.is_search()
        }));

        _.each(rendered_elems, function (elem) {
            var row = $(elem);
            if (! row.hasClass('message_row')) {
                return;
            }
            var id = rows.id(row);
            if (ids_where_next_is_same_sender[id]) {
                row.find('.messagebox').addClass("next_is_same_sender");
            }

            if (row.hasClass('mention')) {
                row.find('.user-mention').each(function () {
                    var email = $(this).attr('data-user-email');
                    if (email === '*' || email === page_params.email) {
                        $(this).addClass('user-mention-me');
                    }
                });
            }
        });

        // The message that was last before this batch came in has to be
        // handled specially because we didn't just render it and
        // therefore have to lookup its associated element
        // If the previous message was part of the same block but
        // had a footer, we need to remove it.
        if (last_message_id !== undefined) {
            var row = rows.get(last_message_id, table_name);
            if (ids_where_next_is_same_sender[last_message_id]) {
                row.find('.messagebox').addClass("next_is_same_sender");
            }
            // We didn't actually rerender the original last message,
            // but we might have set .include_footer=false for it in
            // the above loop since it was the previous message for
            // messages[0].  If so, we need to update the DOM.
            if (this.get(last_message_id) && ! this.get(last_message_id).include_footer) {
                row.removeClass('last_message');
            }
        }

        if (where === 'top' && table.find('.ztable_layout_row').length > 0) {
            // If we have a totally empty narrow, there may not
            // be a .ztable_layout_row.
            table.find('.ztable_layout_row').after(rendered_elems);
        } else {
            table.append(rendered_elems);

            this.update_trailing_bookend();

            // XXX: This is absolutely awful.  There is a firefox bug
            // where when table rows as DOM elements are appended (as
            // opposed to as a string) a border is sometimes added to the
            // row.  This border goes away if we add a dummy row to the
            // top of the table (it doesn't go away on any reflow,
            // though, as resizing the window doesn't make them go away).
            // So, we add an empty row and then garbage collect them
            // later when the user is idle.
            var dummy = $("<tr></tr>");
            table.find('.ztable_layout_row').after(dummy);
            $(document).idle({'idle': 1000*10,
                              'onIdle': function () {
                                  dummy.remove();
                              }});
        }

        _.each(rendered_elems, function (elem) {
            var row = $(elem);
            if (! row.hasClass('message_row')) {
                return;
            }
            var id = rows.id(row);
            message_edit.maybe_show_edit(row, id);
        });

        // Must happen after the elements are inserted into the document for
        // getBoundingClientRect to work.
        _.each(rendered_elems, ui.process_condensing);

        // Must happen after anything that changes the height of messages has
        // taken effect.
        if (where === 'top' && this === current_msg_list && orig_scrolltop_offset !== undefined) {
            // Restore the selected row to its original position in
            // relation to the top of the window
            viewport.scrollTop(this.selected_row().offset().top - orig_scrolltop_offset);
            this.select_id(this._selected_id, {from_rendering: true});
        }

        // Re-add the fading of messages that is lost when we re-render.
        compose.update_faded_messages();

        if (this === current_msg_list && messages_are_new) {
            this._maybe_autoscroll(rendered_elems);
        }
    },

    _maybe_autoscroll: function MessageList__maybe_autoscroll(rendered_elems) {

        // If we are near the bottom of our feed (the bottom is visible) and can
        // scroll up without moving the pointer out of the viewport, do so, by
        // up to the amount taken up by the new message.

        var selected_row = current_msg_list.selected_row();
        var last_visible = rows.last_visible();

        // Make sure we have a selected row and last visible row. (defensive)
        if (!(selected_row && (selected_row.length > 0) && last_visible)) {
            return;
        }

        var selected_row_offset = selected_row.offset().top;
        var info = viewport.message_viewport_info();
        var available_space_for_scroll = selected_row_offset - info.visible_top;

        // Don't scroll if we can't move the pointer up.
        if (available_space_for_scroll <= 0) {
            return;
        }

        var new_messages_height = 0;
        _.each(rendered_elems, function (elem) {
            // Sometimes there are non-DOM elements in rendered_elems; only
            // try to get the heights of actual trs.
            if ($(elem).is("tr")) {
                new_messages_height += $(elem).height();
            }
        });

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

    clear_trailing_bookend: function MessageList_clear_trailing_bookend() {
        var trailing_bookend = rows.get_table(this.table_name).find('#trailing_bookend');
        trailing_bookend.remove();
    },

    // Maintains a trailing bookend element explaining any changes in
    // your subscribed/unsubscribed status at the bottom of the
    // message list.
    update_trailing_bookend: function MessageList_update_trailing_bookend() {
        this.clear_trailing_bookend();
        if (!this.narrowed) {
            return;
        }
        var stream = narrow.stream();
        if (stream === undefined) {
            return;
        }
        var trailing_bookend_content, subscribed = subs.is_subscribed(stream);
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
            var rendered_trailing_bookend = $(templates.render('trailing_bookend', {
                trailing_bookend: trailing_bookend_content
            }));
            rows.get_table(this.table_name).append(rendered_trailing_bookend);
        }
    },

    append: function MessageList_append(messages, messages_are_new) {
        this._items = this._items.concat(messages);
        this._add_to_hash(messages);

        var cur_window_size = this._render_win_end - this._render_win_start;
        if (cur_window_size < this._RENDER_WINDOW_SIZE) {
            var slice_to_render = messages.slice(0, this._RENDER_WINDOW_SIZE - cur_window_size);
            this._render(slice_to_render, 'bottom', messages_are_new);
            this._render_win_end += slice_to_render.length;
        }

        // If the pointer is high on the page such that there is a
        // lot of empty space below and the render window is full, a
        // newly recieved message should trigger a rerender so that
        // the new message, which will appear in the viewable area,
        // is rendered.
        this._maybe_rerender();
    },

    prepend: function MessageList_prepend(messages) {
        this._items = messages.concat(this._items);
        this._add_to_hash(messages);

        this._render_win_start += messages.length;
        this._render_win_end += messages.length;

        var cur_window_size = this._render_win_end - this._render_win_start;
        if (cur_window_size < this._RENDER_WINDOW_SIZE) {
            var slice_to_render = messages.slice(0, this._RENDER_WINDOW_SIZE - cur_window_size);
            this._render(slice_to_render, 'top', false);
            this._render_win_start -= slice_to_render.length;
        }
    },

    add_and_rerender: function MessageList_add_and_rerender(messages) {
        // To add messages that might be in the interior of our
        // existing messages list, we just add the new messages and
        // then rerender the whole thing.
        this._items = messages.concat(this._items);
        this._items.sort(function (a, b) {return a.id - b.id;});
        this._add_to_hash(messages);

        this._clear_rendering_state(true);

        this._update_render_window(this._selected_idx(), false);

        this._render(this._items.slice(this._render_win_start,
                                       this._render_win_end), 'bottom');
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

    show_message_as_read: function (message, options) {
        var row = rows.get(message.id, this.table_name);
        if (options.from === 'pointer' && feature_flags.mark_read_at_bottom) {
            row.find('.unread_marker').addClass('fast_fade');
        } else {
            row.find('.unread_marker').addClass('slow_fade');
        }
        row.removeClass('unread');
    },

    rerender: function MessageList_rerender() {
        // We need to clear the rendering state, rather than just
        // doing _clear_table, since we want to potentially recollapse
        // things.
        this._clear_rendering_state(false);
        this._update_render_window(this._selected_idx(), false);
        this._rerender_preserving_scrolltop();
        if (this._selected_id !== -1) {
            this.select_id(this._selected_id);
        }
    },

    all: function MessageList_all() {
        return this._items;
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
