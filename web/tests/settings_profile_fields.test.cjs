"use strict";

const assert = require("node:assert/strict");

const {mock_esm, with_overrides, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

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

const Sortable = {create: noop};

mock_esm("sortablejs", {default: Sortable});

const list_widget = mock_esm("../src/list_widget");

const settings_profile_fields = zrequire("settings_profile_fields");
const {set_current_user, set_realm} = zrequire("state_data");

const current_user = {};
set_current_user(current_user);
const realm = {};
set_realm(realm);

function make_list_widget_only_render_items(override) {
    override(list_widget, "create", (_container, custom_profile_data, opts) => {
        for (const item of custom_profile_data) {
            opts.modifier_html(item);
        }
    });
}

function test_populate(opts, template_data) {
    with_overrides(({override}) => {
        const fields_data = opts.fields_data;

        override(realm, "custom_profile_field_types", custom_profile_field_types);
        override(current_user, "is_admin", opts.is_admin);
        const $table = $("#admin_profile_fields_table");

        $table[0] = "stub";

        loading.destroy_indicator = noop;

        settings_profile_fields.do_populate_profile_fields(fields_data);

        assert.deepEqual(template_data, opts.expected_template_data);
    });
}

run_test("populate_profile_fields", ({mock_template, override}) => {
    make_list_widget_only_render_items(override);

    override(realm, "custom_profile_fields", {});
    override(realm, "realm_default_external_accounts", JSON.stringify({}));

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
            field_data: JSON.stringify({
                0: {
                    text: "lunch",
                    order: "0",
                },
                1: {
                    text: "dinner",
                    order: "1",
                },
            }),
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
                    {order: "0", value: "0", text: "lunch"},
                    {order: "1", value: "1", text: "dinner"},
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
