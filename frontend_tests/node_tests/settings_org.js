"use strict";

const rewiremock = require("rewiremock/node");

set_global("$", global.make_zjquery());

const noop = () => {};

let form_data;

const _jQuery = {
    each(lst, f) {
        for (const [k, v] of lst.entries()) {
            f(k, v);
        }
    },
};

const _FormData = function () {
    return form_data;
};

const _loading = {
    make_indicator: noop,
    destroy_indicator: noop,
};

const _page_params = {
    is_admin: false,
    realm_domains: [
        {domain: "example.com", allow_subdomains: true},
        {domain: "example.org", allow_subdomains: false},
    ],
    realm_authentication_methods: {},
};

const _realm_icon = {};
const _channel = {};

global.stub_templates((name, data) => {
    if (name === "settings/admin_realm_domains_list") {
        assert(data.realm_domain.domain);
        return "stub-domains-list";
    }
});

const _overlays = {};

const _ui_report = {
    success(msg, elem) {
        elem.val(msg);
    },

    error(msg, xhr, elem) {
        elem.val(msg);
    },
};

const _realm_logo = {
    build_realm_logo_widget: noop,
};

const _list_render = {
    create: () => ({init: noop}),
};

set_global("channel", _channel);
set_global("csrf_token", "token-stub");
set_global("FormData", _FormData);
set_global("jQuery", _jQuery);
set_global("loading", _loading);
set_global("overlays", _overlays);
set_global("page_params", _page_params);
set_global("realm_icon", _realm_icon);
set_global("realm_logo", _realm_logo);
set_global("ui_report", _ui_report);
set_global("list_render", _list_render);

const settings_config = zrequire("settings_config");
const settings_bots = zrequire("settings_bots");
zrequire("stream_data");
rewiremock.proxy(() => zrequire("settings_account"), {
    // Setup is only imported to set the
    // setup.password_change_in_progress flag.
    "../../static/js/setup": {},
});
zrequire("settings_org");
zrequire("settings_ui");
zrequire("dropdown_list_widget");

run_test("unloaded", () => {
    // This test mostly gets us line coverage, and makes
    // sure things don't explode before set_up is called.

    settings_org.reset();
    settings_org.populate_realm_domains();
    settings_org.populate_auth_methods();
});

function simulate_realm_domains_table() {
    $("#realm_domains_table tbody").set_find_results("tr", $.create("realm-tr-stub"));

    let appended;
    $("#realm_domains_table tbody").append = function (html) {
        appended = true;
        assert.equal(html, "stub-domains-list");
    };

    return function verify() {
        assert(appended);
    };
}

function test_realms_domain_modal(add_realm_domain) {
    const info = $(".realm_domains_info");

    $("#add-realm-domain-widget").set_find_results(
        ".new-realm-domain",
        $.create("new-realm-domain-stub"),
    );

    $("#add-realm-domain-widget").set_find_results(
        ".new-realm-domain-allow-subdomains",
        $.create("new-realm-domain-allow-subdomains-stub"),
    );

    let posted;
    let success_callback;
    let error_callback;
    channel.post = function (req) {
        posted = true;
        assert.equal(req.url, "/json/realm/domains");
        success_callback = req.success;
        error_callback = req.error;
    };

    add_realm_domain();

    assert(posted);

    success_callback();
    assert.equal(info.val(), "translated: Added successfully!");

    error_callback({});
    assert.equal(info.val(), "translated: Failed");
}

function createSaveButtons(subsection) {
    const stub_save_button_header = $(`#org-${subsection}`);
    const save_button_controls = $(".save-button-controls");
    const stub_save_button = $(`#org-submit-${subsection}`);
    const stub_discard_button = $(`#org-discard-${subsection}`);
    const stub_save_button_text = $(".save-discard-widget-button-text");
    stub_save_button_header.set_find_results(
        ".subsection-failed-status p",
        $("<failed status element>"),
    );
    stub_save_button.closest = () => stub_save_button_header;
    save_button_controls.set_find_results(".save-button", stub_save_button);
    stub_save_button.set_find_results(".save-discard-widget-button-text", stub_save_button_text);
    stub_save_button_header.set_find_results(".save-button-controls", save_button_controls);
    stub_save_button_header.set_find_results(
        ".subsection-changes-discard .button",
        $(`#org-discard-${subsection}`),
    );
    save_button_controls.set_find_results(".discard-button", stub_discard_button);
    const props = {};
    props.hidden = false;
    save_button_controls.fadeIn = () => {
        props.hidden = false;
    };
    save_button_controls.fadeOut = () => {
        props.hidden = true;
    };
    return {
        props,
        save_button: stub_save_button,
        discard_button: stub_discard_button,
        save_button_header: stub_save_button_header,
        save_button_controls,
        save_button_text: stub_save_button_text,
    };
}

