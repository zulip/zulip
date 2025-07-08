"use strict";

const assert = require("node:assert/strict");

const {$t} = require("./lib/i18n.cjs");
const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const realm_icon = mock_esm("../src/realm_icon");

const channel = mock_esm("../src/channel");

mock_esm("../src/csrf", {csrf_token: "token-stub"});
mock_esm("../src/loading", {
    make_indicator: noop,
    destroy_indicator: noop,
});
mock_esm("../src/buttons", {
    show_button_loading_indicator: noop,
    hide_button_loading_indicator: noop,
    modify_action_button_style: noop,
});
mock_esm("../src/scroll_util", {scroll_element_into_container: noop});
mock_esm("../src/ui_util", {
    disable_element_and_add_tooltip: noop,
    enable_element_and_remove_tooltip: noop,
});
set_global("document", "document-stub");

set_global("requestAnimationFrame", (func) => func());

const settings_account = zrequire("settings_account");
const settings_components = zrequire("settings_components");
const settings_config = zrequire("settings_config");
const settings_org = zrequire("settings_org");
const {set_current_user, set_realm} = zrequire("state_data");
const pygments_data = zrequire("pygments_data");
const {initialize_user_settings} = zrequire("user_settings");

const current_user = {};
set_current_user(current_user);
const realm = {};
set_realm(realm);
initialize_user_settings({user_settings: {}});

function test(label, f) {
    run_test(label, (helpers) => {
        $("#realm-icon-upload-widget .upload-spinner-background").css = noop;
        helpers.override(current_user, "is_admin", false);
        helpers.override(realm, "realm_domains", [
            {domain: "example.com", allow_subdomains: true},
            {domain: "example.org", allow_subdomains: false},
        ]);
        helpers.override(realm, "realm_authentication_methods", {});
        settings_org.reset();
        f(helpers);
    });
}

test("unloaded", () => {
    // This test mostly gets us line coverage, and makes
    // sure things don't explode before set_up is called.

    settings_org.reset();
    settings_org.populate_realm_domains_label();
    settings_org.populate_auth_methods();
});

function createSaveButtons(subsection) {
    const $stub_save_button_header = $(`#org-${CSS.escape(subsection)}`);
    const $save_button_controls = $(".save-button-controls");
    const $stub_save_button = $(".save-button");
    const $stub_discard_button = $(".discard-button");
    const $stub_save_button_text = $(".action-button-label");
    $stub_save_button_header.set_find_results(
        ".subsection-failed-status p",
        $("<failed-status-stub>"),
    );
    $stub_save_button.closest = () => $stub_save_button_header;
    $save_button_controls.set_find_results(".save-button", $stub_save_button);
    $stub_save_button.set_find_results(".action-button-label", $stub_save_button_text);
    $stub_save_button_header.set_find_results(".save-button-controls", $save_button_controls);
    $stub_save_button_header.set_find_results(
        ".subsection-changes-discard button",
        $stub_discard_button,
    );
    $save_button_controls.set_find_results(".discard-button", $stub_discard_button);
    const props = {};
    props.hidden = false;
    $save_button_controls.fadeIn = () => {
        props.hidden = false;
    };
    $save_button_controls.fadeOut = () => {
        props.hidden = true;
    };

    $save_button_controls.closest = () => $stub_save_button_header;
    $stub_save_button_header.set_find_results(".time-limit-setting", []);
    $stub_save_button_header.set_find_results(".pill-container", []);
    $stub_save_button_header.set_find_results(".subsection-changes-save button", $stub_save_button);
    $stub_save_button_header.set_find_results(".save-button", $stub_save_button);

    return {
        props,
        $save_button: $stub_save_button,
        $discard_button: $stub_discard_button,
        $save_button_header: $stub_save_button_header,
        $save_button_controls,
        $save_button_text: $stub_save_button_text,
    };
}

