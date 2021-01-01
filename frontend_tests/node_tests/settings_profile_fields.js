"use strict";

const {strict: assert} = require("assert");

const rewiremock = require("rewiremock/node");

const {stub_templates} = require("../zjsunit/handlebars");
const {set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const {make_zjquery} = require("../zjsunit/zjquery");

set_global("page_params", {});
set_global("$", make_zjquery());
set_global("loading", {});

const SHORT_TEXT_ID = 1;
const CHOICE_ID = 3;
const EXTERNAL_ACCOUNT_ID = 7;

const SHORT_TEXT_NAME = "Short Text";
const CHOICE_NAME = "Choice";
const EXTERNAL_ACCOUNT_NAME = "External account";

page_params.custom_profile_fields = {};
page_params.realm_default_external_accounts = JSON.stringify({});

page_params.custom_profile_field_types = {
    SHORT_TEXT: {
        id: SHORT_TEXT_ID,
        name: SHORT_TEXT_NAME,
    },
    CHOICE: {
        id: CHOICE_ID,
        name: CHOICE_NAME,
    },
    EXTERNAL_ACCOUNT: {
        id: EXTERNAL_ACCOUNT_ID,
        name: EXTERNAL_ACCOUNT_NAME,
    },
};

rewiremock.proxy(() => zrequire("settings_profile_fields"), {
    sortablejs: {default: {create: () => {}}},
});

function test_populate(opts) {
    const fields_data = opts.fields_data;

    page_params.is_admin = opts.is_admin;
    const table = $("#admin_profile_fields_table");
    const rows = $.create("rows");
    const form = $.create("forms");
    table.set_find_results("tr.profile-field-row", rows);
    table.set_find_results("tr.profile-field-form", form);

    let num_appends = 0;
    table.append = () => {
        num_appends += 1;
    };

    loading.destroy_indicator = () => {};

    const template_data = [];
    stub_templates((fn, data) => {
        assert.equal(fn, "admin_profile_field_list");
        template_data.push(data);
        return "whatever";
    });

    settings_profile_fields.do_populate_profile_fields(fields_data);

    assert.deepEqual(template_data, opts.expected_template_data);
    assert.equal(num_appends, fields_data.length);
}

run_test("populate_profile_fields", () => {
    const fields_data = [
        {
            type: SHORT_TEXT_ID,
            id: 10,
            name: "favorite color",
            hint: "blue?",
            field_data: "",
        },
        {
            type: CHOICE_ID,
            id: 30,
            name: "meal",
            hint: "lunch",
            field_data: JSON.stringify([
                {
                    text: "lunch",
                    order: 0,
                },
                {
                    text: "dinner",
                    order: 1,
                },
            ]),
        },
        {
            type: EXTERNAL_ACCOUNT_ID,
            id: 20,
            name: "github profile",
            hint: "username only",
            field_data: JSON.stringify({
                subtype: "github",
            }),
        },
        {
            type: EXTERNAL_ACCOUNT_ID,
            id: 21,
            name: "zulip profile",
            hint: "username only",
            field_data: JSON.stringify({
                subtype: "custom",
                url_pattern: "https://chat.zulip.com/%(username)s",
            }),
        },
    ];
    const expected_template_data = [
        {
            profile_field: {
                id: 10,
                name: "favorite color",
                hint: "blue?",
                type: SHORT_TEXT_NAME,
                choices: [],
                is_choice_field: false,
                is_external_account_field: false,
            },
            can_modify: true,
            realm_default_external_accounts: page_params.realm_default_external_accounts,
        },
        {
            profile_field: {
                id: 30,
                name: "meal",
                hint: "lunch",
                type: CHOICE_NAME,
                choices: [
                    {order: 0, value: "0", text: "lunch"},
                    {order: 1, value: "1", text: "dinner"},
                ],
                is_choice_field: true,
                is_external_account_field: false,
            },
            can_modify: true,
            realm_default_external_accounts: page_params.realm_default_external_accounts,
        },
        {
            profile_field: {
                id: 20,
                name: "github profile",
                hint: "username only",
                type: EXTERNAL_ACCOUNT_NAME,
                choices: [],
                is_choice_field: false,
                is_external_account_field: true,
            },
            can_modify: true,
            realm_default_external_accounts: page_params.realm_default_external_accounts,
        },
        {
            profile_field: {
                id: 21,
                name: "zulip profile",
                hint: "username only",
                type: EXTERNAL_ACCOUNT_NAME,
                choices: [],
                is_choice_field: false,
                is_external_account_field: true,
            },
            can_modify: true,
            realm_default_external_accounts: page_params.realm_default_external_accounts,
        },
    ];

    test_populate({
        fields_data,
        expected_template_data,
        is_admin: true,
    });
});
