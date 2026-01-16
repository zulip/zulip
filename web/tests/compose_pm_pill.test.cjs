"use strict";

const assert = require("node:assert/strict");

const {make_realm} = require("./lib/example_realm.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const input_pill = mock_esm("../src/input_pill");
const people = zrequire("people");

const compose_pm_pill = zrequire("compose_pm_pill");
const {set_realm} = zrequire("state_data");

set_realm(make_realm());

let pills = {
    pill: {},
};

run_test("pills", ({override}) => {
    const me = {
        email: "me@example.com",
        user_id: 30,
        full_name: "Me Myself",
        date_joined: new Date(),
    };

    const othello = {
        user_id: 1,
        email: "othello@example.com",
        full_name: "Othello",
    };

    const iago = {
        email: "iago@zulip.com",
        user_id: 2,
        full_name: "Iago",
    };

    const hamlet = {
        email: "hamlet@example.com",
        user_id: 3,
        full_name: "Hamlet",
    };

    people.initialize_current_user(me.user_id);
    people.add_active_user(me);
    people.add_active_user(othello);
    people.add_active_user(iago);
    people.add_active_user(hamlet);

    const $recipient_stub = $("#private_message_recipient");
    const pill_container_stub = "pill-container";
    $recipient_stub.set_parent(pill_container_stub);
    let create_item_handler;

    const all_pills = new Map();

    pills.appendValidatedData = (item) => {
        const id = item.user_id;
        assert.ok(!all_pills.has(id));
        all_pills.set(id, item);
    };
    pills.items = () => [...all_pills.values()];

    let text_cleared;
    pills.clear_text = () => {
        text_cleared = true;
    };

    let pills_cleared;
    pills.clear = () => {
        pills_cleared = true;
        pills = {
            pill: {},
        };
        all_pills.clear();
    };

    let appendValue_called;
    pills.appendValue = function (value) {
        appendValue_called = true;
        assert.equal(value, othello.user_id.toString());
        this.appendValidatedData(othello);
    };

    function test_create_item(handler) {
        (function test_rejection_path() {
            const item = handler(othello.user_id, pills.items());
            assert.equal(item, undefined);
        })();

        (function test_success_path() {
            const res = handler(iago.user_id, pills.items());
            assert.equal(typeof res, "object");
            assert.equal(res.user_id, iago.user_id);
            assert.equal(res.full_name, iago.full_name);
        })();

        (function test_deactivated_pill() {
            people.deactivate(iago);
            const res = handler(iago.user_id, pills.items());
            assert.equal(typeof res, "object");
            assert.equal(res.user_id, iago.user_id);
            assert.equal(res.full_name, iago.full_name);
            assert.ok(res.deactivated);
            people.add_active_user(iago);
        })();
    }

    function input_pill_stub(opts) {
        assert.equal(opts.$container, pill_container_stub);
        create_item_handler = opts.create_item_from_text;
        assert.ok(create_item_handler);
        return pills;
    }

    override(input_pill, "create", input_pill_stub);

    // We stub the return value of input_pill.create(), manually add widget functions to it.
    pills.onPillCreate = (callback) => {
        callback();
    };
    pills.onPillRemove = (callback) => {
        callback();
    };

    let on_pill_create_or_remove_call_count = 0;
    compose_pm_pill.initialize({
        on_pill_create_or_remove() {
            on_pill_create_or_remove_call_count += 1;
        },
    });
    assert.ok(compose_pm_pill.widget);
    // Called two times via our overridden onPillCreate and onPillRemove methods.
    // Normally these would be called via `set_from_typeahead` method.
    assert.equal(on_pill_create_or_remove_call_count, 2);

    compose_pm_pill.set_from_typeahead(othello);
    compose_pm_pill.set_from_typeahead(hamlet);

    let user_ids = compose_pm_pill.get_user_ids();
    assert.deepEqual(user_ids, [othello.user_id, hamlet.user_id]);

    const user_ids_string = compose_pm_pill.get_user_ids_string();
    assert.equal(user_ids_string, "1,3");

    const emails = compose_pm_pill.get_emails();
    assert.equal(emails, "othello@example.com,hamlet@example.com");

    const persons = [othello, iago, hamlet];
    const items = compose_pm_pill.filter_taken_users(persons);
    assert.deepEqual(items, [
        {email: "iago@zulip.com", user_id: 2, full_name: "Iago", is_moderator: false},
    ]);

    test_create_item(create_item_handler);

    compose_pm_pill.set_from_emails("othello@example.com");
    assert.ok(compose_pm_pill.widget);

    assert.ok(pills_cleared);
    assert.ok(appendValue_called);
    assert.ok(text_cleared);

    compose_pm_pill.set_from_typeahead(me);
    compose_pm_pill.set_from_typeahead(othello);

    user_ids = compose_pm_pill.get_user_ids();
    assert.deepEqual(user_ids, [othello.user_id]);

    compose_pm_pill.set_from_user_ids([hamlet.user_id], true);
    user_ids = compose_pm_pill.get_user_ids();
    assert.deepEqual(user_ids, [hamlet.user_id]);
});

run_test("has_unconverted_data", ({override}) => {
    override(compose_pm_pill.widget, "is_pending", () => true);

    // If the pill itself has pending data, we have unconverted
    // data.
    assert.equal(compose_pm_pill.has_unconverted_data(), true);

    override(compose_pm_pill.widget, "is_pending", () => false);
    override(compose_pm_pill.widget, "items", () => [{user_id: 99}]);

    // Our pill is complete and all items contain user_id, so
    // we do NOT have unconverted data.
    assert.equal(compose_pm_pill.has_unconverted_data(), false);

    override(compose_pm_pill.widget, "items", () => [{user_id: 99}, {email: "random@mit.edu"}]);

    // One of our items only knows email (as in a bridge
    // scenario where we might not have registered the user yet), so
    // we have some unconverted data.
    assert.equal(compose_pm_pill.has_unconverted_data(), true);
});

run_test("update_user_pill_active_status", ({override_rewire}) => {
    const othello = {
        user_id: 1,
        email: "othello@example.com",
        full_name: "Othello",
        is_active: true,
        is_bot: false,
    };

    const inaccessible_user = {
        user_id: 2,
        email: "iago@zulip.com",
        full_name: "Iago",
        is_active: false,
        is_inaccessible_user: true,
        is_bot: false,
    };

    // Test with uninitialized widget - should return early without error
    override_rewire(compose_pm_pill, "widget", undefined);
    // No assertions needed - we're just checking it doesn't throw
    compose_pm_pill.update_user_pill_active_status(othello, false);

    // Set up test data for normal widget tests
    const pills_data = [
        {
            item: {user_id: othello.user_id, full_name: othello.full_name},
            $element: {0: {id: "pill_1"}},
        },
        {
            item: {user_id: inaccessible_user.user_id, full_name: inaccessible_user.full_name},
            $element: {0: {id: "pill_2"}},
        },
    ];

    let pill_updated = false;

    const widget = {
        getPillByPredicate(predicate) {
            return pills_data.find((p) => predicate(p.item));
        },
        updatePill(element, item) {
            const pill = pills_data.find((p) => p.$element[0] === element);
            pill.item = item;
            pill_updated = true;
        },
    };
    override_rewire(compose_pm_pill, "widget", widget);

    // Test deactivating a user - should set deactivated to true
    compose_pm_pill.update_user_pill_active_status(othello, false);

    assert.deepEqual(pills_data[0].item, {
        user_id: othello.user_id,
        full_name: othello.full_name,
        deactivated: true,
    });
    assert.ok(pill_updated);

    // Reset for next test
    pill_updated = false;

    // Test reactivating a user - should set deactivated to false
    compose_pm_pill.update_user_pill_active_status(othello, true);

    assert.deepEqual(pills_data[0].item, {
        user_id: othello.user_id,
        full_name: othello.full_name,
        deactivated: false,
    });
    assert.ok(pill_updated);

    // Reset for next test
    pill_updated = false;

    // Test deactivating an inaccessible user - should keep deactivated as false
    // We consider inaccessible users as active to avoid falsely showing them as deactivated,
    // since we don't have information about their activity status.
    compose_pm_pill.update_user_pill_active_status(inaccessible_user, false);

    assert.deepEqual(pills_data[1].item, {
        user_id: inaccessible_user.user_id,
        full_name: inaccessible_user.full_name,
        deactivated: false,
    });
    assert.ok(pill_updated);

    // Reset for next test
    pill_updated = false;

    // Test updating a user that doesn't have a pill - should be a no-op
    const hamlet = {user_id: 3, email: "hamlet@example.com", full_name: "Hamlet"};
    compose_pm_pill.update_user_pill_active_status(hamlet, true);

    assert.ok(!pill_updated);
});
