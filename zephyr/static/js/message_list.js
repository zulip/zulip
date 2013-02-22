/*jslint nomen: true */
function MessageList(table_name) {
    this._items = [];
    this._hash = {};
    this.table_name = table_name;
    this._selected_id = -1;
    return this;
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

    append: function MessageList_append(messages) {
        this._items = this._items.concat(messages);
        this._add_to_hash(messages);
    },

    prepend: function MessageList_prepend(messages) {
        this._items = messages.concat(this._items);
        this._add_to_hash(messages);
    },

    all: function MessageList_all() {
        return this._items;
    }
};
/*jslint nomen: false */
