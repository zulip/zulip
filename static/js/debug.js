/* eslint-disable no-console */

/* WARNING:

    This file is only included when Django's DEBUG = True and your
    host is in INTERNAL_IPS.

    Do not commit any code elsewhere which uses these functions.
    They are for debugging use only.

    The file may still be accessible under other circumstances, so do
    not put sensitive information here. */

/*
      debug.print_elapsed_time("foo", foo)

    evaluates to foo() and prints the elapsed time
    to the console along with the name "foo". */

export function print_elapsed_time(name, fun) {
    const t0 = new Date().getTime();
    const out = fun();
    const t1 = new Date().getTime();
    console.log(name + ': ' + (t1 - t0) + ' ms');
    return out;
}

export function check_duplicate_ids() {
    const ids = new Set();
    const collisions = [];
    let total_collisions = 0;

    Array.prototype.slice.call(document.querySelectorAll("*")).forEach(function (o) {
        if (o.id && ids.has(o.id)) {
            const el = collisions.find(function (c) {
                return c.id === o.id;
            });

            ids.add(o.id);
            total_collisions += 1;

            if (!el) {
                const tag = o.tagName.toLowerCase();
                collisions.push({
                    id: o.id,
                    count: 1,
                    node: "<" + tag + " className='" + o.className + "' id='" + o.id + "'>" +
                          "</" + tag + ">",
                });
            } else {
                el.count += 1;
            }
        } else if (o.id) {
            ids.add(o.id);
        }
    });

    return {
        collisions: collisions,
        total_collisions: total_collisions,
    };
}

/* An IterationProfiler is used for profiling parts of looping
 * constructs (like a for loop or _.each).  You mark sections of the
 * iteration body and the IterationProfiler will sum the costs of those
 * sections over all iterations.
 *
 * Example:
 *
 *     let ip = new debug.IterationProfiler();
 *     _.each(myarray, function (elem) {
 *         ip.iteration_start();
 *
 *         cheap_op(elem);
 *         ip.section("a");
 *         expensive_op(elem);
 *         ip.section("b");
 *         another_expensive_op(elem);
 *
 *         ip.iteration_stop();
 *     });
 *     ip.done();
 *
 * The console output will look something like:
 *     _iteration_overhead 0.8950002520577982
 *     _rest_of_iteration 153.415000159293413
 *     a 2.361999897402711
 *     b 132.625999901327305
 *
 * The _rest_of_iteration section is the region of the iteration body
 * after section b.
 */
export function IterationProfiler() {
    this.sections = new Map();
    this.last_time = window.performance.now();
}

IterationProfiler.prototype = {
    iteration_start: function () {
        this.section('_iteration_overhead');
    },

    iteration_stop: function () {
        const now = window.performance.now();
        const diff = now - this.last_time;
        if (diff > 1) {
            this.sections.set(
                "_rest_of_iteration",
                (this.sections.get("_rest_of_iteration") || 0) + diff
            );
        }
        this.last_time = now;
    },

    section: function (label) {
        const now = window.performance.now();
        this.sections.set(label, (this.sections.get(label) || 0) + (now - this.last_time));
        this.last_time = now;
    },

    done: function () {
        this.section('_iteration_overhead');

        for (const [prop, cost] of this.sections) {
            console.log(prop, cost);
        }
    },
};