function test_submit_settings_form(override, submit_form) {
    Object.assign(realm, {
        realm_waiting_period_threshold: 1,
        realm_default_language: '"es"',
    });

    override(global, "setTimeout", (func) => func());
    const ev = {
        preventDefault: noop,
        stopPropagation: noop,
    };

    let patched;
    let data;
    let success_callback;
    override(channel, "patch", (req) => {
        patched = true;
        assert.equal(req.url, "/json/realm");
        data = req.data;
        success_callback = req.success;
    });

    let subsection = "other-permissions";
    let stubs = createSaveButtons(subsection);
    let $save_button = stubs.$save_button;
    let $save_button_header = stubs.$save_button_header;
    $save_button_header.attr("id", `org-${subsection}`);

    $("#id_realm_waiting_period_threshold").val(10);

    let $subsection_elem = $(`#org-${CSS.escape(subsection)}`);

    subsection = "user-defaults";
    stubs = createSaveButtons(subsection);
    $save_button = stubs.$save_button;
    $save_button_header = stubs.$save_button_header;
    $save_button_header.attr("id", `org-${subsection}`);

    const $realm_default_language_elem = $("#id_realm_default_language");
    $realm_default_language_elem.val("en");
    $realm_default_language_elem.attr("id", "id_realm_default_language");

    $subsection_elem = $(`#org-${CSS.escape(subsection)}`);
    $subsection_elem.set_find_results(".prop-element", [$realm_default_language_elem]);

    submit_form.call({to_$: () => $(".save-button")}, ev);
    assert.ok(patched);

    const expected_value = {
        default_language: "en",
    };
    assert.deepEqual(data, expected_value);

    // Testing only once for since callback is same for all cases
    success_callback();
    assert.equal(stubs.props.hidden, true);
    assert.equal($save_button.attr("data-status"), "saved");
    assert.equal(stubs.$save_button_text.text(), "translated: Saved");
}

function test_change_save_button_state() {
    const {
        $save_button_controls,
        $save_button_text,
        $save_button,
        $save_button_header,
        $discard_button,
        props,
    } = createSaveButtons("msg-editing");
    $save_button_header.attr("id", "org-msg-editing");
    $("#org-msg-editing").closest = () => ({});

    {
        settings_components.change_save_button_state($save_button_controls, "unsaved");
        assert.equal($save_button_text.text(), "translated: Save changes");
        assert.equal(props.hidden, false);
        assert.equal($save_button.attr("data-status"), "unsaved");
        assert.equal($discard_button.visible(), true);
    }
    {
        settings_components.change_save_button_state($save_button_controls, "discarded");
        assert.equal(props.hidden, true);
    }
    {
        settings_components.change_save_button_state($save_button_controls, "saving");
        assert.equal($save_button.attr("data-status"), "saving");
        assert.equal($discard_button.visible(), false);
    }
    {
        // The "discarded" state should not interfere during the saving stage.
        settings_components.change_save_button_state($save_button_controls, "discarded");
        assert.equal(props.hidden, false);
    }
    {
        settings_components.change_save_button_state($save_button_controls, "succeeded");
        assert.equal(props.hidden, true);
        assert.equal($save_button.attr("data-status"), "saved");
        assert.equal($save_button_text.text(), "translated: Saved");
    }
    {
        settings_components.change_save_button_state($save_button_controls, "failed");
        assert.equal(props.hidden, false);
        assert.equal($save_button.attr("data-status"), "failed");
        assert.equal($save_button_text.text(), "translated: Save changes");
    }
}

function test_upload_realm_icon(override, upload_realm_logo_or_icon) {
    const file_input = [{files: ["image1.png", "image2.png"]}];

    let posted;
    override(channel, "post", (req) => {
        posted = true;
        assert.equal(req.url, "/json/realm/icon");
        assert.equal(req.data.get("csrfmiddlewaretoken"), "token-stub");
        assert.equal(req.data.get("file-0"), "image1.png");
        assert.equal(req.data.get("file-1"), "image2.png");
    });

    upload_realm_logo_or_icon(file_input, null, true);
    assert.ok(posted);
}

function test_extract_property_name() {
    $("#id_realm_allow_message_editing").attr("id", "id_realm_allow_message_editing");
    assert.equal(
        settings_components.extract_property_name($("#id_realm_allow_message_editing")),
        "realm_allow_message_editing",
    );

    $("#id_realm_message_content_edit_limit_minutes_label").attr(
        "id",
        "id_realm_message_content_edit_limit_minutes_label",
    );
    assert.equal(
        settings_components.extract_property_name(
            $("#id_realm_message_content_edit_limit_minutes_label"),
        ),
        "realm_message_content_edit_limit_minutes_label",
    );

    $("#id-realm-allow-message-deleting").attr("id", "id-realm-allow-message-deleting");
    assert.equal(
        settings_components.extract_property_name($("#id-realm-allow-message-deleting")),
        "realm_allow_message_deleting",
    );
}

