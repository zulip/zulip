"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test, noop} = require("./lib/test");
const $ = require("./lib/zjquery");
const {current_user, realm} = require("./lib/zpage_params");

const loading = mock_esm("../src/loading");

const SHORT_TEXT_ID = 1;

const SELECT_ID = 3;
const EXTERNAL_ACCOUNT_ID = 7;
const LONG_TEXT_ID = 2;
const USER_FIELD_ID = 6;

const SHORT_TEXT_NAME = "Short text";
const SELECT_NAME = "Select";
const EXTERNAL_ACCOUNT_NAME = "External account";
const LONG_TEXT_NAME = "Long text";
const USER_FIELD_NAME = "Person";

const custom_profile_field_types = {
    SHORT_TEXT: {
        id: SHORT_TEXT_ID,
        name: SHORT_TEXT_NAME,
    },
    SELECT: {
        id: SELECT_ID,
        name: SELECT_NAME,
    },
    EXTERNAL_ACCOUNT: {
        id: EXTERNAL_ACCOUNT_ID,
        name: EXTERNAL_ACCOUNT_NAME,
    },
    LONG_TEXT: {
        id: LONG_TEXT_ID,
        name: LONG_TEXT_NAME,
    },
    USER: {
        id: USER_FIELD_ID,
        name: USER_FIELD_NAME,
    },
};

mock_esm("sortablejs", {Sortable: {create() {}}});

const settings_profile_fields = zrequire("settings_profile_fields");

function test_populate(opts, template_data) {
    const fields_data = opts.fields_data;

    realm.custom_profile_field_types = custom_profile_field_types;
    current_user.is_admin = opts.is_admin;
    const $table = $("#admin_profile_fields_table");
    const $rows = $.create("rows");
    const $form = $.create("forms");
    $table.set_find_results("tr.profile-field-row", $rows);
    $table.set_find_results("tr.profile-field-form", $form);

    $table[0] = "stub";

    $rows.remove = noop;
    $form.remove = noop;

    let num_appends = 0;
    $table.append = () => {
        num_appends += 1;
    };

    loading.destroy_indicator = noop;

    settings_profile_fields.do_populate_profile_fields(fields_data);

    assert.deepEqual(template_data, opts.expected_template_data);
    assert.equal(num_appends, fields_data.length);
}

run_test("populate_profile_fields", ({mock_template}) => {
    realm.custom_profile_fields = {};
    realm.realm_default_external_accounts = JSON.stringify({});

    $("#admin_profile_fields_table .display_in_profile_summary_false").toggleClass = noop;

    const template_data = [];
    mock_template("settings/admin_profile_field_list.hbs", false, (data) => {
        template_data.push(data);
        return "<admin-profile-field-list-stub>";
    });

    const fields_data = [
        {
            type: SHORT_TEXT_ID,
            id: 10,
            name: "favorite color",
            hint: "blue?",
            field_data: "",
            display_in_profile_summary: false,
            valid_to_display_in_summary: true,
            required: false,
        },
        {
            type: SELECT_ID,
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
            display_in_profile_summary: false,
            valid_to_display_in_summary: true,
            required: false,
        },
        {
            type: EXTERNAL_ACCOUNT_ID,
            id: 20,
            name: "github profile",
            hint: "username only",
            field_data: JSON.stringify({
                subtype: "github",
            }),
            display_in_profile_summary: true,
            valid_to_display_in_summary: true,
            required: false,
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
            display_in_profile_summary: true,
            valid_to_display_in_summary: true,
            required: false,
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
                is_select_field: false,
                is_external_account_field: false,
                display_in_profile_summary: false,
                valid_to_display_in_summary: true,
                required: false,
            },
            can_modify: true,
            realm_default_external_accounts: realm.realm_default_external_accounts,
        },
        {
            profile_field: {
                id: 30,
                name: "meal",
                hint: "lunch",
                type: SELECT_NAME,
                choices: [
                    {order: 0, value: "0", text: "lunch"},
                    {order: 1, value: "1", text: "dinner"},
                ],
                is_select_field: true,
                is_external_account_field: false,
                display_in_profile_summary: false,
                valid_to_display_in_summary: true,
                required: false,
            },
            can_modify: true,
            realm_default_external_accounts: realm.realm_default_external_accounts,
        },
        {
            profile_field: {
                id: 20,
                name: "github profile",
                hint: "username only",
                type: EXTERNAL_ACCOUNT_NAME,
                choices: [],
                is_select_field: false,
                is_external_account_field: true,
                display_in_profile_summary: true,
                valid_to_display_in_summary: true,
                required: false,
            },
            can_modify: true,
            realm_default_external_accounts: realm.realm_default_external_accounts,
        },
        {
            profile_field: {
                id: 21,
                name: "zulip profile",
                hint: "username only",
                type: EXTERNAL_ACCOUNT_NAME,
                choices: [],
                is_select_field: false,
                is_external_account_field: true,
                display_in_profile_summary: true,
                valid_to_display_in_summary: true,
                required: false,
            },
            can_modify: true,
            realm_default_external_accounts: realm.realm_default_external_accounts,
        },
    ];

    test_populate(
        {
            fields_data,
            expected_template_data,
            is_admin: true,
        },
        template_data,
    );
});
