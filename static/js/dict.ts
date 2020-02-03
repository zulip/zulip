export class Dict<V> {
    private _items: Map<string, V> = new Map();

    get(key: string): V | undefined {
        return this._items.get(this._munge(key));
    }

    set(key: string, value: V): Dict<V> {
        this._items.set(this._munge(key), value);
        return this;
    }

    has(key: string): boolean {
        return this._items.has(this._munge(key));
    }

    delete(key: string): void {
        this._items.delete(this._munge(key));
    }

    keys(): Iterator<string> {
        return this._items.keys();
    }

    values(): Iterator<V> {
        return this._items.values();
    }

    [Symbol.iterator](): Iterator<[string, V]> {
        return this._items.entries();
    }

    get size(): number {
        return this._items.size;
    }

    clear(): void {
        this._items.clear();
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

        return key;
    }
}