function test_submit_settings_form(submit_form) {
    Object.assign(page_params, {
        realm_bot_creation_policy: settings_bots.bot_creation_policy_values.restricted.code,
        realm_email_address_visibility:
            settings_config.email_address_visibility_values.admins_only.code,
        realm_add_emoji_by_admins_only: true,
        realm_create_stream_by_admins_only: true,
        realm_waiting_period_threshold: 1,
        realm_default_language: '"es"',
        realm_default_twenty_four_hour_time: false,
        realm_invite_to_stream_policy:
            settings_config.invite_to_stream_policy_values.by_admins_only.code,
        realm_create_stream_policy: settings_config.create_stream_policy_values.by_members.code,
    });

    global.patch_builtin("setTimeout", (func) => func());
    const ev = {
        preventDefault: noop,
        stopPropagation: noop,
    };

    let patched;
    let data;
    let success_callback;
    channel.patch = (req) => {
        patched = true;
        assert.equal(req.url, "/json/realm");
        data = req.data;
        success_callback = req.success;
    };

    let subsection = "other-permissions";
    ev.currentTarget = `#org-submit-${subsection}`;
    let stubs = createSaveButtons(subsection);
    let save_button = stubs.save_button;
    save_button.attr("id", `org-submit-${subsection}`);
    save_button.replace = () => `${subsection}`;

    $("#id_realm_waiting_period_threshold").val(10);

    const invite_to_stream_policy_elem = $("#id_realm_invite_to_stream_policy");
    invite_to_stream_policy_elem.val("1");
    invite_to_stream_policy_elem.attr("id", "id_realm_invite_to_stream_policy");
    invite_to_stream_policy_elem.data = () => "number";

    const create_stream_policy_elem = $("#id_realm_create_stream_policy");
    create_stream_policy_elem.val("2");
    create_stream_policy_elem.attr("id", "id_realm_create_stream_policy");
    create_stream_policy_elem.data = () => "number";

    const add_emoji_by_admins_only_elem = $("#id_realm_add_emoji_by_admins_only");
    add_emoji_by_admins_only_elem.val("by_anyone");
    add_emoji_by_admins_only_elem.attr("id", "id_realm_add_emoji_by_admins_only");

    const bot_creation_policy_elem = $("#id_realm_bot_creation_policy");
    bot_creation_policy_elem.val("1");
    bot_creation_policy_elem.attr("id", "id_realm_bot_creation_policy");
    bot_creation_policy_elem.data = () => "number";
    const email_address_visibility_elem = $("#id_realm_email_address_visibility");
    email_address_visibility_elem.val("1");
    email_address_visibility_elem.attr("id", "id_realm_email_address_visibility");
    email_address_visibility_elem.data = () => "number";

    let subsection_elem = $(`#org-${subsection}`);
    subsection_elem.closest = () => subsection_elem;
    subsection_elem.set_find_results(".prop-element", [
        bot_creation_policy_elem,
        email_address_visibility_elem,
        add_emoji_by_admins_only_elem,
        create_stream_policy_elem,
        invite_to_stream_policy_elem,
    ]);

    patched = false;
    submit_form(ev);
    assert(patched);

    let expected_value = {
        bot_creation_policy: "1",
        invite_to_stream_policy: "1",
        email_address_visibility: "1",
        add_emoji_by_admins_only: false,
        create_stream_policy: "2",
    };
    assert.deepEqual(data, expected_value);

    subsection = "user-defaults";
    ev.currentTarget = `#org-submit-${subsection}`;
    stubs = createSaveButtons(subsection);
    save_button = stubs.save_button;
    save_button.attr("id", `org-submit-${subsection}`);

    const realm_default_language_elem = $("#id_realm_default_language");
    realm_default_language_elem.val("en");
    realm_default_language_elem.attr("id", "id_realm_default_language");
    realm_default_language_elem.data = () => "string";
    const realm_default_twenty_four_hour_time_elem = $("#id_realm_default_twenty_four_hour_time");
    realm_default_twenty_four_hour_time_elem.val("true");
    realm_default_twenty_four_hour_time_elem.attr("id", "id_realm_default_twenty_four_hour_time");
    realm_default_twenty_four_hour_time_elem.data = () => "boolean";

    subsection_elem = $(`#org-${subsection}`);
    subsection_elem.closest = () => subsection_elem;
    subsection_elem.set_find_results(".prop-element", [
        realm_default_language_elem,
        realm_default_twenty_four_hour_time_elem,
    ]);

    submit_form(ev);
    assert(patched);

    expected_value = {
        default_language: '"en"',
        default_twenty_four_hour_time: "true",
    };
    assert.deepEqual(data, expected_value);

    // Testing only once for since callback is same for all cases
    success_callback();
    assert.equal(stubs.props.hidden, true);
    assert.equal(save_button.attr("data-status"), "saved");
    assert.equal(stubs.save_button_text.text(), "translated: Saved");
}

