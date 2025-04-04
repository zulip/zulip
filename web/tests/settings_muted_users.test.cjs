"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const channel = mock_esm("../src/channel");
const list_widget = mock_esm("../src/list_widget", {
    generic_sort_functions: noop,
});
mock_esm("../src/settings_data", {
    user_can_access_all_other_users: () => false,
});

const settings_muted_users = zrequire("settings_muted_users");
const muted_users = zrequire("muted_users");
const people = zrequire("people");
const {set_realm} = zrequire("state_data");
const {initialize_user_settings} = zrequire("user_settings");

set_realm({});
initialize_user_settings({user_settings: {}});

run_test("settings", ({override}) => {
    people.add_active_user({user_id: 5, email: "five@zulip.com", full_name: "Feivel Fiverson"});
    muted_users.add_muted_user(5, 1577836800);
    muted_users.add_muted_user(10, 1577836900);
    let populate_list_called = false;
    override(list_widget, "create", (_$container, list) => {
        assert.deepEqual(list, [
            {
                date_muted: 1577836800000,
                date_muted_str: "Jan 1, 2020",
                user_id: 5,
                user_name: "Feivel Fiverson",
                can_unmute: true,
            },
            {
                date_muted: 1577836900000,
                date_muted_str: "Jan 1, 2020",
                user_id: 10,
                user_name: "translated: Unknown user",
                can_unmute: false,
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
    channel.del = (payload) => {
        assert.equal(payload.url, "/json/users/me/muted_users/5");
        unmute_user_called = true;
        return {abort() {}};
    };

    unmute_click_handler.call($unmute_button, event);
    assert.ok(unmute_user_called);
    assert.ok(row_attribute_fetched);

    let mute_user_called = false;
    channel.post = (payload) => {
        assert.equal(payload.url, "/json/users/me/muted_users/5");
        mute_user_called = true;
        return {abort() {}};
    };
    muted_users.mute_user(5);
    assert.ok(mute_user_called);
});
