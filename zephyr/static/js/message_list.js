/*jslint nomen: true */
function MessageList(table_name, filter, opts) {
    $.extend(this, {collapse_messages: true}, opts);
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

function process_collapsing(index, elem) {
    var content = $(elem).find(".message_content")[0];
    var message = current_msg_list.get(rows.id($(elem)));
    if (content !== undefined && message !== undefined) {
        // If message.expanded is defined, then the user has manually
        // specified whether this message should be expanded or collapsed.
        if (message.expanded === true) {
            $(content).addClass("expanded");
            $(elem).find(".message_collapser").show();
            $(elem).find(".message_expander").hide();
            return;
        } else if (message.expanded === false) {
            $(content).removeClass("expanded");
            $(elem).find(".message_expander").show();
            $(elem).find(".message_collapser").hide();
            return;
        }

        // We've limited the height of all elements in CSS.
        // If offsetHeight < scrollHeight, then our CSS height limit has taken
        // effect and we should show an expander button.
        // If offsetHeight is only slightly smaller than scrollHeight, then we
        // would only be collapsing by a small amount, which can be annoying.
        // Instead of showing an expander button, just expand that element instead
        // of keeping it collapsed.  (This also solves a bug seen on some Mac
        // systems where offsetHeight == scrollHeight-1 for no apparent reason).
        if (content.offsetHeight === 0 && content.scrollHeight === 0) {
            return;
        } else if (content.offsetHeight + 250 < content.scrollHeight) {
            $(elem).find(".message_expander").show();
        } else if (content.offsetHeight < content.scrollHeight) {
            $(content).addClass("expanded");
        }
    }
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

    _clear_rendering_state: function MessageList__clear_rendering_state() {
        this._message_groups = [];
        this._clear_table();
        this.last_message_historical = false;
    },

    clear: function  MessageList_clear(opts) {
        opts = $.extend({}, {clear_selected_id: true}, opts);

        this._items = [];
        this._hash = {};
        this._clear_rendering_state();

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
        this._maybe_rerender();

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

        if (where === "bottom") {
            // Remove the trailing bookend; it'll be re-added after we do our rendering
            this.clear_trailing_bookend();
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
            if (util.same_recipient(prev, message) && self.collapse_messages &&
               prev.historical === message.historical) {
                current_group.push(message.id);
            } else {
                if (current_group.length > 0)
                    new_message_groups.push(current_group);
                current_group = [message.id];

                // Add a space to the table, but not for the first element.
                message.include_recipient = true;
                message.include_bookend   = (prev !== undefined);
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
                util.same_sender(prev, message) &&
                (Math.abs(message.timestamp - prev.timestamp) < 60*10)) {
                message.include_sender = false;
                ids_where_next_is_same_sender[prev.id] = true;
            }

            add_display_time(message, prev);

            message.dom_id = table_name + message.id;

            if (message.sender_email === page_params.email) {
                message.stamp = ui.get_gravatar_stamp();
            }

            if (message.is_stream) {
                message.background_color = subs.get_color(message.stream);
                message.color_class = subs.get_color_class(message.background_color);
                message.invite_only = subs.get_invite_only(message.stream);
            }

            message.contains_mention = notifications.speaking_at_me(message);

            messages_to_render.push(message);
            prev = message;
            self.last_message_historical = message.historical;
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

        var rendered_elems = $(templates.render('message', {
            messages: messages_to_render,
            include_layout_row: (table.find('tr:first').length === 0),
            use_match_properties: this.filter.is_search()
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

        $.each(rendered_elems, process_collapsing);

        // Re-add the fading of messages that is lost when we re-render.
        compose.update_faded_messages();

        // If we are near the bottom of our feed (the bottom is visible) and can
        // scroll up without moving the pointer out of the viewport, do so, by
        // up to the amount taken up by the new message.

        // Don't try to scroll if this isn't the visible message list.
        if (this !== current_msg_list) {
            return;
        }

        // Don't try to scroll when composing.
        if (compose.composing()) {
            return;
        }

        var selected_row = current_msg_list.selected_row();
        if (within_viewport(rows.last_visible()) && selected_row && (selected_row.length > 0)) {
            var viewport_offset = viewport.scrollTop();
            var new_messages_height = 0;

            $.each(rendered_elems, function() {
                // Sometimes there are non-DOM elements in rendered_elems; only
                // try to get the heights of actual trs.
                if ($(this).is("tr")) {
                    new_messages_height += $(this).height();
                }
            });

            var selected_row_offset = selected_row.offset().top;
            var available_space_for_scroll = selected_row_offset - viewport_offset -
                $("#floating_recipient_bar").height() - $("#searchbox_form").height();

            suppress_scroll_pointer_update = true; // Gets set to false in the scroll handler.
            // viewport (which is window) doesn't have a scrollTop, so scroll
            // the closest concept that does.
            $("html, body").animate({scrollTop: viewport_offset +
                                     Math.min(new_messages_height, available_space_for_scroll)});
        }
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
        var trailing_bookend_content, subscribed = subs.have(stream);
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

    append: function MessageList_append(messages) {
        this._items = this._items.concat(messages);
        this._add_to_hash(messages);

        var cur_window_size = this._render_win_end - this._render_win_start;
        if (cur_window_size < this._RENDER_WINDOW_SIZE) {
            var slice_to_render = messages.slice(0, this._RENDER_WINDOW_SIZE - cur_window_size);
            this._render(slice_to_render, 'bottom');
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
    },

    add_and_rerender: function MessageList_interior(messages) {
        // To add messages that might be in the interior of our
        // existing messages list, we just add the new messages and
        // then rerender the whole thing.
        this._items = messages.concat(this._items);
        this._items.sort(function(a, b) {return a.id - b.id;});
        this._add_to_hash(messages);

        this._clear_rendering_state();

        this._update_render_window(this._selected_idx(), false);

        this._render(this._items.slice(this._render_win_start,
                                       this._render_win_end), 'bottom');
    },

    all: function MessageList_all() {
        return this._items;
    }
};

$(document).on('message_selected.zephyr hashchange.zephyr mousewheel mousemove', function (event) {
    // TODO: Figure out how to limit this animation stop to just the autoscroll
    $("html, body").stop();
});
$(document).on('hashchange.zephyr', function (event) {
    $("tr.message_row").each(process_collapsing);
});
}());
/*jslint nomen: false */