function test_sync_realm_settings({override}) {
    const $subsection_stub = $.create("org-subsection-stub");
    $subsection_stub.set_find_results(
        ".save-button-controls",
        $.create("save-button-controls-stub").addClass("hide"),
    );

    {
        /* Test message content edit limit minutes sync */
        const $property_elem = $("#id_realm_message_content_edit_limit_minutes");
        const $property_dropdown_elem = $("#id_realm_message_content_edit_limit_seconds");
        $property_elem.length = 1;
        $property_dropdown_elem.length = 1;
        $property_elem.attr("id", "id_realm_message_content_edit_limit_minutes");
        $property_dropdown_elem.attr("id", "id_realm_message_content_edit_limit_seconds");
        $property_dropdown_elem.closest = () => $subsection_stub;
        $property_dropdown_elem[0] = "#id_realm_message_content_edit_limit_seconds";

        override(realm, "realm_message_content_edit_limit_seconds", 120);

        settings_org.sync_realm_settings("message_content_edit_limit_seconds");
        assert.equal($("#id_realm_message_content_edit_limit_minutes").val(), "2");
    }

    {
        /* Test message content edit limit dropdown value sync */
        override(realm, "realm_message_content_edit_limit_seconds", 120);
        settings_org.sync_realm_settings("message_content_edit_limit_seconds");
        assert.equal($("#id_realm_message_content_edit_limit_seconds").val(), "120");

        override(realm, "realm_message_content_edit_limit_seconds", 130);
        settings_org.sync_realm_settings("message_content_edit_limit_seconds");
        assert.equal($("#id_realm_message_content_edit_limit_seconds").val(), "custom_period");
    }

    {
        /* Test organization joining restrictions settings sync */
        const $property_elem = $("#id_realm_org_join_restrictions");
        $property_elem.length = 1;
        $property_elem.attr("id", "id_realm_org_join_restrictions");
        $property_elem.closest = () => $subsection_stub;
        $property_elem[0] = "#id_realm_org_join_restrictions";

        override(realm, "realm_emails_restricted_to_domains", true);
        override(realm, "realm_disallow_disposable_email_addresses", false);
        settings_org.sync_realm_settings("emails_restricted_to_domains");
        assert.equal($("#id_realm_org_join_restrictions").val(), "only_selected_domain");

        override(realm, "realm_emails_restricted_to_domains", false);

        override(realm, "realm_disallow_disposable_email_addresses", true);
        settings_org.sync_realm_settings("emails_restricted_to_domains");
        assert.equal($("#id_realm_org_join_restrictions").val(), "no_disposable_email");

        override(realm, "realm_disallow_disposable_email_addresses", false);
        settings_org.sync_realm_settings("emails_restricted_to_domains");
        assert.equal($("#id_realm_org_join_restrictions").val(), "no_restriction");
    }
}

