import * as blueslip from "./blueslip";

export class LazySet {
    private data:
        | {
              arr: number[];
              set: undefined;
          }
        | {
              arr: undefined;
              set: Set<number>;
          };

    /*
        This class is optimized for a very
        particular use case.

        We often have lots of subscribers on
        a stream.  We get an array from the
        backend, because it's JSON.

        Often the only operation we need
        on subscribers is to get the length,
        which is plenty cheap as an array.

        Making an array from a set is cheap
        for one stream, but it's expensive
        for all N streams at page load.

        Once somebody does an operation
        where sets are useful, such
        as has/add/delete, we convert it over
        to a set for a one-time cost.
    */

    constructor(vals: number[]) {
        this.data = {
            arr: vals,
            set: undefined,
        };
    }

    get size(): number {
        const {data} = this;
        if (data.set !== undefined) {
            return data.set.size;
        }

        return data.arr.length;
    }

    keys(): IterableIterator<number> {
        const {data} = this;
        if (data.set !== undefined) {
            return data.set.keys();
        }
        return data.arr.values();
    }

    _make_set(): Set<number> {
        if (this.data.set !== undefined) {
            return this.data.set;
        }

        this.data = {
            arr: undefined,
            set: new Set(this.data.arr),
        };

        return this.data.set;
    }

    map<T>(f: (v: number, k: number) => T): T[] {
        return [...this.keys()].map((v, k) => f(v, k));
    }

    has(v: number): boolean {
        const set = this._make_set();
        const val = this._clean(v);
        return set.has(val);
    }

    add(v: number): void {
        const set = this._make_set();
        const val = this._clean(v);
        set.add(val);
    }

    delete(v: number): boolean {
        const set = this._make_set();
        const val = this._clean(v);
        return set.delete(val);
    }

    _clean(v: number | string): number {
        if (typeof v !== "number") {
            blueslip.error("not a number", {v});
            return Number.parseInt(v, 10);
        }
        return v;
    }
}
