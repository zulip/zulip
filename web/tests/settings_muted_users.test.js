"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");

const noop = () => {};

const list_widget = mock_esm("../src/list_widget", {
    generic_sort_functions: noop,
});
const muted_users_ui = mock_esm("../src/muted_users_ui");

const settings_muted_users = zrequire("settings_muted_users");
const muted_users = zrequire("muted_users");
const people = zrequire("people");

run_test("settings", ({override}) => {
    people.add_active_user({user_id: 5, email: "five@zulip.com", full_name: "Feivel Fiverson"});
    muted_users.add_muted_user(5, 1577836800);
    let populate_list_called = false;
    override(list_widget, "create", (_$container, list) => {
        assert.deepEqual(list, [
            {
                date_muted_str: "Jan 1, 2020",
                user_id: 5,
                user_name: "Feivel Fiverson",
            },
        ]);
        populate_list_called = true;
    });

    settings_muted_users.reset();
    assert.equal(settings_muted_users.loaded, false);

    settings_muted_users.set_up();
    assert.equal(settings_muted_users.loaded, true);
    assert.ok(populate_list_called);

    const unmute_click_handler = $("body").get_on_handler("click", ".settings-unmute-user");
    assert.equal(typeof unmute_click_handler, "function");

    const event = {
        stopPropagation: noop,
    };

    const $unmute_button = $.create("settings-unmute-user");
    const $fake_row = $('tr[data-user-id="5"]');
    $unmute_button.closest = (opts) => {
        assert.equal(opts, "tr");
        return $fake_row;
    };

    let row_attribute_fetched = false;
    $fake_row.attr = (opts) => {
        assert.equal(opts, "data-user-id");
        row_attribute_fetched += 1;
        return "5";
    };

    let unmute_user_called = false;
    muted_users_ui.unmute_user = (user_id) => {
        assert.equal(user_id, 5);
        unmute_user_called = true;
    };

    unmute_click_handler.call($unmute_button, event);
    assert.ok(unmute_user_called);
    assert.ok(row_attribute_fetched);
});