function test_parse_time_limit({override}) {
    const $elem = $("#id_realm_message_content_edit_limit_minutes");
    const test_function = (value, expected_value = value) => {
        $elem.val(value);
        override(
            realm,
            "realm_message_content_edit_limit_seconds",
            settings_components.parse_time_limit($elem),
        );
        assert.equal(
            settings_components.get_realm_time_limits_in_minutes(
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

function test_discard_changes_button({override}, discard_changes) {
    const ev = {
        preventDefault: noop,
        stopPropagation: noop,
    };

    override(
        realm,
        "realm_message_edit_history_visibility_policy",
        settings_config.message_edit_history_visibility_policy_values.always.code,
    );
    override(realm, "realm_allow_message_editing", true);
    override(realm, "realm_message_content_edit_limit_seconds", 3600);
    override(realm, "realm_message_content_delete_limit_seconds", 120);

    const $message_edit_history_visibility_policy = $(
        "#id_realm_message_edit_history_visibility_policy",
    ).val(settings_config.message_edit_history_visibility_policy_values.never.code);
    const $msg_edit_limit_setting = $("#id_realm_message_content_edit_limit_seconds").val(
        "custom_period",
    );
    const $message_content_edit_limit_minutes = $(
        "#id_realm_message_content_edit_limit_minutes",
    ).val(130);
    const $msg_delete_limit_setting = $("#id_realm_message_content_delete_limit_seconds").val(
        "custom_period",
    );
    const $message_content_delete_limit_minutes = $(
        "#id_realm_message_content_delete_limit_minutes",
    ).val(130);

    $message_edit_history_visibility_policy.attr(
        "id",
        "id_realm_message_edit_history_visibility_policy",
    );
    $msg_edit_limit_setting.attr("id", "id_realm_message_content_edit_limit_seconds");
    $msg_delete_limit_setting.attr("id", "id_realm_message_content_delete_limit_seconds");
    $message_content_edit_limit_minutes.attr("id", "id_realm_message_content_edit_limit_minutes");
    $message_content_delete_limit_minutes.attr(
        "id",
        "id_realm_message_content_delete_limit_minutes",
    );

    const $discard_button_parent = $(".settings-subsection-parent");
    $discard_button_parent.set_find_results(".prop-element", [
        $message_edit_history_visibility_policy,
        $msg_edit_limit_setting,
        $msg_delete_limit_setting,
    ]);

    const {$discard_button, $save_button_controls, props} = createSaveButtons("msg-editing");
    $discard_button.closest = (selector) => {
        assert.equal(selector, ".settings-subsection-parent");
        return $discard_button_parent;
    };

    $discard_button_parent.set_find_results(".save-button-controls", $save_button_controls);

    discard_changes.call({to_$: () => $(".discard-button")}, ev);

    assert.equal(
        $message_edit_history_visibility_policy.val(),
        settings_config.message_edit_history_visibility_policy_values.always.code,
    );
    assert.equal($msg_edit_limit_setting.val(), "3600");
    assert.equal($message_content_edit_limit_minutes.val(), "60");
    assert.equal($msg_delete_limit_setting.val(), "120");
    assert.equal($message_content_delete_limit_minutes.val(), "2");
    assert.ok(props.hidden);
}

test("set_up", ({override, override_rewire}) => {
    override(realm, "realm_available_video_chat_providers", {
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
            name: "BigBlueButton",
        },
    });
    override(realm, "realm_message_retention_days", null);

    let upload_realm_logo_or_icon;
    realm_icon.build_realm_icon_widget = (f) => {
        upload_realm_logo_or_icon = f;
    };

    override_rewire(settings_org, "init_dropdown_widgets", noop);
    override_rewire(settings_org, "initialize_group_setting_widgets", noop);
    $("#id_realm_message_content_edit_limit_minutes").set_parent(
        $.create("<stub edit limit custom input parent>"),
    );
    $("#id_realm_move_messages_within_stream_limit_minutes").set_parent(
        $.create("<stub move within stream custom input parent>"),
    );
    $("#id_realm_move_messages_between_streams_limit_minutes").set_parent(
        $.create("<stub move between streams custom input parent>"),
    );
    $("#id_realm_message_content_delete_limit_minutes").set_parent(
        $.create("<stub delete limit custom input parent>"),
    );
    const $stub_message_content_edit_limit_parent = $.create(
        "<stub message_content_edit_limit parent",
    );
    $("#id_realm_message_content_edit_limit_seconds").set_parent(
        $stub_message_content_edit_limit_parent,
    );

    const $stub_move_within_stream_limit_parent = $.create("<stub move_within_stream_limit parent");
    $("#id_realm_move_messages_within_stream_limit_seconds").set_parent(
        $stub_move_within_stream_limit_parent,
    );

    const $stub_move_between_streams_limit_parent = $.create(
        "<stub move_between_streams_limit parent",
    );
    $("#id_realm_move_messages_between_streams_limit_seconds").set_parent(
        $stub_move_between_streams_limit_parent,
    );

    const $stub_message_content_delete_limit_parent = $.create(
        "<stub message_content_delete_limit parent",
    );
    $("#id_realm_message_content_delete_limit_seconds").set_parent(
        $stub_message_content_delete_limit_parent,
    );

    const $custom_edit_limit_input = $("#id_realm_message_content_edit_limit_minutes");
    $stub_message_content_edit_limit_parent.set_find_results(
        ".time-limit-custom-input",
        $custom_edit_limit_input,
    );
    $custom_edit_limit_input.attr("id", "id_realm_message_content_edit_limit_minutes");

    const $custom_move_within_stream_limit_input = $(
        "#id_realm_move_messages_within_stream_limit_minutes",
    );
    $stub_move_within_stream_limit_parent.set_find_results(
        ".time-limit-custom-input",
        $custom_move_within_stream_limit_input,
    );
    $custom_move_within_stream_limit_input.attr(
        "id",
        "id_realm_move_messages_within_stream_limit_minutes",
    );

    const $custom_move_between_streams_limit_input = $(
        "#id_realm_move_messages_between_streams_limit_minutes",
    );
    $stub_move_between_streams_limit_parent.set_find_results(
        ".time-limit-custom-input",
        $custom_move_between_streams_limit_input,
    );
    $custom_move_between_streams_limit_input.attr(
        "id",
        "id_realm_move_messages_between_streams_limit_minutes",
    );

    const $custom_delete_limit_input = $("#id_realm_message_content_delete_limit_minutes");
    $stub_message_content_delete_limit_parent.set_find_results(
        ".time-limit-custom-input",
        $custom_delete_limit_input,
    );
    $custom_delete_limit_input.attr("id", "id_realm_message_content_delete_limit_minutes");

    const $stub_realm_message_retention_parent = $.create(
        "<stub message retention setting parent>",
    );
    const $realm_message_retention_custom_input = $("#id_realm_message_retention_custom_input");
    $("#id_realm_message_retention_days").set_parent($stub_realm_message_retention_parent);
    $realm_message_retention_custom_input.set_parent($stub_realm_message_retention_parent);
    $stub_realm_message_retention_parent.set_find_results(
        ".message-retention-setting-custom-input",
        $realm_message_retention_custom_input,
    );
    $realm_message_retention_custom_input.attr("id", "id_realm_message_retention_custom_input");

    const $stub_realm_waiting_period_threshold_parent = $.create(
        "<stub waiting period threshold setting parent>",
    );
    const $realm_waiting_period_threshold_custom_input = $(
        "#id_realm_waiting_period_threshold_custom_input",
    );
    $("#id_realm_waiting_period_threshold").set_parent($stub_realm_waiting_period_threshold_parent);
    $realm_waiting_period_threshold_custom_input.set_parent(
        $stub_realm_waiting_period_threshold_parent,
    );
    $stub_realm_waiting_period_threshold_parent.set_find_results(
        ".time-limit-custom-input",
        $realm_waiting_period_threshold_custom_input,
    );
    $realm_waiting_period_threshold_custom_input.attr(
        "id",
        "id_realm_waiting_period_threshold_custom_input",
    );

    $("#message_content_in_email_notifications_label").set_parent(
        $.create("<stub in-content setting checkbox>"),
    );
    $("#enable_digest_emails_label").set_parent($.create("<stub digest setting checkbox>"));
    $("#id_realm_digest_weekday").set_parent($.create("<stub digest weekday setting dropdown>"));
    $("#allowed_domains_label").set_parent($.create("<stub-allowed-domain-label-parent>"));
    const $waiting_period_parent_elem = $.create("waiting-period-parent-stub");
    $("#id_realm_waiting_period_threshold").set_parent($waiting_period_parent_elem);
    $("#id_realm_can_create_web_public_channel_group").set_parent(
        $.create("<stub-can-create-web-public-channel-group-parent>"),
    );

    // Make our plan not limited so we don't have to stub all the
    // elements involved in disabling the can_create_groups input.
    override(realm, "zulip_plan_is_not_limited", true);

    override_rewire(settings_components, "get_input_element_value", (elem) => $(elem).val());

    // TEST set_up() here, but this mostly just allows us to
    // get access to the click handlers.
    override(current_user, "is_owner", true);
    settings_org.set_up();

    test_submit_settings_form(
        override,
        $(".admin-realm-form").get_on_handler(
            "click",
            ".subsection-header .subsection-changes-save .save-button[data-status='unsaved']",
        ),
    );
    test_upload_realm_icon(override, upload_realm_logo_or_icon);
    test_extract_property_name();
    test_change_save_button_state();
    test_sync_realm_settings({override});
    test_parse_time_limit({override});
    test_discard_changes_button(
        {override},
        $(".admin-realm-form").get_on_handler(
            "click",
            ".subsection-header .subsection-changes-discard button",
        ),
    );
});

test("test get_organization_settings_options", () => {
    const sorted_option_values = settings_org.get_organization_settings_options();
    const sorted_common_policy_values = sorted_option_values.common_policy_values;
    const expected_common_policy_values = [
        {
            key: "by_admins_only",
            order: 1,
            code: 2,
            description: $t({defaultMessage: "Admins"}),
        },
        {
            key: "by_moderators_only",
            order: 2,
            code: 4,
            description: $t({defaultMessage: "Admins and moderators"}),
        },
        {
            key: "by_full_members",
            order: 3,
            code: 3,
            description: $t({defaultMessage: "Admins, moderators and full members"}),
        },
        {
            key: "by_members",
            order: 4,
            code: 1,
            description: $t({defaultMessage: "Admins, moderators and members"}),
        },
    ];
    assert.deepEqual(sorted_common_policy_values, expected_common_policy_values);
});

test("test get_sorted_options_list", () => {
    const option_values_1 = {
        by_admins_only: {
            order: 3,
            code: 2,
            description: $t({defaultMessage: "Admins"}),
        },
        by_members: {
            order: 2,
            code: 1,
            description: $t({defaultMessage: "Admins, moderators and members"}),
        },
        by_full_members: {
            order: 1,
            code: 3,
            description: $t({defaultMessage: "Admins, moderators and full members"}),
        },
    };
    let expected_option_values = [
        {
            key: "by_full_members",
            order: 1,
            code: 3,
            description: $t({defaultMessage: "Admins, moderators and full members"}),
        },
        {
            key: "by_members",
            order: 2,
            code: 1,
            description: $t({defaultMessage: "Admins, moderators and members"}),
        },
        {
            key: "by_admins_only",
            order: 3,
            code: 2,
            description: $t({defaultMessage: "Admins"}),
        },
    ];
    assert.deepEqual(
        settings_components.get_sorted_options_list(option_values_1),
        expected_option_values,
    );

    const option_values_2 = {
        by_admins_only: {
            code: 1,
            description: $t({defaultMessage: "Admins"}),
        },
        by_members: {
            code: 2,
            description: $t({defaultMessage: "Admins, moderators and members"}),
        },
        by_full_members: {
            code: 3,
            description: $t({defaultMessage: "Admins, moderators and full members"}),
        },
    };
    expected_option_values = [
        {
            key: "by_admins_only",
            code: 1,
            description: $t({defaultMessage: "Admins"}),
        },
        {
            key: "by_full_members",
            code: 3,
            description: $t({defaultMessage: "Admins, moderators and full members"}),
        },
        {
            key: "by_members",
            code: 2,
            description: $t({defaultMessage: "Admins, moderators and members"}),
        },
    ];
    assert.deepEqual(
        settings_components.get_sorted_options_list(option_values_2),
        expected_option_values,
    );
});

test("test combined_code_language_options", ({override}) => {
    const default_options = Object.keys(pygments_data.langs).map((x) => ({
        name: x,
        unique_id: x,
    }));

    const expected_options_without_realm_playgrounds = [
        {
            is_setting_disabled: true,
            unique_id: "",
            name: $t({defaultMessage: "No language set"}),
            show_disabled_icon: true,
            show_disabled_option_name: false,
        },
        ...default_options,
    ];

    const options_without_realm_playgrounds = settings_org.combined_code_language_options();
    assert.deepEqual(options_without_realm_playgrounds, expected_options_without_realm_playgrounds);

    override(realm, "realm_playgrounds", [
        {pygments_language: "custom_lang_1"},
        {pygments_language: "custom_lang_2"},
    ]);

    const expected_options_with_realm_playgrounds = [
        {
            is_setting_disabled: true,
            unique_id: "",
            name: $t({defaultMessage: "No language set"}),
            show_disabled_icon: true,
            show_disabled_option_name: false,
        },
        {unique_id: "custom_lang_1", name: "custom_lang_1"},
        {unique_id: "custom_lang_2", name: "custom_lang_2"},
        ...default_options,
    ];

    const options_with_realm_playgrounds = settings_org.combined_code_language_options();
    assert.deepEqual(options_with_realm_playgrounds, expected_options_with_realm_playgrounds);
});

test("misc", ({override}) => {
    override(current_user, "is_admin", false);
    $("#user-avatar-upload-widget").length = 1;
    $("#user_details_section").length = 1;

    override(realm, "realm_name_changes_disabled", false);
    override(realm, "server_name_changes_disabled", false);
    settings_account.update_name_change_display();
    assert.ok(!$("#full_name").prop("disabled"));
    assert.ok(!$("#full_name_input_container").hasClass("disabled_setting_tooltip"));
    assert.ok(!$("label[for='full_name']").hasClass("cursor-text"));

    override(realm, "realm_name_changes_disabled", true);
    override(realm, "server_name_changes_disabled", false);
    settings_account.update_name_change_display();
    assert.ok($("#full_name").prop("disabled"));
    assert.ok($("#full_name_input_container").hasClass("disabled_setting_tooltip"));
    assert.ok($("label[for='full_name']").hasClass("cursor-text"));

    override(realm, "realm_name_changes_disabled", true);
    override(realm, "server_name_changes_disabled", true);
    settings_account.update_name_change_display();
    assert.ok($("#full_name").prop("disabled"));
    assert.ok($("#full_name_input_container").hasClass("disabled_setting_tooltip"));
    assert.ok($("label[for='full_name']").hasClass("cursor-text"));

    override(realm, "realm_name_changes_disabled", false);
    override(realm, "server_name_changes_disabled", true);
    settings_account.update_name_change_display();
    assert.ok($("#full_name").prop("disabled"));
    assert.ok($("#full_name_input_container").hasClass("disabled_setting_tooltip"));
    assert.ok($("label[for='full_name']").hasClass("cursor-text"));

    override(realm, "realm_email_changes_disabled", false);
    settings_account.update_email_change_display();
    assert.ok(!$("#change_email_button").hasClass("hide"));
    assert.ok(!$("label[for='change_email_button']").hasClass("cursor-text"));

    override(realm, "realm_email_changes_disabled", true);
    settings_account.update_email_change_display();
    assert.ok($("#change_email_button").hasClass("hide"));
    assert.ok($("label[for='change_email_button']").hasClass("cursor-text"));

    override(realm, "realm_avatar_changes_disabled", false);
    override(realm, "server_avatar_changes_disabled", false);
    settings_account.update_avatar_change_display();
    assert.ok(!$("#user-avatar-upload-widget .image_upload_button").hasClass("hide"));
    override(realm, "realm_avatar_changes_disabled", true);
    override(realm, "server_avatar_changes_disabled", false);
    settings_account.update_avatar_change_display();
    assert.ok($("#user-avatar-upload-widget .image_upload_button").hasClass("hide"));
    override(realm, "realm_avatar_changes_disabled", false);
    override(realm, "server_avatar_changes_disabled", true);
    settings_account.update_avatar_change_display();
    assert.ok($("#user-avatar-upload-widget .image_upload_button").hasClass("hide"));
    override(realm, "realm_avatar_changes_disabled", true);
    override(realm, "server_avatar_changes_disabled", true);
    settings_account.update_avatar_change_display();
    assert.ok($("#user-avatar-upload-widget .image_upload_button").hasClass("hide"));

    // If organization admin, these UI elements are never disabled.
    override(current_user, "is_admin", true);
    settings_account.update_name_change_display();
    assert.ok(!$("#full_name").prop("disabled"));
    assert.ok(!$("#full_name_input_container").hasClass("disabled_setting_tooltip"));
    assert.ok(!$("label[for='full_name']").hasClass("cursor-text"));

    settings_account.update_email_change_display();
    assert.ok(!$("#change_email_button").hasClass("hide"));

    settings_account.update_avatar_change_display();
    assert.ok(!$("#user-avatar-upload-widget .image_upload_button").hasClass("hide"));
});