function test_change_save_button_state() {
    const {
        save_button_controls,
        save_button_text,
        save_button,
        discard_button,
        props,
    } = createSaveButtons("msg-editing");
    save_button.attr("id", "org-submit-msg-editing");

    {
        settings_org.change_save_button_state(save_button_controls, "unsaved");
        assert.equal(save_button_text.text(), "translated: Save changes");
        assert.equal(props.hidden, false);
        assert.equal(save_button.attr("data-status"), "unsaved");
        assert.equal(discard_button.visible(), true);
    }
    {
        settings_org.change_save_button_state(save_button_controls, "saved");
        assert.equal(save_button_text.text(), "translated: Save changes");
        assert.equal(props.hidden, true);
        assert.equal(save_button.attr("data-status"), "");
    }
    {
        settings_org.change_save_button_state(save_button_controls, "saving");
        assert.equal(save_button_text.text(), "translated: Saving");
        assert.equal(save_button.attr("data-status"), "saving");
        assert.equal(save_button.hasClass("saving"), true);
        assert.equal(discard_button.visible(), false);
    }
    {
        settings_org.change_save_button_state(save_button_controls, "discarded");
        assert.equal(props.hidden, true);
    }
    {
        settings_org.change_save_button_state(save_button_controls, "succeeded");
        assert.equal(props.hidden, true);
        assert.equal(save_button.attr("data-status"), "saved");
        assert.equal(save_button_text.text(), "translated: Saved");
    }
    {
        settings_org.change_save_button_state(save_button_controls, "failed");
        assert.equal(props.hidden, false);
        assert.equal(save_button.attr("data-status"), "failed");
        assert.equal(save_button_text.text(), "translated: Save changes");
    }
}

function test_upload_realm_icon(upload_realm_logo_or_icon) {
    form_data = {
        append(field, val) {
            form_data[field] = val;
        },
    };

    const file_input = [{files: ["image1.png", "image2.png"]}];

    let posted;
    channel.post = function (req) {
        posted = true;
        assert.equal(req.url, "/json/realm/icon");
        assert.equal(req.data.csrfmiddlewaretoken, "token-stub");
        assert.equal(req.data["file-0"], "image1.png");
        assert.equal(req.data["file-1"], "image2.png");
    };

    upload_realm_logo_or_icon(file_input, null, true);
    assert(posted);
}

function test_change_allow_subdomains(change_allow_subdomains) {
    const ev = {
        stopPropagation: noop,
    };

    const info = $(".realm_domains_info");
    info.fadeOut = noop;
    const domain = "example.com";
    let allow = true;

    let success_callback;
    let error_callback;
    channel.patch = function (req) {
        assert.equal(req.url, "/json/realm/domains/example.com");
        assert.equal(req.data.allow_subdomains, JSON.stringify(allow));
        success_callback = req.success;
        error_callback = req.error;
    };

    const domain_obj = $.create("domain object");
    domain_obj.text(domain);

    const elem_obj = $.create("<elem html>");
    const parents_obj = $.create("parents object");

    elem_obj.set_parents_result("tr", parents_obj);
    parents_obj.set_find_results(".domain", domain_obj);
    elem_obj.prop("checked", allow);

    change_allow_subdomains.call(elem_obj, ev);

    success_callback();
    assert.equal(info.val(), "translated: Update successful: Subdomains allowed for example.com");

    error_callback({});
    assert.equal(info.val(), "translated: Failed");

    allow = false;
    elem_obj.prop("checked", allow);
    change_allow_subdomains.call(elem_obj, ev);
    success_callback();
    assert.equal(
        info.val(),
        "translated: Update successful: Subdomains no longer allowed for example.com",
    );
}

