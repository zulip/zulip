import * as _ from 'underscore';

/**
 * Implementation detail of the Dict class. `key` is `k` converted to a string,
 * in lowercase if the `fold_case` option is enabled.
 */
type KeyValue<K, V> = { k: K, v: V }
type Items<K, V> = {
    [key: string]: KeyValue<K, V>
}

/**
 * This class primarily exists to support the fold_case option, because so many
 * string keys in Zulip are case-insensitive (emails, stream names, topics,
 * etc.). Dict also accepts any key that can be converted to a string.
 */
export class Dict<K, V> {
    private _items: Items<K, V> = {};
    private _fold_case: boolean;

    /**
     * @param opts - setting `fold_case` to true will make `has()` and `get()`
     *               case-insensitive. `keys()` and other methods that
     *               implicitly return keys return the original casing/type
     *               of the key passed into `set()`.
     */
    constructor(opts?: {fold_case: boolean}) {
        this._fold_case = opts ? opts.fold_case : false;
    }

    /**
     * Constructs a Dict object from an existing object's keys and values.
     * @param obj - A javascript object
     * @param opts - Options to be passed to the Dict constructor
     */
    static from<V>(obj: { [key: string]: V }, opts?: {fold_case: boolean}): Dict<string, V> {
        if (typeof obj !== "object" || obj === null) {
            throw new TypeError("Cannot convert argument to Dict");
        }

        let dict = new Dict<string, V>(opts);
        for (const key in obj) {
            dict.set(key, obj[key]);
        }
        return dict;
    }

    /**
     * Construct a Dict object from an array with each element set to `true`.
     * Intended for use as a set data structure.
     * @param arr - An array of keys
     * @param opts - Options to be passed to the Dict constructor
     */
    static from_array<K, V>(arr: K[], opts?: {fold_case: boolean}): Dict<K, V | true> {
        if (!(arr instanceof Array)) {
            throw new TypeError("Argument is not an array");
        }

        let dict = new Dict<K, V | true>(opts);
        for (const key of arr) {
            dict.set(key, true);
        }
        return dict;
    }

    // Handle case-folding of keys and the empty string.
    private _munge(key: K): string | undefined {
        if (key === undefined) {
            blueslip.error("Tried to call a Dict method with an undefined key.");
            return undefined;
        }
        let str_key = ':' + key.toString();
        return this._fold_case ? str_key.toLowerCase() : str_key;
    }

    clone(): Dict<K, V> {
        let dict = new Dict<K, V>({fold_case: this._fold_case});
        dict._items = { ...this._items };
        return dict;
    }

    get(key: K): V | undefined {
        const mapping = this._items[this._munge(key)];
        if (mapping === undefined) {
            return undefined;
        }
        return mapping.v;
    }

    set(key: K, value: V): V {
        this._items[this._munge(key)] = {k: key, v: value};
        return value;
    }

    /**
     * If `key` exists in the Dict, return its value. Otherwise insert `key`
     * with a value of `value` and return the value.
     */
    setdefault(key: K, value: V): V {
        const mapping = this._items[this._munge(key)];
        if (mapping === undefined) {
            return this.set(key, value);
        }
        return mapping.v;
    }

    has(key: K): boolean {
        return _.has(this._items, this._munge(key));
    }

    del(key: K): void {
        delete this._items[this._munge(key)];
    }

    keys(): K[] {
        return _.pluck(_.values(this._items), 'k');
    }

    values(): V[] {
        return _.pluck(_.values(this._items), 'v');
    }

    items(): [K, V][] {
        return _.map(_.values(this._items),
            (mapping: KeyValue<K, V>): [K, V] => [mapping.k, mapping.v]);
    }

    num_items(): number {
        return _.keys(this._items).length;
    }

    is_empty(): boolean {
        return _.isEmpty(this._items);
    }

    each(f: (v: V, k?: K) => void) {
        _.each(this._items, (mapping: KeyValue<K, V>) => f(mapping.v, mapping.k));
    }

    clear() {
        this._items = {};
    }
}
