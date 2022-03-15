"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

const narrow_state = mock_esm("../../static/js/narrow_state");

const people = zrequire("people");
const pm_list_data = zrequire("pm_list_data");

const alice = {
    email: "alice@zulip.com",
    user_id: 101,
    full_name: "Alice",
};
const bob = {
    email: "bob@zulip.com",
    user_id: 102,
    full_name: "Bob",
};

people.add_active_user(alice);
people.add_active_user(bob);

function test(label, f) {
    run_test(label, ({override, override_rewire}) => {
        f({override, override_rewire});
    });
}

test("get_active_user_ids_string", ({override}) => {
    let active_filter;

    override(narrow_state, "filter", () => active_filter);

    assert.equal(pm_list_data.get_active_user_ids_string(), undefined);

    function set_filter_result(emails) {
        active_filter = {
            operands: (operand) => {
                assert.equal(operand, "pm-with");
                return emails;
            },
        };
    }

    set_filter_result([]);
    assert.equal(pm_list_data.get_active_user_ids_string(), undefined);

    set_filter_result(["bob@zulip.com,alice@zulip.com"]);
    assert.equal(pm_list_data.get_active_user_ids_string(), "101,102");
});