function test_extract_property_name() {
    $("#id_realm_allow_message_editing").attr("id", "id_realm_allow_message_editing");
    assert.equal(
        settings_org.extract_property_name($("#id_realm_allow_message_editing")),
        "realm_allow_message_editing",
    );

    $("#id_realm_message_content_edit_limit_minutes_label").attr(
        "id",
        "id_realm_message_content_edit_limit_minutes_label",
    );
    assert.equal(
        settings_org.extract_property_name($("#id_realm_message_content_edit_limit_minutes_label")),
        "realm_message_content_edit_limit_minutes_label",
    );

    $("#id-realm-allow-message-deleting").attr("id", "id-realm-allow-message-deleting");
    assert.equal(
        settings_org.extract_property_name($("#id-realm-allow-message-deleting")),
        "realm_allow_message_deleting",
    );
}

function test_sync_realm_settings() {
    overlays.settings_open = () => true;

    {
        /* Test invalid settings property sync */
        const property_elem = $("#id_realm_invalid_settings_property");
        property_elem.attr("id", "id_realm_invalid_settings_property");
        property_elem.length = 1;

        blueslip.expect(
            "error",
            "Element refers to unknown property realm_invalid_settings_property",
        );
        settings_org.sync_realm_settings("invalid_settings_property");
    }

    {
        /*
            Test that when create stream policy is set to "full members" that the dropdown
            is set to the correct value.
        */
        const property_elem = $("#id_realm_create_stream_policy");
        property_elem.length = 1;
        property_elem.attr("id", "id_realm_create_stream_policy");

        page_params.realm_create_stream_policy = 3;

        settings_org.sync_realm_settings("create_stream_policy");
        assert.equal(
            $("#id_realm_create_stream_policy").val(),
            settings_config.create_stream_policy_values.by_full_members.code,
        );
    }

    {
        /*
            Test that when create stream policy is set to "by members" that the dropdown
            is set to the correct value.
        */
        const property_elem = $("#id_realm_create_stream_policy");
        property_elem.length = 1;
        property_elem.attr("id", "id_realm_create_stream_policy");

        page_params.realm_create_stream_policy = 1;

        settings_org.sync_realm_settings("create_stream_policy");
        assert.equal(
            $("#id_realm_create_stream_policy").val(),
            settings_config.create_stream_policy_values.by_members.code,
        );
    }

    {
        /*
            Test that when create stream policy is set to "by admins only" that the dropdown
            is set to the correct value.
        */
        const property_elem = $("#id_realm_create_stream_policy");
        property_elem.length = 1;
        property_elem.attr("id", "id_realm_create_stream_policy");

        page_params.realm_create_stream_policy = 2;

        settings_org.sync_realm_settings("create_stream_policy");
        assert.equal(
            $("#id_realm_create_stream_policy").val(),
            settings_config.create_stream_policy_values.by_admins_only.code,
        );
    }

    {
        /*
            Test that when invite to stream policy is set to "full members" that the dropdown
            is set to the correct value.
        */
        const property_elem = $("#id_realm_invite_to_stream_policy");
        property_elem.length = 1;
        property_elem.attr("id", "id_realm_invite_to_stream_policy");

        page_params.realm_invite_to_stream_policy = 3;

        settings_org.sync_realm_settings("invite_to_stream_policy");
        assert.equal(
            $("#id_realm_invite_to_stream_policy").val(),
            settings_config.create_stream_policy_values.by_full_members.code,
        );
    }

    {
        /*
            Test that when create stream policy is set to "by members" that the dropdown
            is set to the correct value.
        */
        const property_elem = $("#id_realm_invite_to_stream_policy");
        property_elem.length = 1;
        property_elem.attr("id", "id_realm_invite_to_stream_policy");

        page_params.realm_invite_to_stream_policy = 1;

        settings_org.sync_realm_settings("invite_to_stream_policy");
        assert.equal(
            $("#id_realm_invite_to_stream_policy").val(),
            settings_config.create_stream_policy_values.by_members.code,
        );
    }

    {
        /*
            Test that when create stream policy is set to "by admins only" that the dropdown
            is set to the correct value.
        */
        const property_elem = $("#id_realm_invite_to_stream_policy");
        property_elem.length = 1;
        property_elem.attr("id", "id_realm_invite_to_stream_policy");

        page_params.realm_invite_to_stream_policy = 2;

        settings_org.sync_realm_settings("invite_to_stream_policy");
        assert.equal(
            $("#id_realm_invite_to_stream_policy").val(),
            settings_config.create_stream_policy_values.by_admins_only.code,
        );
    }

    {
        /* Test message content edit limit minutes sync */
        const property_elem = $("#id_realm_message_content_edit_limit_minutes");
        property_elem.length = 1;
        property_elem.attr("id", "id_realm_message_content_edit_limit_minutes");

        page_params.realm_create_stream_policy = 1;
        page_params.realm_message_content_edit_limit_seconds = 120;

        settings_org.sync_realm_settings("message_content_edit_limit_seconds");
        assert.equal($("#id_realm_message_content_edit_limit_minutes").val(), "2");
    }

    {
        /* Test message content edit limit dropdown value sync */
        const property_elem = $("#id_realm_msg_edit_limit_setting");
        property_elem.length = 1;
        property_elem.attr("id", "id_realm_msg_edit_limit_setting");

        page_params.realm_allow_message_editing = false;
        page_params.realm_message_content_edit_limit_seconds = 120;
        settings_org.sync_realm_settings("allow_message_editing");
        assert.equal($("#id_realm_msg_edit_limit_setting").val(), "never");

        page_params.realm_allow_message_editing = true;

        page_params.realm_message_content_edit_limit_seconds = 120;
        settings_org.sync_realm_settings("allow_message_editing");
        assert.equal($("#id_realm_msg_edit_limit_setting").val(), "upto_two_min");

        page_params.realm_message_content_edit_limit_seconds = 130;
        settings_org.sync_realm_settings("allow_message_editing");
        assert.equal($("#id_realm_msg_edit_limit_setting").val(), "custom_limit");
    }

    {
        /* Test message content edit limit minutes sync */
        const property_elem = $("#id_realm_message_content_edit_limit_minutes");
        property_elem.length = 1;
        property_elem.attr("id", "id_realm_message_content_edit_limit_minutes");

        page_params.realm_create_stream_policy = 1;
        page_params.realm_message_content_edit_limit_seconds = 120;

        settings_org.sync_realm_settings("message_content_edit_limit_seconds");
        assert.equal($("#id_realm_message_content_edit_limit_minutes").val(), "2");
    }

    {
        /* Test organization joining restrictions settings sync */
        const property_elem = $("#id_realm_org_join_restrictions");
        property_elem.length = 1;
        property_elem.attr("id", "id_realm_org_join_restrictions");

        page_params.realm_emails_restricted_to_domains = true;
        page_params.realm_disallow_disposable_email_addresses = false;
        settings_org.sync_realm_settings("emails_restricted_to_domains");
        assert.equal($("#id_realm_org_join_restrictions").val(), "only_selected_domain");

        page_params.realm_emails_restricted_to_domains = false;

        page_params.realm_disallow_disposable_email_addresses = true;
        settings_org.sync_realm_settings("emails_restricted_to_domains");
        assert.equal($("#id_realm_org_join_restrictions").val(), "no_disposable_email");

        page_params.realm_disallow_disposable_email_addresses = false;
        settings_org.sync_realm_settings("emails_restricted_to_domains");
        assert.equal($("#id_realm_org_join_restrictions").val(), "no_restriction");
    }
}

