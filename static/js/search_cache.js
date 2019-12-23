/*
exports.test = function () {
    const config = {};

    const names = [
        'vishnu',
        'steven',
        'steve',
        'stephen',
        'stephanie',
        'stefan',
        'stan',
        'sandra',
        'sally',
        'rohitt',
        'alice',
        'al',
        'adam',
    ];

    const is_good = function (query) {
        return function (name) {
            return name.startsWith(query);
        };
    };

    config.get_first_results = function (query) {
        return _.filter(names, is_good(query));
    };

    config.is_good = is_good;

    config.sort = function (names) {
        return names.sort();
    };

    config.cache_life_ms = 15000;

    config.verbose = true;

    return exports.make(config);
};
*/

exports.make = function (config) {
    /*
        Use this class ONLY if you understand
        the rules:

            - The objects you search must be mostly
              stable.  For example, something like
              `people.get_all_persons()` is stable
              enough that if we're 5 seconds old,
              and somebody joined the realm 3 seconds
              ago, it's fine if they don't show up
              in a search yet.

            - Make sure your `is_good` is prefix-friendly.
              In other words if a value "is good" for
              the search 'alice' then it should also be
              good for 'ali'.

            - Your `sort` should not depend on the query.
    */

    // boolean
    const verbose = config.verbose;

    // How do we get our main data?  Note that we let
    // have you provide a function that takes a query,
    // so that even on the first query, you can limit
    // results, rather than building us a list that we
    // filter for you.
    const get_first_results = config.get_first_results;

    // Note that is_good should return a function, so
    // it's `is_good(query)(val)` to see if a val is good.
    //
    // This lets you preprocess a query as needed in O(1)
    // time (for example, to break out termlets).
    const is_good = config.is_good;

    const sort = config.sort;

    const cache_life_ms = config.cache_life_ms;

    if (!config.cache_life_ms) {
        blueslip.error('programming error');
    }

    // These vars are what support caching:
    let filtered_data;
    let time_filtered;
    let last_query;

    function now() {
        // We work in milliseconds!
        return new Date().getTime();
    }

    function trace(s) {
        if (verbose) {
            blueslip.info(s);
        }
    }

    function is_current(time) {
        if (!time) {
            trace("first time getting data");
            return false;
        }

        const t = now();
        const elapsed = t - time;
        const current = elapsed < cache_life_ms;

        trace("is_current: " + current);
        return current;
    }

    function get_results(query, input_data) {
        trace("filtering (or re-filtering)");

        // important! actually cache the data,
        // don't use locals here
        time_filtered = now();

        const is_match = is_good(query);

        filtered_data = _.filter(input_data, is_match);

        filtered_data = sort(filtered_data);
        last_query = query;

        return filtered_data;
    }

    const search = function (query) {
        if (is_current(time_filtered)) {
            if (query === last_query) {
                trace("use cached results");
                return filtered_data;
            }

            // Optimization, don't refilter entire
            // data if we simply extended the prefix.

            if (query.startsWith(last_query)) {
                trace("use prior results then re-filter");
                return get_results(query, filtered_data);
            }

            // keep going...
        }

        trace('get first results (no cache)');
        return get_results(query, get_first_results(query));
    };

    return search;
};

window.search_cache = exports;
