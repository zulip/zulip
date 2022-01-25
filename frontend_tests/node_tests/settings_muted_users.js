"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

const muted_users_ui = mock_esm("../../static/js/muted_users_ui");

const settings_muted_users = zrequire("settings_muted_users");
const muted_users = zrequire("muted_users");

const noop = () => {};

run_test("settings", ({override_rewire}) => {
    muted_users.add_muted_user(5, 1577836800);
    let populate_list_called = false;
    override_rewire(settings_muted_users, "populate_list", () => {
        const opts = muted_users.get_muted_users();
        assert.deepEqual(opts, [
            {
                date_muted: 1577836800000,
                date_muted_str: "Jan\u00A001,\u00A02020",
                id: 5,
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
        if (opts === "data-user-id") {
            row_attribute_fetched += 1;
            return "5";
        }
        throw new Error(`Unknown attribute ${opts}`);
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
