exports.LazySet = function (vals) {
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
    const self = {};
    self.arr = vals;
    self.set = undefined;

    self.keys = function () {
        if (self.set !== undefined) {
            return Array.from(self.set);
        }
        return self.arr;
    };

    function make_set() {
        if (self.set !== undefined) {
            return;
        }
        self.set = new Set(self.arr);
        self.arr = undefined;
    }

    self.num_items = function () {
        if (self.set !== undefined) {
            return self.set.size;
        }

        return self.arr.length;
    };

    self.map = function (f) {
        return _.map(self.keys(), f);
    };

    self.has = function (v) {
        make_set();
        const val = self._clean(v);
        return self.set.has(val);
    };

    self.add = function (v) {
        make_set();
        const val = self._clean(v);
        self.set.add(val);
    };

    self.delete = function (v) {
        make_set();
        const val = self._clean(v);
        return self.set.delete(val);
    };

    self._clean = function (v) {
        if (typeof v !== 'number') {
            blueslip.error('not a number');
            return parseInt(v, 10);
        }
        return v;
    };


    return self;
};
