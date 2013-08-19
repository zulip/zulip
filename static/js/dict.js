/* Constructs a new Dict object.
 *
 * Dict() -> the new Dict will be empty
 */
function Dict() {
    var self = this;
    this._items = {};
}

/* Constructs a new Dict object from another object.
 *
 * Dict.from(otherdict) -> create a shallow copy of otherdict
 * Dict.from(jsobj) -> create a Dict with keys corresponding to the properties of
 *                     jsobj and values corresponding to the value of the appropriate
 *                     property
 */
Dict.from = function Dict_from(obj) {
    var ret = new Dict();

    if (typeof obj === "object" && obj !== null) {
        if (obj instanceof Dict) {
            ret._items = _.clone(obj._items);
        } else {
            _.each(obj, function (val, key) {
                ret.set(key, val);
            });
        }
    } else {
        throw new TypeError("Cannot convert argument to Dict");
    }

    return ret;
};

(function () {

function munge(k) {
    return ':' + k;
}

Dict.prototype = _.object(_.map({
    get: function Dict_get(key) {
        var mapping = this._items[munge(key)];
        if (mapping === undefined) {
            return undefined;
        }
        return mapping.v;
    },

    set: function Dict_set(key, value) {
        return (this._items[munge(key)] = {k: key, v: value});
    },

    has: function Dict_has(key) {
        return _.has(this._items, munge(key));
    },

    del: function Dict_del(key) {
        return delete this._items[munge(key)];
    },

    keys: function Dict_keys() {
        return _.pluck(_.values(this._items), 'k');
    },

    values: function Dict_values() {
        return _.pluck(_.values(this._items), 'v');
    },

    items: function Dict_items() {
        return _.map(_.values(this._items), function (mapping) {
            return [mapping.k, mapping.v];
        });
    },

    // Iterates through the Dict calling f(value, key) for each (key, value) pair in the Dict
    each: function Dict_each(f) {
        return _.each(this._items, function (mapping) {
            f(mapping.v, mapping.k);
        });
    }
}, function (value, key) {
    return [key, util.enforce_arity(value)];
}));

}());

if (typeof module !== 'undefined') {
    module.exports = Dict;
}
