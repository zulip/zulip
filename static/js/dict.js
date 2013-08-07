/* Constructs a new Dict object.
 *
 * Dict() -> the new Dict will be empty
 * Dict(otherdict) -> create a shallow copy of otherdict
 * Dict(jsobj) -> create a Dict with keys corresponding to the properties of
 *                jsobj and values corresponding to the value of the appropriate
 *                property
 */
function Dict(obj) {
    var self = this;
    this._items = {};

    if (typeof obj === "object" && obj !== null) {
        if (obj instanceof Dict) {
            _.each(obj.items(), function (kv) {
                self.set(kv[0], kv[1]);
            });
        } else {
            _.each(obj, function (val, key) {
                self.set(key, val);
            });
        }
    }
}

(function () {

function munge(k) {
    return ':' + k;
}

function unmunge(k) {
    return k.substr(1);
}

Dict.prototype = _.object(_.map({
    get: function Dict_get(key) {
        return this._items[munge(key)];
    },

    set: function Dict_set(key, value) {
        return (this._items[munge(key)] = value);
    },

    has: function Dict_has(key) {
        return _.has(this._items, munge(key));
    },

    del: function Dict_del(key) {
        return delete this._items[munge(key)];
    },

    keys: function Dict_keys() {
        return _.map(_.keys(this._items), unmunge);
    },

    values: function Dict_values() {
        return _.values(this._items);
    },

    items: function Dict_items() {
        return _.map(_.pairs(this._items), function (pair) {
            return [unmunge(pair[0]), pair[1]];
        });
    }
}, function (value, key) {
    return [key, util.enforce_arity(value)];
}));

}());

if (typeof module !== 'undefined') {
    module.exports = Dict;
}