function test_parse_time_limit() {
    const elem = $("#id_realm_message_content_edit_limit_minutes");
    const test_function = (value, expected_value = value) => {
        elem.val(value);
        global.page_params.realm_message_content_edit_limit_seconds = settings_org.parse_time_limit(
            elem,
        );
        assert.equal(
            settings_org.get_realm_time_limits_in_minutes(
                "realm_message_content_edit_limit_seconds",
            ),
            expected_value,
        );
    };

    test_function("0.01", "0");
    test_function("0.1");
    test_function("0.122", "0.1");
    test_function("0.155", "0.2");
    test_function("0.150", "0.1");
    test_function("0.5");
    test_function("1");
    test_function("1.1");
    test_function("10.5");
    test_function("50.3");
    test_function("100");
    test_function("100.1");
    test_function("127.79", "127.8");
    test_function("201.1");
    test_function("501.15", "501.1");
    test_function("501.34", "501.3");
}

function test_discard_changes_button(discard_changes) {
    const ev = {
        preventDefault: noop,
        stopPropagation: noop,
        target: "#org-discard-msg-editing",
    };

    page_params.realm_allow_edit_history = true;
    page_params.realm_allow_community_topic_editing = true;
    page_params.realm_allow_message_editing = true;
    page_params.realm_message_content_edit_limit_seconds = 3600;
    page_params.realm_allow_message_deleting = true;
    page_params.realm_message_content_delete_limit_seconds = 120;

    const allow_edit_history = $("#id_realm_allow_edit_history").prop("checked", false);
    const allow_community_topic_editing = $("#id_realm_allow_community_topic_editing").prop(
        "checked",
        true,
    );
    const msg_edit_limit_setting = $("#id_realm_msg_edit_limit_setting").val("custom_limit");
    const message_content_edit_limit_minutes = $(
        "#id_realm_message_content_edit_limit_minutes",
    ).val(130);
    const msg_delete_limit_setting = $("#id_realm_msg_delete_limit_setting").val("custom_limit");
    const message_content_delete_limit_minutes = $(
        "#id_realm_message_content_delete_limit_minutes",
    ).val(130);

    allow_edit_history.attr("id", "id_realm_allow_edit_history");
    msg_edit_limit_setting.attr("id", "id_realm_msg_edit_limit_setting");
    msg_delete_limit_setting.attr("id", "id_realm_msg_delete_limit_setting");
    allow_community_topic_editing.attr("id", "id_realm_allow_community_topic_editing");
    message_content_edit_limit_minutes.attr("id", "id_realm_message_content_edit_limit_minutes");
    message_content_delete_limit_minutes.attr(
        "id",
        "id_realm_message_content_delete_limit_minutes",
    );

    const discard_button_parent = $(".org-subsection-parent");
    discard_button_parent.find = () => [
        allow_edit_history,
        msg_edit_limit_setting,
        msg_delete_limit_setting,
        allow_community_topic_editing,
        message_content_edit_limit_minutes,
        message_content_delete_limit_minutes,
    ];

    $("#org-discard-msg-editing").closest = () => discard_button_parent;

    const stubbed_function = settings_org.change_save_button_state;
    settings_org.change_save_button_state = (save_button_controls, state) => {
        assert.equal(state, "discarded");
    };

    discard_changes(ev);

    assert.equal(allow_edit_history.prop("checked"), true);
    assert.equal(allow_community_topic_editing.prop("checked"), true);
    assert.equal(msg_edit_limit_setting.val(), "upto_one_hour");
    assert.equal(message_content_edit_limit_minutes.val(), "60");
    assert.equal(msg_delete_limit_setting.val(), "upto_two_min");
    assert.equal(message_content_delete_limit_minutes.val(), "2");

    settings_org.change_save_button_state = stubbed_function;
}

