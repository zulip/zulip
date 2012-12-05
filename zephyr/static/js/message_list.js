/*jslint nomen: true */
function MessageList(table_name) {
    this._items = [];
    this._hash = {};
    this.table_name = table_name;
    return this;
}

MessageList.prototype = {
    get: function MessageList_get(id) {
        id = parseInt(id, 10);
        if (isNaN(id)) {
            return false;
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
