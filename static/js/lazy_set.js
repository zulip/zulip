export class LazySet {
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

    constructor(vals) {
        this.arr = vals;
        this.set = undefined;
    }

    keys() {
        if (this.set !== undefined) {
            return this.set.keys();
        }
        return this.arr.values();
    }

    _make_set() {
        if (this.set !== undefined) {
            return;
        }
        this.set = new Set(this.arr);
        this.arr = undefined;
    }

    get size() {
        if (this.set !== undefined) {
            return this.set.size;
        }

        return this.arr.length;
    }

    map(f) {
        return Array.from(this.keys(), f);
    }

    has(v) {
        this._make_set();
        const val = this._clean(v);
        return this.set.has(val);
    }

    add(v) {
        this._make_set();
        const val = this._clean(v);
        this.set.add(val);
    }

    delete(v) {
        this._make_set();
        const val = this._clean(v);
        return this.set.delete(val);
    }

    _clean(v) {
        if (typeof v !== "number") {
            blueslip.error("not a number");
            return Number.parseInt(v, 10);
        }
        return v;
    }
}
