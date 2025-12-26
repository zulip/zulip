"use strict";

const assert = require("node:assert/strict");

const {make_realm} = require("./lib/example_realm.cjs");
const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const people = zrequire("people");
const settings_config = zrequire("../src/settings_config.ts");
const {set_current_user, set_realm} = zrequire("state_data");

const current_user = {};
set_current_user(current_user);
const realm = make_realm();
set_realm(realm);

const owner = {
    email: "me@example.com",
    user_id: 30,
    full_name: "Me Myself",
    timezone: "America/Los_Angeles",
    is_admin: true,
    is_guest: false,
    is_moderator: false,
    is_bot: false,
    is_owner: true,
    role: settings_config.user_role_values.owner.code,
};

const regular_user = {
    email: "user@example.com",
    user_id: 32,
    full_name: "Regular User",
    is_admin: false,
    is_guest: false,
    is_moderator: false,
    is_bot: false,
    is_owner: false,
    role: settings_config.user_role_values.member.code,
};

function initialize() {
    people.init();
    people.add_active_user({...owner});
    people.initialize_current_user(owner.user_id);
}

run_test("user_is_only_organization_owner", ({override}) => {
    initialize();
    override(current_user, "is_owner", true);
    override(current_user, "is_admin", true);
    const person = people.get_by_email(owner.email);
    person.is_owner = true;
    assert.ok(person.is_owner && people.is_current_user_only_owner());
});

run_test("non-owner user can be deactivated even when sole owner exists", ({override}) => {
    initialize();
    override(current_user, "is_owner", true);
    override(current_user, "is_admin", true);

    const person = people.get_by_email(owner.email);
    person.is_owner = true;
    people.add_active_user({...regular_user});

    const reg_user = people.get_by_user_id(regular_user.user_id);
    const user_is_only_organization_owner =
        reg_user.is_owner && people.is_current_user_only_owner();
    assert.ok(!user_is_only_organization_owner);
});
