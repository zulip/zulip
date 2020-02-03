import * as _ from 'underscore';

type KeyValue<V> = { k: string; v: V };
type Items<V> = {
    [key: string]: KeyValue<V>;
};

export class Dict<V> {
    private _items: Items<V> = {};

    /**
     * Construct a Dict object from an array with each element set to `true`.
     * Intended for use as a set data structure.
     * @param arr - An array of keys
     */
    static from_array<V>(arr: string[]): Dict<V | true> {
        if (!(arr instanceof Array)) {
            throw new TypeError("Argument is not an array");
        }

        const dict = new Dict<V | true>();
        for (const key of arr) {
            dict.set(key, true);
        }
        return dict;
    }

    clone(): Dict<V> {
        const dict = new Dict<V>();
        dict._items = { ...this._items };
        return dict;
    }

    get(key: string): V | undefined {
        const mapping = this._items[this._munge(key)];
        if (mapping === undefined) {
            return undefined;
        }
        return mapping.v;
    }

    set(key: string, value: V): V {
        this._items[this._munge(key)] = {k: key, v: value};
        return value;
    }

    /**
     * If `key` exists in the Dict, return its value. Otherwise insert `key`
     * with a value of `value` and return the value.
     */
    setdefault(key: string, value: V): V {
        const mapping = this._items[this._munge(key)];
        if (mapping === undefined) {
            return this.set(key, value);
        }
        return mapping.v;
    }

    has(key: string): boolean {
        return _.has(this._items, this._munge(key));
    }

    del(key: string): void {
        delete this._items[this._munge(key)];
    }

    keys(): string[] {
        return _.pluck(_.values(this._items), 'k');
    }

    values(): V[] {
        return _.pluck(_.values(this._items), 'v');
    }

    items(): [string, V][] {
        return _.map(_.values(this._items),
            (mapping: KeyValue<V>): [string, V] => [mapping.k, mapping.v]);
    }

    num_items(): number {
        return _.keys(this._items).length;
    }

    is_empty(): boolean {
        return _.isEmpty(this._items);
    }

    each(f: (v: V, k?: string) => void): void {
        _.each(this._items, (mapping: KeyValue<V>) => f(mapping.v, mapping.k));
    }

    clear(): void {
        this._items = {};
    }

    // Convert keys to strings and handle undefined.
    private _munge(key: string): string | undefined {
        if (key === undefined) {
            blueslip.error("Tried to call a Dict method with an undefined key.");
            return undefined;
        }

        if (typeof key !== 'string') {
            blueslip.error("Tried to call a Dict method with a non-string.");
            key = (key as object).toString();
        }

        return ':' + key;
    }
}
