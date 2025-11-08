/* eslint-disable no-console */

// This module is included from webpack in development mode.  To access it from
// the browser console, run:
//   var debug = require("./src/debug");

type Collision = {
    id: string;
    count: number;
    node: string;
};

export function check_duplicate_ids(): {collisions: Collision[]; total_collisions: number} {
    const ids = new Set<string>();
    const collisions: Collision[] = [];
    let total_collisions = 0;

    for (const o of document.querySelectorAll("*")) {
        if (o.id && ids.has(o.id)) {
            const el = collisions.find((c) => c.id === o.id);

            ids.add(o.id);
            total_collisions += 1;

            if (!el) {
                const tag = o.tagName.toLowerCase();
                collisions.push({
                    id: o.id,
                    count: 1,
                    node: `<${tag} class="${o.className}" id="${o.id}"></${tag}>`,
                });
            } else {
                el.count += 1;
            }
        } else if (o.id) {
            ids.add(o.id);
        }
    }

    return {
        collisions,
        total_collisions,
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
export class IterationProfiler {
    sections = new Map<string, number>();
    last_time = window.performance.now();

    iteration_start(): void {
        this.section("_iteration_overhead");
    }

    iteration_stop(): void {
        const now = window.performance.now();
        const diff = now - this.last_time;
        if (diff > 1) {
            this.sections.set(
                "_rest_of_iteration",
                (this.sections.get("_rest_of_iteration") ?? 0) + diff,
            );
        }
        this.last_time = now;
    }

    section(label: string): void {
        const now = window.performance.now();
        this.sections.set(label, (this.sections.get(label) ?? 0) + (now - this.last_time));
        this.last_time = now;
    }

    done(): void {
        this.section("_iteration_overhead");

        for (const [prop, cost] of this.sections) {
            console.log(prop, cost);
        }
    }
}
