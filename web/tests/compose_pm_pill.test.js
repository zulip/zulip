"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");

const input_pill = mock_esm("../src/input_pill");
const people = zrequire("people");

const compose_pm_pill = zrequire("compose_pm_pill");

let pills = {
    pill: {},
};

run_test("pills", ({override, override_rewire}) => {
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
        assert.equal(value, "othello@example.com");
        this.appendValidatedData(othello);
    };

    let get_by_email_called = false;
    override_rewire(people, "get_by_email", (user_email) => {
        get_by_email_called = true;
        switch (user_email) {
            case iago.email:
                return iago;
            case othello.email:
                return othello;
            /* istanbul ignore next */
            default:
                throw new Error(`Unknown user email ${user_email}`);
        }
    });

    let get_by_user_id_called = false;
    override_rewire(people, "get_by_user_id", (id) => {
        get_by_user_id_called = true;
        switch (id) {
            case othello.user_id:
                return othello;
            case hamlet.user_id:
                return hamlet;
            /* istanbul ignore next */
            default:
                throw new Error(`Unknown user ID ${id}`);
        }
    });

    function test_create_item(handler) {
        (function test_rejection_path() {
            const item = handler(othello.email, pills.items());
            assert.ok(get_by_email_called);
            assert.equal(item, undefined);
        })();

        (function test_success_path() {
            get_by_email_called = false;
            const res = handler(iago.email, pills.items());
            assert.ok(get_by_email_called);
            assert.equal(typeof res, "object");
            assert.equal(res.user_id, iago.user_id);
            assert.equal(res.display_value, iago.full_name);
        })();

        (function test_deactivated_pill() {
            people.deactivate(iago);
            get_by_email_called = false;
            const res = handler(iago.email, pills.items());
            assert.ok(get_by_email_called);
            assert.equal(typeof res, "object");
            assert.equal(res.user_id, iago.user_id);
            assert.equal(res.display_value, iago.full_name + " (deactivated)");
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

    const user_ids = compose_pm_pill.get_user_ids();
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

    assert.ok(get_by_user_id_called);
    assert.ok(pills_cleared);
    assert.ok(appendValue_called);
    assert.ok(text_cleared);
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

    // One of our items only knows email (as in a bridge-with-zephyr
    // scenario where we might not have registered the user yet), so
    // we have some unconverted data.
    assert.equal(compose_pm_pill.has_unconverted_data(), true);
});
