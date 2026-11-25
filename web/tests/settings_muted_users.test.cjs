"use strict";

const assert = require("node:assert/strict");

const {make_realm} = require("./lib/example_realm.cjs");
const {make_user} = require("./lib/example_user.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const channel = mock_esm("../src/channel");
const list_widget = mock_esm("../src/list_widget", {
    generic_sort_functions: noop,
});
const overlays = mock_esm("../src/overlays", {
    settings_open: () => false,
});
mock_esm("../src/settings_data", {
    user_can_access_all_other_users: () => false,
});

const settings_muted_users = zrequire("settings_muted_users");
const muted_users = zrequire("muted_users");
const people = zrequire("people");
const {set_realm} = zrequire("state_data");
const {initialize_user_settings} = zrequire("user_settings");

set_realm(make_realm());
initialize_user_settings({user_settings: {}});

run_test("settings", ({override}) => {
    people.add_active_user(
        make_user({
            user_id: 5,
            email: "five@zulip.com",
            full_name: "Feivel Fiverson",
        }),
    );
    people.add_active_user(
        make_user({
            user_id: 7,
            email: "seven@zulip.com",
            full_name: "Loading…",
            is_placeholder_user: true,
        }),
    );
    muted_users.add_muted_user(5, 1577836800);
    muted_users.add_muted_user(10, 1577836900);
    muted_users.add_muted_user(7, 1577837000);
    let populate_list_called = false;
    let replaced_list_data;
    override(list_widget, "create", (_$container, list) => {
        assert.deepEqual(list, [
            {
                date_muted: 1577836800000,
                date_muted_str: "Jan 1, 2020",
                user_id: 5,
                user_name: "Feivel Fiverson",
                can_unmute: true,
                is_placeholder_user: false,
            },
            {
                date_muted: 1577836900000,
                date_muted_str: "Jan 1, 2020",
                user_id: 10,
                user_name: "translated: Unknown user",
                can_unmute: false,
                is_placeholder_user: false,
            },
            {
                date_muted: 1577837000000,
                date_muted_str: "Jan 1, 2020",
                user_id: 7,
                user_name: "Loading…",
                can_unmute: true,
                is_placeholder_user: true,
                loading_shimmer_width_class: "loading-shimmer-width-2",
            },
        ]);
        populate_list_called = true;
        return {
            replace_list_data(list) {
                replaced_list_data = list;
            },
        };
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
    $unmute_button.set_closest_results("tr", $fake_row);

    $fake_row.attr("data-user-id", "5");

    let unmute_user_called = false;
    channel.del = (payload) => {
        assert.equal(payload.url, "/json/users/me/muted_users/5");
        unmute_user_called = true;
        return {abort() {}};
    };

    unmute_click_handler.call($unmute_button, event);
    assert.ok(unmute_user_called);

    let mute_user_called = false;
    channel.post = (payload) => {
        assert.equal(payload.url, "/json/users/me/muted_users/5");
        mute_user_called = true;
        return {abort() {}};
    };
    muted_users.mute_user(5);
    assert.ok(mute_user_called);

    people.add_active_user(
        make_user({
            user_id: 7,
            email: "seven@zulip.com",
            full_name: "Seven Sevenson",
        }),
    );
    populate_list_called = false;
    settings_muted_users.handle_users_fetched([7]);
    assert.equal(replaced_list_data, undefined);

    // Only the data of a muted user changes the list.
    override(overlays, "settings_open", () => true);
    settings_muted_users.handle_users_fetched([8]);
    assert.equal(replaced_list_data, undefined);

    // The list gets new items, without being made again.
    settings_muted_users.handle_users_fetched([7, 8]);
    assert.deepEqual(
        replaced_list_data.map((item) => [item.user_name, item.is_placeholder_user]),
        [
            ["Feivel Fiverson", false],
            ["translated: Unknown user", false],
            ["Seven Sevenson", false],
        ],
    );
    assert.ok(!populate_list_called);

    replaced_list_data = undefined;
    settings_muted_users.reset();
    settings_muted_users.handle_users_fetched([7]);
    assert.equal(replaced_list_data, undefined);
});
