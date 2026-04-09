"use strict";

const assert = require("node:assert/strict");

const blueslip = require("./lib/zblueslip.cjs");
const {run_test} = require("./lib/test.cjs");
const {zrequire} = require("./lib/namespace.cjs");

const recurring_scheduled_messages = zrequire("recurring_scheduled_messages");

function make_recurring_scheduled_message(overrides = {}) {
    return {
        id: 1,
        content: "hello world",
        destinations: [],
        recurrence_type: "weekly",
        recurrence_days: [0, 2, 4],
        scheduled_time: "09:00",
        next_delivery: 100,
        is_active: true,
        date_created: 50,
        ...overrides,
    };
}

run_test("initialize_sorts_by_next_delivery", () => {
    recurring_scheduled_messages.initialize({
        recurring_scheduled_messages: [
            make_recurring_scheduled_message({
                id: 2,
                next_delivery: 300,
                recurrence_type: "monthly",
                recurrence_days: {type: "calendar_day", day: 15},
            }),
            make_recurring_scheduled_message({id: 1, next_delivery: 100}),
            make_recurring_scheduled_message({id: 3, next_delivery: 200}),
        ],
    });

    assert.deepEqual(
        recurring_scheduled_messages.get_all().map((rsm) => rsm.id),
        [1, 3, 2],
    );
    assert.equal(recurring_scheduled_messages.count(), 3);
    assert.equal(recurring_scheduled_messages.get_by_id(2)?.content, "hello world");
});

run_test("add_update_remove", () => {
    recurring_scheduled_messages.initialize({recurring_scheduled_messages: []});

    const original = make_recurring_scheduled_message({id: 7, next_delivery: 500});
    recurring_scheduled_messages.add(original);
    assert.equal(recurring_scheduled_messages.count(), 1);
    assert.equal(recurring_scheduled_messages.get_by_id(7)?.next_delivery, 500);

    recurring_scheduled_messages.update({
        ...original,
        next_delivery: 150,
        recurrence_type: "monthly",
        recurrence_days: {type: "ordinal_weekday", ordinal: -1, weekday: 4},
    });
    assert.equal(recurring_scheduled_messages.get_by_id(7)?.next_delivery, 150);

    recurring_scheduled_messages.remove(7);
    assert.equal(recurring_scheduled_messages.count(), 0);
});

run_test("get_by_id_logs_missing_item", () => {
    recurring_scheduled_messages.initialize({recurring_scheduled_messages: []});

    blueslip.expect("error", "Could not find recurring scheduled message");
    assert.equal(recurring_scheduled_messages.get_by_id(99), undefined);
    blueslip.reset();
});