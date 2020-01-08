import * as _ from 'underscore';

/*
    Use this class to manage keys where you don't care
    about case (i.e. case-insensitive).

    Keys for FoldDict should be strings.  We "fold" all
    casings of "alice" (e.g. "ALICE", "Alice", "ALIce", etc.)
    to "alice" as the key.

    Examples of case-insensitive data in Zulip are:
        - emails
        - stream names
        - topics
        - etc.
 */

export class FoldDict<V> {
    private _map = new Map();

    // For historical reasons, we keep the last
    // unmunged value of any key.  Any function
    // returning keys should maybe just return
    // the munged (lowercase) value of the key.
    private _keymap = new Map();

    get(key: string): V | undefined {
        return this._map.get(this._munge(key));
    }

    set(key: string, value: V): V {
        const k = this._munge(key);
        this._map.set(k, value);
        this._keymap.set(k, key);
        return value;
    }

    has(key: string): boolean {
        return this._map.has(this._munge(key));
    }

    del(key: string): void {
        this._map.delete(this._munge(key));
    }

    keys(): string[] {
        const res = [];

        for (const key of this._map.keys()) {
            res.push(this._keymap.get(key));
        }

        return res;
    }

    values(): V[] {
        return Array.from(this._map.values());
    }

    items(): [string, V][] {
        const res: [string, V][] = [];

        for (const k of this._map.keys()) {
            const key = this._keymap.get(k);
            res.push([key, this._map.get(k)]);
        }
        return res;
    }

    num_items(): number {
        return this._map.size;
    }

    is_empty(): boolean {
        return this._map.size === 0;
    }

    each(f: (v: V, k?: string) => void): void {
        for (const k of this._map.keys()) {
            const key = this._keymap.get(k);
            f(this._map.get(k), key);
        }
    }

    clear(): void {
        this._map.clear();
    }

    // Handle case-folding of keys and the empty string.
    private _munge(key: string): string | undefined {
        if (key === undefined) {
            blueslip.error("Tried to call a FoldDict method with an undefined key.");
            return undefined;
        }

        const str_key = key.toString().toLowerCase();
        return str_key;
    }
}
