import * as _ from 'underscore';

type KeyValue<K, V> = { k: K; v: V };
type Items<K, V> = {
    [key: string]: KeyValue<K, V>;
};

export class Dict<K, V> {
    private _items: Items<K, V> = {};

    /**
     * Constructs a Dict object from an existing object's keys and values.
     * @param obj - A javascript object
     */
    static from<V>(obj: { [key: string]: V }): Dict<string, V> {
        if (typeof obj !== "object" || obj === null) {
            throw new TypeError("Cannot convert argument to Dict");
        }

        const dict = new Dict<string, V>();
        _.each(obj, function (val: V, key: string) {
            dict.set(key, val);
        });

        return dict;
    }

    /**
     * Construct a Dict object from an array with each element set to `true`.
     * Intended for use as a set data structure.
     * @param arr - An array of keys
     */
    static from_array<K, V>(arr: K[]): Dict<K, V | true> {
        if (!(arr instanceof Array)) {
            throw new TypeError("Argument is not an array");
        }

        const dict = new Dict<K, V | true>();
        for (const key of arr) {
            dict.set(key, true);
        }
        return dict;
    }

    clone(): Dict<K, V> {
        const dict = new Dict<K, V>();
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

    each(f: (v: V, k?: K) => void): void {
        _.each(this._items, (mapping: KeyValue<K, V>) => f(mapping.v, mapping.k));
    }

    clear(): void {
        this._items = {};
    }

    // Convert keys to strings and handle undefined.
    private _munge(key: K): string | undefined {
        if (key === undefined) {
            blueslip.error("Tried to call a Dict method with an undefined key.");
            return undefined;
        }
        const str_key = ':' + key.toString();
        return str_key;
    }
}
