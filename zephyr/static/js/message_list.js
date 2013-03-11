/*jslint nomen: true */
function MessageList(table_name, opts) {
    $.extend(this, {collapse_messages: true}, opts);
    this._items = [];
    this._hash = {};
    this.table_name = table_name;
    this._selected_id = -1;
    this._message_groups = [];
    // Half-open interval of the indices that define the current render window
    this._render_win_start = 0;
    this._render_win_end = 0;

    if (this.table_name) {
        this._clear_table();
    }
    return this;
}

(function () {

function add_display_time(message, prev) {
    if (message.timestr !== undefined) {
        return;
    }
    var two_digits = function (x) { return ('0' + x).slice(-2); };
    var time = new XDate(message.timestamp * 1000);
    var include_date = message.include_recipient;

    if (prev !== undefined) {
        var prev_time = new XDate(prev.timestamp * 1000);
        if (time.toDateString() !== prev_time.toDateString()) {
            include_date = true;
        }
    }

    // NB: timestr is HTML, inserted into the document without escaping.
    if (include_date) {
        message.timestr = (timerender.render_time(time))[0].outerHTML;
    } else {
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

    clear: function  MessageList_clear(opts) {
        opts = $.extend({}, {clear_selected_id: true}, opts);

        this._items = [];
        this._hash = {};
        this._message_groups = [];
        this._clear_table();

        if (opts.clear_selected_id) {
            this._selected_id = -1;
        }
    },

    selected_id: function MessageList_selected_id() {
        return this._selected_id;
    },

    select_id: function MessageList_select_id(id, opts) {
        opts = $.extend({then_scroll: false, use_closest: false}, opts, {id: id, msg_list: this});
        id = parseInt(id, 10);
        if (isNaN(id)) {
            blueslip.fatal("Bad message id");
        }
        if (this.get(id) === undefined) {
            if (!opts.use_closest) {
                blueslip.error("Selected message id not in MessageList");
            }
            id = this.closest_id(id);
            opts.id = id;
        }
        this._selected_id = id;

        // This is the number of pixels between the top of the
        // viewable window and the newly selected message
        var scrolltop_offset;
        var selected_row = rows.get(id, this.table_name);
        var new_msg_in_view = (selected_row.length > 0);
        if (new_msg_in_view) {
            scrolltop_offset = viewport.scrollTop() - selected_row.offset().top;
        }
        if (this._maybe_rerender()) {
            // If we could see the newly selected message, scroll the
            // window such that the newly selected message is at the
            // same location as it would have been before we
            // re-rendered.
            if (new_msg_in_view) {
                viewport.scrollTop(rows.get(id, this.table_name).offset().top + scrolltop_offset);
            }
        }
        $(document).trigger($.Event('message_selected.zephyr', opts));
    },

    selected_message: function MessageList_selected_message() {
        return this.get(this._selected_id);
    },

    selected_row: function MessageList_selected_row() {
        return rows.get(this._selected_id, this.table_name);
    },

    closest_id: function MessageList_closest_id(id) {
        if (this._items.length === 0) {
            return -1;
        }
        var closest = util.lower_bound(this._items, id,
                                       function (a, b) {
                                           return a.id < b;
                                       });
        if (closest === this._items.length
            || (closest !== 0
                && (id - this._items[closest - 1].id <
                    this._items[closest].id - id)))
        {
            closest = closest - 1;
        }
        return this._items[closest].id;
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

    // Number of messages to render at a time
    _RENDER_WINDOW_SIZE: 400,
    // Number of messages away from edge of render window at which we
    // trigger a re-render
    _RENDER_THRESHOLD: 50,

    _maybe_rerender: function MessageList__maybe_rerender() {
        if (this.table_name === undefined) {
            return false;
        }

        var selected_idx = util.lower_bound(this._items, this._selected_id,
                                            function (a, b) { return a.id < b; });
        var new_start;

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

        new_start = Math.max(selected_idx - this._RENDER_WINDOW_SIZE / 2, 0);
        if (new_start === this._render_win_start) {
            return false;
        }

        this._render_win_start = new_start;
        this._render_win_end = Math.min(this._render_win_start + this._RENDER_WINDOW_SIZE,
                                        this._items.length);

        this._clear_table();
        this._render(this._items.slice(this._render_win_start,
                                       this._render_win_end),
                     'bottom', true);
        return true;
    },

    _render: function MessageList__render(messages, where) {
        if (messages.length === 0 || this.table_name === undefined)
            return;

        var self = this;
        var table_name = this.table_name;
        var table = rows.get_table(table_name);
        var messages_to_render = [];
        var ids_where_next_is_same_sender = {};
        var prev;
        var last_message_id;

        var current_group = [];
        var new_message_groups = [];

        if (where === 'top' && this.collapse_messages && this._message_groups.length > 0) {
            // Delete the current top message group, and add it back in with these
            // messages, in order to collapse properly.
            //
            // This means we redraw the entire view on each update when narrowed by
            // subject, which could be a problem down the line.  For now we hope
            // that subject views will not be very big.

            var top_group = this._message_groups[0];
            var top_messages = [];
            $.each(top_group, function (index, id) {
                rows.get(id, table_name).remove();
                top_messages.push(self.get(id));
            });
            messages = messages.concat(top_messages);

            // Delete the leftover recipient label.
            table.find('.recipient_row:first').remove();
        } else {
            last_message_id = rows.id(table.find('tr[zid]:last'));
            prev = this.get(last_message_id);
        }

        $.each(messages, function (index, message) {
            message.include_recipient = false;
            message.include_bookend   = false;
            if (util.same_recipient(prev, message) && self.collapse_messages) {
                current_group.push(message.id);
            } else {
                if (current_group.length > 0)
                    new_message_groups.push(current_group);
                current_group = [message.id];

                // Add a space to the table, but not for the first element.
                message.include_recipient = true;
                message.include_bookend   = (prev !== undefined);
            }

            message.include_sender = true;
            if (!message.include_recipient &&
                util.same_sender(prev, message) &&
                (Math.abs(message.timestamp - prev.timestamp) < 60*10)) {
                message.include_sender = false;
                ids_where_next_is_same_sender[prev.id] = true;
            }

            add_display_time(message, prev);

            message.dom_id = table_name + message.id;

            if (message.sender_email === email) {
                message.stamp = ui.get_gravatar_stamp();
            }

            if (message.is_stream) {
                message.background_color = subs.get_color(message.display_recipient);
                message.color_class = subs.get_color_class(message.background_color);
                message.invite_only = subs.get_invite_only(message.display_recipient);
            }

            messages_to_render.push(message);
            prev = message;
        });

        if (messages_to_render.length === 0) {
            return;
        }

        if (current_group.length > 0)
            new_message_groups.push(current_group);

        if (where === 'top') {
            this._message_groups = new_message_groups.concat(this._message_groups);
        } else {
            this._message_groups = this._message_groups.concat(new_message_groups);
        }

        var rendered_elems = $(templates.message({
            messages: messages_to_render,
            include_layout_row: (table.find('tr:first').length === 0)
        }));

        $.each(rendered_elems, function (index, elem) {
            var row = $(elem);
            if (! row.hasClass('message_row')) {
                return;
            }
            var id = rows.id(row);
            if (ids_where_next_is_same_sender[id]) {
                row.find('.messagebox').addClass("next_is_same_sender");
            }
            if (self === narrowed_msg_list) {
                // If narrowed, we may need to highlight the message
                search.maybe_highlight_message(row);
            }
        });

        // The message that was last before this batch came in has to be
        // handled specially because we didn't just render it and
        // therefore have to lookup its associated element
        if (last_message_id !== undefined
            && ids_where_next_is_same_sender[last_message_id])
        {
            var row = rows.get(last_message_id, table_name);
            row.find('.messagebox').addClass("next_is_same_sender");
        }

        if (where === 'top' && table.find('.ztable_layout_row').length > 0) {
            // If we have a totally empty narrow, there may not
            // be a .ztable_layout_row.
            table.find('.ztable_layout_row').after(rendered_elems);
        } else {
            table.append(rendered_elems);

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

        // Re-add the fading of messages that is lost when we re-render.
        compose.update_faded_messages();
    },

    append: function MessageList_append(messages) {
        this._items = this._items.concat(messages);
        this._add_to_hash(messages);

        var cur_window_size = this._render_win_end - this._render_win_start;
        if (cur_window_size < this._RENDER_WINDOW_SIZE) {
            var slice_to_render = messages.slice(0, this._RENDER_WINDOW_SIZE - cur_window_size);
            this._render(slice_to_render, 'bottom');
            this._render_win_end += slice_to_render.length;
        }
    },

    prepend: function MessageList_prepend(messages) {
        this._items = messages.concat(this._items);
        this._add_to_hash(messages);

        this._render_win_start += messages.length;
        this._render_win_end += messages.length;
    },

    all: function MessageList_all() {
        return this._items;
    }
};
}());
/*jslint nomen: false */