run_test("set_up", (override) => {
    const verify_realm_domains = simulate_realm_domains_table();
    page_params.realm_available_video_chat_providers = {
        jitsi_meet: {
            id: 1,
            name: "Jitsi Meet",
        },
        zoom: {
            id: 3,
            name: "Zoom",
        },
        big_blue_button: {
            id: 4,
            name: "Big Blue Button",
        },
    };

    let upload_realm_logo_or_icon;
    realm_icon.build_realm_icon_widget = function (f) {
        upload_realm_logo_or_icon = f;
    };

    const dropdown_list_widget_backup = dropdown_list_widget;
    window.dropdown_list_widget = () => ({
        render: noop,
        update: noop,
    });
    $("#id_realm_message_content_edit_limit_minutes").set_parent(
        $.create("<stub edit limit parent>"),
    );
    $("#id_realm_message_content_delete_limit_minutes").set_parent(
        $.create("<stub delete limit parent>"),
    );
    $("#id_realm_message_retention_days").set_parent($.create("<stub retention period parent>"));
    $("#message_content_in_email_notifications_label").set_parent(
        $.create("<stub in-content setting checkbox>"),
    );
    $("#enable_digest_emails_label").set_parent($.create("<stub digest setting checkbox>"));
    $("#id_realm_digest_weekday").set_parent($.create("<stub digest weekday setting dropdown>"));
    $("#allowed_domains_label").set_parent($.create("<stub-allowed-domain-label-parent>"));
    const waiting_period_parent_elem = $.create("waiting-period-parent-stub");
    $("#id_realm_waiting_period_threshold").set_parent(waiting_period_parent_elem);

    const allow_topic_edit_label_parent = $.create("allow-topic-edit-label-parent");
    $("#id_realm_allow_community_topic_editing_label").set_parent(allow_topic_edit_label_parent);

    channel.get = function (opts) {
        assert.equal(opts.url, "/json/export/realm");
    };

    // TEST set_up() here, but this mostly just allows us to
    // get access to the click handlers.
    override("settings_org.maybe_disable_widgets", noop);
    settings_org.set_up();

    verify_realm_domains();

    test_realms_domain_modal(() => $("#submit-add-realm-domain").trigger("click"));
    test_submit_settings_form(
        $(".organization").get_on_handler(
            "click",
            ".subsection-header .subsection-changes-save .button",
        ),
    );
    test_upload_realm_icon(upload_realm_logo_or_icon);
    test_change_allow_subdomains(
        $("#realm_domains_table").get_on_handler("change", ".allow-subdomains"),
    );
    test_extract_property_name();
    test_change_save_button_state();
    test_sync_realm_settings();
    test_parse_time_limit();
    test_discard_changes_button(
        $(".organization").get_on_handler(
            "click",
            ".subsection-header .subsection-changes-discard .button",
        ),
    );

    window.dropdown_list_widget = dropdown_list_widget_backup;
});

