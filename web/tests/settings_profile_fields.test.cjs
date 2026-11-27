"use strict";

const assert = require("node:assert/strict");

const {make_realm} = require("./lib/example_realm.cjs");
const {mock_esm, with_overrides, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const loading = mock_esm("../src/loading");

const SHORT_TEXT_ID = 1;

const DROPDOWN_ID = 3;
const EXTERNAL_ACCOUNT_ID = 7;
const PARAGRAPH_ID = 2;
const USER_FIELD_ID = 6;

const SHORT_TEXT_NAME = "Short text";
const DROPDOWN_NAME = "Dropdown";
const EXTERNAL_ACCOUNT_NAME = "External account";
const PARAGRAPH_NAME = "Paragraph";
const USER_FIELD_NAME = "Person";

const custom_profile_field_types = {
    SHORT_TEXT: {
        id: SHORT_TEXT_ID,
        name: SHORT_TEXT_NAME,
    },
    DROPDOWN: {
        id: DROPDOWN_ID,
        name: DROPDOWN_NAME,
    },
    EXTERNAL_ACCOUNT: {
        id: EXTERNAL_ACCOUNT_ID,
        name: EXTERNAL_ACCOUNT_NAME,
    },
    PARAGRAPH: {
        id: PARAGRAPH_ID,
        name: PARAGRAPH_NAME,
    },
    USER: {
        id: USER_FIELD_ID,
        name: USER_FIELD_NAME,
    },
};

const Sortable = {create: noop};

mock_esm("sortablejs", {default: Sortable});

const list_widget = mock_esm("../src/list_widget");

const settings_components = zrequire("settings_components");
const settings_profile_fields = zrequire("settings_profile_fields");
const {set_current_user, set_realm} = zrequire("state_data");

const current_user = {};
set_current_user(current_user);
const realm = make_realm();
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

        loading.destroy_indicator = noop;

        settings_profile_fields.do_populate_profile_fields(fields_data);

        assert.deepEqual(template_data, opts.expected_template_data);
    });
}

run_test("populate_profile_fields", ({mock_template, override}) => {
    make_list_widget_only_render_items(override);

    override(realm, "custom_profile_fields", {});
    override(realm, "realm_default_external_accounts", JSON.stringify({}));

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
            type: DROPDOWN_ID,
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
                type: DROPDOWN_NAME,
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

run_test("read_field_data_from_form_dropdown", ({override}) => {
    override(realm, "custom_profile_field_types", custom_profile_field_types);

    let next_id = 0;
    function make_choice_row(data_value, text) {
        const id = next_id;
        next_id += 1;
        const $row = $.create(`.choice-row-${id}`);
        $row.attr("data-value", data_value);
        const $input = $.create(`.choice-input-${id}`);
        $input.val(text);
        $row.set_find_results("input", $input);
        return {$row, $input};
    }

    function set_form_rows($form, rows) {
        $form.set_find_results(
            "div.choice-row",
            rows.map((row) => row.$row[0]),
        );
    }

    const old_field_data = {
        0: {text: "Vim", order: "1"},
        1: {text: "Emacs", order: "2"},
    };

    const $create_form = $.create("#add-new-custom-profile-field-form");
    set_form_rows($create_form, [
        make_choice_row("0", "Vim"),
        make_choice_row("1", "Emacs"),
        make_choice_row("2", ""),
    ]);
    assert.deepEqual(
        settings_components.read_field_data_from_form(DROPDOWN_ID, $create_form, undefined),
        old_field_data,
    );

    const $edit_form = $.create("#edit-profile-field-form-1");
    const emacs_row = make_choice_row("1", "Emacs");
    const new_row = make_choice_row("2", "Vim");
    const trailing_blank_row = make_choice_row("3", "");
    set_form_rows($edit_form, [emacs_row, new_row, trailing_blank_row]);

    assert.deepEqual(
        settings_components.read_field_data_from_form(DROPDOWN_ID, $edit_form, old_field_data),
        {
            0: {text: "Vim", order: "2"},
            1: {text: "Emacs", order: "1"},
        },
    );
    assert.equal(new_row.$row.attr("data-value"), "2");

    new_row.$input.val("Vim1");
    assert.deepEqual(
        settings_components.read_field_data_from_form(DROPDOWN_ID, $edit_form, old_field_data),
        {
            1: {text: "Emacs", order: "1"},
            2: {text: "Vim1", order: "2"},
        },
    );

    const $duplicate_form = $.create("#edit-profile-field-form-2");
    const existing_vim_row = make_choice_row("0", "Vim");
    const existing_emacs_row = make_choice_row("1", "Emacs");
    const duplicate_vim_row = make_choice_row("2", "Vim");
    set_form_rows($duplicate_form, [existing_vim_row, existing_emacs_row, duplicate_vim_row]);

    assert.deepEqual(
        settings_components.read_field_data_from_form(DROPDOWN_ID, $duplicate_form, old_field_data),
        {
            0: {text: "Vim", order: "1"},
            1: {text: "Emacs", order: "2"},
            2: {text: "Vim", order: "3"},
        },
    );

    const $deleted_duplicate_form = $.create("#edit-profile-field-form-3");
    const kept_emacs_row = make_choice_row("1", "Emacs");
    const readded_vim_row_1 = make_choice_row("2", "Vim");
    const readded_vim_row_2 = make_choice_row("3", "Vim");
    set_form_rows($deleted_duplicate_form, [kept_emacs_row, readded_vim_row_1, readded_vim_row_2]);

    assert.deepEqual(
        settings_components.read_field_data_from_form(
            DROPDOWN_ID,
            $deleted_duplicate_form,
            old_field_data,
        ),
        {
            0: {text: "Vim", order: "2"},
            1: {text: "Emacs", order: "1"},
            3: {text: "Vim", order: "3"},
        },
    );

    const $renamed_form = $.create("#edit-profile-field-form-4");
    const renamed_neovim_row = make_choice_row("0", "Neovim");
    const untouched_emacs_row = make_choice_row("1", "Emacs");
    const new_vim_row = make_choice_row("2", "Vim");
    set_form_rows($renamed_form, [renamed_neovim_row, untouched_emacs_row, new_vim_row]);

    assert.deepEqual(
        settings_components.read_field_data_from_form(DROPDOWN_ID, $renamed_form, old_field_data),
        {
            0: {text: "Neovim", order: "1"},
            1: {text: "Emacs", order: "2"},
            2: {text: "Vim", order: "3"},
        },
    );
});
