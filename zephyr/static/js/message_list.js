/*jslint nomen: true */
function MessageList(table_name) {
    this._items = [];
    this._hash = {};
    this.table_name = table_name;
    this._selected_id = -1;
    this._message_groups = [];

    if (this.table_name) {
        this._clear_table();
    }
    return this;
}

(function () {

function add_display_time(message, prev) {
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

    // Convert to number of hours ahead/behind UTC.
    // The sign of getTimezoneOffset() is reversed wrt
    // the conventional meaning of UTC+n / UTC-n
    var tz_offset = -time.getTimezoneOffset() / 60;

    message.full_date_str = time.toLocaleDateString();
    message.full_time_str = time.toLocaleTimeString() +
        ' (UTC' + ((tz_offset < 0) ? '' : '+') + tz_offset + ')';
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
            throw (new Error("Bad message id"));
        }
        if (this.get(id) === undefined) {
            if (!opts.use_closest) {
                throw (new Error("Selected message id not in MessageList"));
            } else {
                id = this.closest_id(id);
                opts.id = id;
            }
        }
        this._selected_id = id;
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
                throw (new Error("Bad message id"));
            }
            if (self._hash[id] !== undefined) {
                throw (new Error("Duplicate message added to MessageList"));
            }
            self._hash[id] = elem;
        });
    },

    _render: function MessageList__render(messages, where, allow_collapse) {
        if (messages.length === 0)
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

        if (where === 'top' && narrow.allow_collapse() && this._message_groups.length > 0) {
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
            if (util.same_recipient(prev, message) && allow_collapse) {
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
            if (this === narrowed_msg_list) {
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
    },

    append: function MessageList_append(messages, allow_collapse) {
        this._items = this._items.concat(messages);
        this._add_to_hash(messages);
        if (this.table_name) {
            this._render(messages, 'bottom', allow_collapse);
        }
    },

    prepend: function MessageList_prepend(messages, allow_collapse) {
        this._items = messages.concat(this._items);
        this._add_to_hash(messages);
        if (this.table_name) {
            this._render(messages, 'top', allow_collapse);
        }
    },

    all: function MessageList_all() {
        return this._items;
    }
};
}());
/*jslint nomen: false */