run_test("test get_organization_settings_options", () => {
    const sorted_option_values = settings_org.get_organization_settings_options();
    const sorted_create_stream_policy_values = sorted_option_values.create_stream_policy_values;
    const expected_create_stream_policy_values = [
        {
            key: "by_admins_only",
            order: 1,
            code: 2,
            description: i18n.t("Admins"),
        },
        {
            key: "by_full_members",
            order: 2,
            code: 3,
            description: i18n.t("Admins and full members"),
        },
        {
            key: "by_members",
            order: 3,
            code: 1,
            description: i18n.t("Admins and members"),
        },
    ];
    assert.deepEqual(sorted_create_stream_policy_values, expected_create_stream_policy_values);
});

run_test("test get_sorted_options_list", () => {
    const option_values_1 = {
        by_admins_only: {
            order: 3,
            code: 2,
            description: i18n.t("Admins"),
        },
        by_members: {
            order: 2,
            code: 1,
            description: i18n.t("Admins and members"),
        },
        by_full_members: {
            order: 1,
            code: 3,
            description: i18n.t("Admins and full members"),
        },
    };
    let expected_option_values = [
        {
            key: "by_full_members",
            order: 1,
            code: 3,
            description: i18n.t("Admins and full members"),
        },
        {
            key: "by_members",
            order: 2,
            code: 1,
            description: i18n.t("Admins and members"),
        },
        {
            key: "by_admins_only",
            order: 3,
            code: 2,
            description: i18n.t("Admins"),
        },
    ];
    assert.deepEqual(settings_org.get_sorted_options_list(option_values_1), expected_option_values);

    const option_values_2 = {
        by_admins_only: {
            code: 1,
            description: i18n.t("Admins"),
        },
        by_members: {
            code: 2,
            description: i18n.t("Admins and members"),
        },
        by_full_members: {
            code: 3,
            description: i18n.t("Admins and full members"),
        },
    };
    expected_option_values = [
        {
            key: "by_admins_only",
            code: 1,
            description: i18n.t("Admins"),
        },
        {
            key: "by_full_members",
            code: 3,
            description: i18n.t("Admins and full members"),
        },
        {
            key: "by_members",
            code: 2,
            description: i18n.t("Admins and members"),
        },
    ];
    assert.deepEqual(settings_org.get_sorted_options_list(option_values_2), expected_option_values);
});

run_test("misc", () => {
    page_params.is_admin = false;

    const stub_notification_disable_parent = $.create("<stub notification_disable parent");
    stub_notification_disable_parent.set_find_results(
        ".dropdown_list_reset_button:not([disabled])",
        $.create("<disable link>"),
    );

    page_params.realm_name_changes_disabled = false;
    page_params.server_name_changes_disabled = false;
    settings_account.update_name_change_display();
    assert(!$("#full_name").prop("disabled"));
    assert.equal($(".change_name_tooltip").is(":visible"), false);

    page_params.realm_name_changes_disabled = true;
    page_params.server_name_changes_disabled = false;
    settings_account.update_name_change_display();
    assert($("#full_name").prop("disabled"));
    assert($(".change_name_tooltip").is(":visible"));

    page_params.realm_name_changes_disabled = true;
    page_params.server_name_changes_disabled = true;
    settings_account.update_name_change_display();
    assert($("#full_name").prop("disabled"));
    assert($(".change_name_tooltip").is(":visible"));

    page_params.realm_name_changes_disabled = false;
    page_params.server_name_changes_disabled = true;
    settings_account.update_name_change_display();
    assert($("#full_name").prop("disabled"));
    assert($(".change_name_tooltip").is(":visible"));

    page_params.realm_email_changes_disabled = false;
    settings_account.update_email_change_display();
    assert(!$("#change_email .button").prop("disabled"));

    page_params.realm_email_changes_disabled = true;
    settings_account.update_email_change_display();
    assert($("#change_email .button").prop("disabled"));

    page_params.realm_avatar_changes_disabled = false;
    page_params.server_avatar_changes_disabled = false;
    settings_account.update_avatar_change_display();
    assert(!$("#user-avatar-upload-widget .image_upload_button").prop("disabled"));
    assert(!$("#user-avatar-upload-widget .image-delete-button .button").prop("disabled"));
    page_params.realm_avatar_changes_disabled = true;
    page_params.server_avatar_changes_disabled = false;
    settings_account.update_avatar_change_display();
    assert($("#user-avatar-upload-widget .image_upload_button").prop("disabled"));
    assert($("#user-avatar-upload-widget .image-delete-button .button").prop("disabled"));
    page_params.realm_avatar_changes_disabled = false;
    page_params.server_avatar_changes_disabled = true;
    settings_account.update_avatar_change_display();
    assert($("#user-avatar-upload-widget .image_upload_button").prop("disabled"));
    assert($("#user-avatar-upload-widget .image-delete-button .button").prop("disabled"));
    page_params.realm_avatar_changes_disabled = true;
    page_params.server_avatar_changes_disabled = true;
    settings_account.update_avatar_change_display();
    assert($("#user-avatar-upload-widget .image_upload_button").prop("disabled"));
    assert($("#user-avatar-upload-widget .image-delete-button .button").prop("disabled"));

    // If organization admin, these UI elements are never disabled.
    page_params.is_admin = true;
    settings_account.update_name_change_display();
    assert(!$("#full_name").prop("disabled"));
    assert.equal($(".change_name_tooltip").is(":visible"), false);

    settings_account.update_email_change_display();
    assert(!$("#change_email .button").prop("disabled"));

    stream_data.get_streams_for_settings_page = () => {
        const arr = [];
        arr.push({name: "some_stream", stream_id: 75});
        arr.push({name: "some_stream", stream_id: 42});
        return arr;
    };

    // Set stubs for dropdown_list_widget:
    const widget_settings = [
        "realm_notifications_stream_id",
        "realm_signup_notifications_stream_id",
        "realm_default_code_block_language",
    ];
    const dropdown_list_parent = $.create("<list parent>");
    dropdown_list_parent.set_find_results(
        ".dropdown_list_reset_button:not([disabled])",
        $.create("<disable button>"),
    );
    widget_settings.forEach((name) => {
        const elem = $.create(`#${name}_widget #${name}_name`);
        elem.closest = () => dropdown_list_parent;
    });

    // We do not define any settings we need in page_params yet, but we don't need to for this test.
    blueslip.expect(
        "warn",
        "dropdown-list-widget: Called without a default value; using null value",
        3,
    );
    settings_org.init_dropdown_widgets();

    let setting_name = "realm_notifications_stream_id";
    let elem = $(`#${setting_name}_widget #${setting_name}_name`);
    elem.closest = function () {
        return stub_notification_disable_parent;
    };
    stream_data.get_sub_by_id = function (stream_id) {
        assert.equal(stream_id, 42);
        return {name: "some_stream"};
    };
    settings_org.notifications_stream_widget.render(42);
    assert.equal(elem.text(), "#some_stream");
    assert(!elem.hasClass("text-warning"));

    settings_org.notifications_stream_widget.render(undefined);
    assert.equal(elem.text(), "translated: Disabled");
    assert(elem.hasClass("text-warning"));

    setting_name = "realm_signup_notifications_stream_id";
    elem = $(`#${setting_name}_widget #${setting_name}_name`);
    elem.closest = function () {
        return stub_notification_disable_parent;
    };
    stream_data.get_sub_by_id = function (stream_id) {
        assert.equal(stream_id, 75);
        return {name: "some_stream"};
    };
    settings_org.signup_notifications_stream_widget.render(75);
    assert.equal(elem.text(), "#some_stream");
    assert(!elem.hasClass("text-warning"));

    settings_org.signup_notifications_stream_widget.render(undefined);
    assert.equal(elem.text(), "translated: Disabled");
    assert(elem.hasClass("text-warning"));
});
