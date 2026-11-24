"use strict";

const assert = require("node:assert/strict");

const {make_realm} = require("./lib/example_realm.cjs");
const {$t} = require("./lib/i18n.cjs");
const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const realm_icon = mock_esm("../src/realm_icon");

const channel = mock_esm("../src/channel");

mock_esm("../src/csrf", {csrf_token: "token-stub"});
mock_esm("../src/loading", {
    make_indicator: noop,
    destroy_indicator: noop,
});
mock_esm("../src/settings_banner", {set_up_upgrade_banners: noop});
mock_esm("../src/buttons", {
    show_button_loading_indicator: noop,
    hide_button_loading_indicator: noop,
    modify_action_button_style: noop,
});
mock_esm("../src/scroll_util", {scroll_element_into_container: noop});
mock_esm("../src/ui_util", {
    disable_element_and_add_tooltip: noop,
    enable_element_and_remove_tooltip($element) {
        $element.prop("disabled", false);
    },
});
set_global("document", "document-stub");

set_global("requestAnimationFrame", (func) => func());

const settings_account = zrequire("settings_account");
const settings_components = zrequire("settings_components");
const settings_config = zrequire("settings_config");
const settings_org = zrequire("settings_org");
const {set_current_user, set_realm} = zrequire("state_data");
const pygments_data = zrequire("pygments_data");
const {initialize: initialize_realm_user_settings_defaults} = zrequire(
    "realm_user_settings_defaults",
);
const {initialize_user_settings} = zrequire("user_settings");

const current_user = {};
set_current_user(current_user);
const realm = make_realm();
set_realm(realm);
const realm_user_settings_defaults = {};
initialize_realm_user_settings_defaults({realm_user_settings_defaults});
initialize_user_settings({user_settings: {}});

function test(label, f) {
    run_test(label, (helpers) => {
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
    $stub_save_button_header.set_find_results(".alert-notification", $("<failed-status-stub>"));
    $stub_save_button.set_closest_results(".settings-subsection-parent", $stub_save_button_header);
    $save_button_controls.set_parent($stub_save_button_header);
    $save_button_controls.set_find_results(".save-button", $stub_save_button);
    $stub_save_button.set_find_results(".action-button-label", $stub_save_button_text);
    $stub_save_button_header.set_find_results(".save-button-controls", $save_button_controls);
    $stub_save_button_header.set_find_results(
        ".subsection-changes-discard button",
        $stub_discard_button,
    );
    $save_button_controls.set_find_results(".discard-button", $stub_discard_button);

    $save_button_controls.set_closest_results(
        ".settings-subsection-parent",
        $stub_save_button_header,
    );
    $stub_save_button_header.set_find_results(".time-limit-setting", []);
    $stub_save_button_header.set_find_results(".pill-container.prop-element", []);
    $stub_save_button_header.set_find_results(".subsection-changes-save button", $stub_save_button);
    $stub_save_button_header.set_find_results(".save-button", $stub_save_button);

    return {
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
    let $save_button_header = stubs.$save_button_header;
    $save_button_header.attr("id", `org-${subsection}`);

    $("#id_realm_waiting_period_threshold").val(10);

    subsection = "user-defaults";
    stubs = createSaveButtons(subsection);
    const $save_button = stubs.$save_button;
    $save_button_header = stubs.$save_button_header;
    $save_button_header.attr("id", `org-${subsection}`);

    const $realm_topics_policy_elem = $("#id_realm_topics_policy");
    $realm_topics_policy_elem.val("disable_empty_topic");
    $realm_topics_policy_elem.attr("id", "id_realm_topics_policy");

    const $subsection_elem = $(`#org-${CSS.escape(subsection)}`);
    $subsection_elem.set_find_results(".prop-element", [$realm_topics_policy_elem]);

    submit_form.call({to_$: () => $(".save-button")}, ev);
    assert.ok(patched);

    const expected_value = {
        topics_policy: "disable_empty_topic",
    };
    assert.deepEqual(data, expected_value);

    // Testing only once for since callback is same for all cases
    success_callback();
    assert.equal(stubs.$save_button_controls.visible(), false);
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
    } = createSaveButtons("msg-editing");
    $save_button_header.attr("id", "org-msg-editing");
    $save_button_header.set_matches(".subsection-header", true);
    $save_button_header.set_closest_results(".channel-permissions", {});

    {
        settings_components.change_save_button_state($save_button_controls, "unsaved");
        assert.equal($save_button_text.text(), "translated: Save changes");
        assert.equal($save_button_controls.visible(), true);
        assert.equal($save_button.attr("data-status"), "unsaved");
        assert.equal($discard_button.visible(), true);
    }
    {
        settings_components.change_save_button_state($save_button_controls, "discarded");
        assert.equal($save_button_controls.visible(), false);
    }
    {
        settings_components.change_save_button_state($save_button_controls, "saving");
        assert.equal($save_button.attr("data-status"), "saving");
        assert.equal($discard_button.visible(), false);
    }
    {
        // The "discarded" state should not interfere during the saving stage.
        settings_components.change_save_button_state($save_button_controls, "discarded");
        assert.equal($save_button_controls.visible(), true);
    }
    {
        settings_components.change_save_button_state($save_button_controls, "succeeded");
        assert.equal($save_button_controls.visible(), false);
        assert.equal($save_button.attr("data-status"), "saved");
        assert.equal($save_button_text.text(), "translated: Saved");
    }
    {
        let error_callback_called = false;
        function error_callback() {
            error_callback_called = true;
        }
        settings_components.change_save_button_state(
            $save_button_controls,
            "failed",
            error_callback,
        );
        assert.equal($save_button_controls.visible(), false);
        assert.equal(error_callback_called, true);
    }
}

function test_upload_realm_icon(override, upload_realm_logo_or_icon) {
    const file = "image1.png";

    let posted;
    override(channel, "post", (req) => {
        posted = true;
        assert.equal(req.url, "/json/realm/icon");
        assert.equal(req.data.get("csrfmiddlewaretoken"), "token-stub");
        assert.deepEqual(req.data.get("file"), file);
    });

    upload_realm_logo_or_icon(file, null, true);
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
        $property_elem.attr("id", "id_realm_message_content_edit_limit_minutes");
        $property_dropdown_elem.attr("id", "id_realm_message_content_edit_limit_seconds");
        $property_dropdown_elem.set_closest_results(
            ".settings-subsection-parent",
            $subsection_stub,
        );

        override(realm, "realm_message_content_edit_limit_seconds", 120);

        settings_org.sync_realm_settings("message_content_edit_limit_seconds");
        assert.equal($("#id_realm_message_content_edit_limit_minutes").val(), "2");
        assert.equal($("#id_realm_message_content_edit_limit_unit").val(), "minutes");

        override(realm, "realm_message_content_edit_limit_seconds", 1209600);
        settings_org.sync_realm_settings("message_content_edit_limit_seconds");
        assert.equal($("#id_realm_message_content_edit_limit_seconds").val(), "custom_period");
        assert.equal($("#id_realm_message_content_edit_limit_minutes").val(), "2");
        assert.equal($("#id_realm_message_content_edit_limit_unit").val(), "weeks");
    }

    {
        /* Test message content edit limit dropdown value sync */
        override(realm, "realm_message_content_edit_limit_seconds", 120);
        settings_org.sync_realm_settings("message_content_edit_limit_seconds");
        assert.equal($("#id_realm_message_content_edit_limit_seconds").val(), "120");
        assert.equal($("#id_realm_message_content_edit_limit_unit").val(), "minutes");

        override(realm, "realm_message_content_edit_limit_seconds", 130);
        settings_org.sync_realm_settings("message_content_edit_limit_seconds");
        assert.equal($("#id_realm_message_content_edit_limit_seconds").val(), "custom_period");
        assert.equal($("#id_realm_message_content_edit_limit_minutes").val(), "2.2");
        assert.equal($("#id_realm_message_content_edit_limit_unit").val(), "minutes");
    }

    {
        /* Test organization joining restrictions settings sync */
        const $property_elem = $("#id_realm_org_join_restrictions");
        $property_elem.attr("id", "id_realm_org_join_restrictions");
        $property_elem.set_closest_results(".settings-subsection-parent", $subsection_stub);

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
    const $unit_elem = $("#id_realm_message_content_edit_limit_unit");
    const $dependent_block = $.create("<dependent-settings-block-stub>");
    $elem.set_closest_results(".dependent-settings-block", $dependent_block);

    const test_function = (
        value,
        expected_value = value,
        unit,
        expected_custom_input_values,
        expected_seconds,
    ) => {
        $elem.val(value);
        if (unit === undefined) {
            $dependent_block.set_find_results(".time-limit-custom-unit", []);
        } else {
            $dependent_block.set_find_results(".time-limit-custom-unit", $unit_elem);
            $unit_elem.val(unit);
        }
        const parsed_seconds = settings_components.parse_time_limit($elem);
        if (expected_seconds !== undefined) {
            assert.equal(parsed_seconds, expected_seconds);
        }
        override(realm, "realm_message_content_edit_limit_seconds", parsed_seconds);
        assert.equal(
            settings_components.get_realm_time_limits_in_minutes(
                "realm_message_content_edit_limit_seconds",
            ),
            expected_value,
        );
        if (expected_custom_input_values !== undefined) {
            const custom_input_values =
                settings_components.get_realm_time_limit_custom_input_values(
                    "realm_message_content_edit_limit_seconds",
                );
            assert.deepEqual(custom_input_values, expected_custom_input_values);

            // Round-trip: re-parsing the loaded value and unit yields the exact same seconds.
            $elem.val(custom_input_values.value);
            $unit_elem.val(custom_input_values.unit);
            assert.equal(settings_components.parse_time_limit($elem), parsed_seconds);
        }
    };

    test_function("0.01", "0");
    test_function("0.1");
    test_function("0.122", "0.1");
    test_function("0.155", "0.2");
    test_function("0.150", "0.1");
    test_function("0.5");
    test_function("1");
    test_function("1.1");
    test_function("1.5", "1.5", "minutes", {value: "1.5", unit: "minutes"}, 90);
    test_function("10.5");
    test_function("50.3");
    test_function("90", "90", "minutes", {value: "90", unit: "minutes"}, 5400);
    test_function("100");
    test_function("100.1");
    test_function("120", "120", "minutes", {value: "2", unit: "hours"}, 7200);
    test_function("127.79", "127.8");
    test_function("201.1");
    test_function("501.15", "501.1");
    test_function("501.34", "501.3");
    test_function("0.5", "30", "hours", {value: "30", unit: "minutes"}, 1800);
    test_function("1.25", "75", "hours", {value: "75", unit: "minutes"}, 4500);
    test_function("2.", "120", "hours", {value: "2", unit: "hours"}, 7200);
    test_function("2", "120", "hours", {value: "2", unit: "hours"}, 7200);

    // Whole-second inputs that are not multiples of 6 seconds (e.g., 1.0625 hours = 3825s)
    // round-trip cleanly via 2-decimal minutes (63.75 minutes).
    $elem.val("1.0625");
    $unit_elem.val("hours");
    assert.equal(settings_components.parse_time_limit($elem), 3825);
    override(realm, "realm_message_content_edit_limit_seconds", 3825);
    const quarter_minute_values = settings_components.get_realm_time_limit_custom_input_values(
        "realm_message_content_edit_limit_seconds",
    );
    assert.deepEqual(quarter_minute_values, {value: "63.75", unit: "minutes"});
    $elem.val(quarter_minute_values.value);
    $unit_elem.val(quarter_minute_values.unit);
    assert.equal(settings_components.parse_time_limit($elem), 3825);

    // Non-exact inputs with a unit dropdown return NaN rather than silently rounding.
    $dependent_block.set_find_results(".time-limit-custom-unit", $unit_elem);
    $unit_elem.val("minutes");
    $elem.val("0.122");
    assert.ok(Number.isNaN(settings_components.parse_time_limit($elem)));
    $unit_elem.val("hours");
    $elem.val("1.0001");
    assert.ok(Number.isNaN(settings_components.parse_time_limit($elem)));
    test_function("24", "1440", "hours", {value: "1", unit: "days"}, 86400);
    test_function("3", "4320", "days", {value: "3", unit: "days"}, 259200);
    test_function("14", "20160", "days", {value: "2", unit: "weeks"}, 1209600);
    test_function("1.3", "13104", "weeks", {value: "13104", unit: "minutes"}, 786240);
    test_function("1.01", "10180.8", "weeks", {value: "10180.8", unit: "minutes"}, 610848);
    test_function("2", "20160", "weeks", {value: "2", unit: "weeks"}, 1209600);

    // Null ("Any time") resets custom input to empty string and minutes.
    override(realm, "realm_message_content_edit_limit_seconds", null);
    assert.deepEqual(
        settings_components.get_realm_time_limit_custom_input_values(
            "realm_message_content_edit_limit_seconds",
        ),
        {value: "", unit: "minutes"},
    );
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
    const $message_content_edit_limit_unit = $("#id_realm_message_content_edit_limit_unit").val(
        "days",
    );
    const $msg_delete_limit_setting = $("#id_realm_message_content_delete_limit_seconds").val(
        "custom_period",
    );
    const $message_content_delete_limit_minutes = $(
        "#id_realm_message_content_delete_limit_minutes",
    ).val(130);
    const $message_content_delete_limit_unit = $("#id_realm_message_content_delete_limit_unit").val(
        "weeks",
    );

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

    const {$discard_button, $save_button_controls} = createSaveButtons("msg-editing");
    $discard_button.set_closest_results(".settings-subsection-parent", $discard_button_parent);

    $discard_button_parent.set_find_results(".save-button-controls", $save_button_controls);

    discard_changes.call({to_$: () => $(".discard-button")}, ev);

    assert.equal(
        $message_edit_history_visibility_policy.val(),
        settings_config.message_edit_history_visibility_policy_values.always.code,
    );
    assert.equal($msg_edit_limit_setting.val(), "3600");
    assert.equal($message_content_edit_limit_minutes.val(), "1");
    assert.equal($message_content_edit_limit_unit.val(), "hours");
    assert.equal($msg_delete_limit_setting.val(), "120");
    assert.equal($message_content_delete_limit_minutes.val(), "2");
    assert.equal($message_content_delete_limit_unit.val(), "minutes");
    assert.ok(!$save_button_controls.visible());

    // Discarding edits to a saved custom value (2 weeks) restores Custom + 2 + weeks,
    // and discarding an unchecked "Allow message editing" re-enables all 3 sub-settings.
    override(realm, "realm_allow_message_editing", true);
    override(realm, "realm_message_content_edit_limit_seconds", 1209600);
    const $allow_message_editing = $("#id_realm_allow_message_editing");
    $allow_message_editing.attr("id", "id_realm_allow_message_editing");
    $allow_message_editing.prop("checked", false);
    $msg_edit_limit_setting.prop("disabled", true);
    $message_content_edit_limit_minutes.val("5").prop("disabled", true);
    $message_content_edit_limit_unit.val("days").prop("disabled", true);

    $discard_button_parent.set_find_results(".prop-element", [
        $allow_message_editing,
        $msg_edit_limit_setting,
    ]);
    discard_changes.call({to_$: () => $(".discard-button")}, ev);

    assert.equal($allow_message_editing.prop("checked"), true);
    assert.equal($msg_edit_limit_setting.prop("disabled"), false);
    assert.equal($message_content_edit_limit_minutes.prop("disabled"), false);
    assert.equal($message_content_edit_limit_unit.prop("disabled"), false);
    assert.equal($msg_edit_limit_setting.val(), "custom_period");
    assert.equal($message_content_edit_limit_minutes.val(), "2");
    assert.equal($message_content_edit_limit_unit.val(), "weeks");
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
        constructor_groups: {
            id: 6,
            name: "Constructor Groups",
        },
        nextcloud_talk: {
            id: 7,
            name: "Nextcloud Talk",
        },
        webex: {
            id: 8,
            name: "Webex",
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
    $stub_message_content_edit_limit_parent.set_find_results(
        ".time-limit-custom-unit",
        $("#id_realm_message_content_edit_limit_unit"),
    );
    $custom_edit_limit_input.attr("id", "id_realm_message_content_edit_limit_minutes");

    const $custom_move_within_stream_limit_input = $(
        "#id_realm_move_messages_within_stream_limit_minutes",
    );
    $stub_move_within_stream_limit_parent.set_find_results(
        ".time-limit-custom-input",
        $custom_move_within_stream_limit_input,
    );
    $stub_move_within_stream_limit_parent.set_find_results(
        ".time-limit-custom-unit",
        $("#id_realm_move_messages_within_stream_limit_unit"),
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
    $stub_move_between_streams_limit_parent.set_find_results(
        ".time-limit-custom-unit",
        $("#id_realm_move_messages_between_streams_limit_unit"),
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
    $stub_message_content_delete_limit_parent.set_find_results(
        ".time-limit-custom-unit",
        $("#id_realm_message_content_delete_limit_unit"),
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
    override(realm, "realm_welcome_message_custom_text", "");
    $("#id_realm_welcome_message_custom_text").set_parent(
        $.create("<stub welcome message custom text>"),
    );
    override_rewire(settings_components, "resize_textareas_in_subsection", noop);

    override_rewire(settings_org, "set_two_tier_billing_settings_visibility", noop);

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

    // Toggling "Allow message editing" synchronizes disabled state on the unit dropdown.
    const allow_edit_change_handler = $("input#id_realm_allow_message_editing").get_on_handler(
        "change",
    );
    allow_edit_change_handler.call({checked: false});
    assert.equal($("#id_realm_message_content_edit_limit_seconds").prop("disabled"), true);
    assert.equal($("#id_realm_message_content_edit_limit_minutes").prop("disabled"), true);
    assert.equal($("#id_realm_message_content_edit_limit_unit").prop("disabled"), true);
    allow_edit_change_handler.call({checked: true});
    assert.equal($("#id_realm_message_content_edit_limit_seconds").prop("disabled"), false);
    assert.equal($("#id_realm_message_content_edit_limit_minutes").prop("disabled"), false);
    assert.equal($("#id_realm_message_content_edit_limit_unit").prop("disabled"), false);

    // Switching the main dropdown to Custom populates both custom value and unit.
    override(realm, "realm_message_content_edit_limit_seconds", 1209600);
    $("#id_realm_message_content_edit_limit_seconds").val("custom_period");
    $("#id_realm_message_content_edit_limit_minutes").val("");
    $("#id_realm_message_content_edit_limit_unit").val("minutes");
    settings_components.update_custom_value_input("realm_message_content_edit_limit_seconds");
    assert.equal($("#id_realm_message_content_edit_limit_minutes").val(), "2");
    assert.equal($("#id_realm_message_content_edit_limit_unit").val(), "weeks");
});

test("custom time limit save validation and change detection", ({override}) => {
    const select_elements = new Set();
    const register_select = ($el) => {
        select_elements.add($el);
        if ($el[0] !== undefined) {
            select_elements.add($el[0]);
        }
    };
    override(global, "HTMLSelectElement", {
        [Symbol.hasInstance]: (instance) => select_elements.has(instance),
    });
    const {$save_button, $save_button_controls, $save_button_header} =
        createSaveButtons("msg-editing");
    $save_button_header.attr("id", "org-msg-editing");
    $save_button_header.set_matches(".subsection-header", true);
    $save_button_header.set_closest_results(".channel-permissions", []);
    $save_button_header.set_closest_results(".advanced-configurations-container", []);

    const $setting_elem = $.create("<time-limit-setting-stub>");
    const $dropdown_elem = $("#id_realm_message_content_edit_limit_seconds");
    const $custom_input_elem = $("#id_realm_message_content_edit_limit_minutes");
    const $unit_elem = $("#id_realm_message_content_edit_limit_unit");
    const $dependent_block = $.create("<dependent-settings-block-stub>");
    const $settings_section = $.create("<settings-section-stub>");

    register_select($dropdown_elem);
    register_select($unit_elem);
    $dropdown_elem.attr("id", "id_realm_message_content_edit_limit_seconds");
    $dropdown_elem.attr("data-setting-widget-type", "time-limit");
    $dropdown_elem.set_parent($setting_elem);
    $dropdown_elem.set_closest_results(".settings-section.show", $settings_section);
    $custom_input_elem.set_closest_results(".dependent-settings-block", $dependent_block);
    $dependent_block.set_find_results(".time-limit-custom-unit", $unit_elem);

    $setting_elem.set_find_results(
        "select:not([multiple]):not(.time-limit-custom-unit)",
        $dropdown_elem,
    );
    $setting_elem.set_find_results("input.time-limit-custom-input", $custom_input_elem);
    $save_button_header.set_find_results(".time-limit-setting", [$setting_elem]);
    $save_button_header.set_find_results(".prop-element", [$dropdown_elem]);
    $save_button_header.set_find_results(
        ".subsection-header .save-button-controls",
        $save_button_controls,
    );
    $save_button_header.set_find_results(".alert-notification", $.create("<alert-stub>"));
    $save_button_header.set_find_results(".save-button", $save_button);

    override(realm, "realm_message_content_edit_limit_seconds", 600);
    $dropdown_elem.val("custom_period");

    const check_state = (value, unit) => {
        $custom_input_elem.val(value);
        $unit_elem.val(unit);
        settings_components.save_discard_realm_settings_widget_status_handler($save_button_header);
    };

    // Same duration (10 minutes = 600s): no unsaved changes.
    check_state("10", "minutes");
    assert.equal($save_button_controls.visible(), false);

    // Changing only the unit dropdown triggers change detection and enables saving.
    check_state("10", "hours");
    assert.equal($save_button_controls.visible(), true);
    assert.equal($save_button.prop("disabled"), false);
    assert.equal(settings_components.get_input_element_value($dropdown_elem), 36000);

    // Fractional inputs that map to exact 0.1-minute increments are valid.
    check_state("0.5", "hours");
    assert.equal($save_button_controls.visible(), true);
    assert.equal($save_button.prop("disabled"), false);
    assert.equal(settings_components.get_input_element_value($dropdown_elem), 1800);

    check_state("1.25", "hours");
    assert.equal($save_button.prop("disabled"), false);
    assert.equal(settings_components.get_input_element_value($dropdown_elem), 4500);

    check_state("2.", "hours");
    assert.equal($save_button.prop("disabled"), false);
    assert.equal(settings_components.get_input_element_value($dropdown_elem), 7200);

    check_state("1.0625", "hours");
    assert.equal($save_button.prop("disabled"), false);
    assert.equal(settings_components.get_input_element_value($dropdown_elem), 3825);

    check_state("1.3", "weeks");
    assert.equal($save_button.prop("disabled"), false);
    assert.equal(settings_components.get_input_element_value($dropdown_elem), 786240);

    check_state("1.01", "weeks");
    assert.equal($save_button.prop("disabled"), false);
    assert.equal(settings_components.get_input_element_value($dropdown_elem), 610848);

    // Inputs that would lose precision on round-trip disable Save rather than silently rounding.
    check_state("1.001", "hours");
    assert.equal($save_button_controls.visible(), true);
    assert.equal($save_button.prop("disabled"), true);

    check_state("0.122", "minutes");
    assert.equal($save_button.prop("disabled"), true);

    check_state("0.01", "minutes");
    assert.equal($save_button.prop("disabled"), true);

    // Upper bound (32-bit signed integer seconds = 2147483647) and invalid inputs.
    check_state("3550", "weeks");
    assert.equal($save_button.prop("disabled"), false);
    assert.equal(settings_components.get_input_element_value($dropdown_elem), 2147040000);

    check_state("3551", "weeks");
    assert.equal($save_button.prop("disabled"), true);

    check_state("0", "minutes");
    assert.equal($save_button.prop("disabled"), true);

    check_state("-5", "days");
    assert.equal($save_button.prop("disabled"), true);

    check_state("24a", "hours");
    assert.equal($save_button.prop("disabled"), true);

    // Invalid input that would round to the saved value (1.0001 hours ~= 3600s)
    // must remain a pending change with Save disabled and Discard visible.
    override(realm, "realm_message_content_edit_limit_seconds", 3600);
    check_state("1.0001", "hours");
    assert.equal($save_button_controls.visible(), true);
    assert.equal($save_button.prop("disabled"), true);

    // Neighbor setting without a unit dropdown (email_notifications_batching_period_seconds)
    // continues defaulting to minutes and validating properly.
    const $batch_section = $.create("<realm-default-settings-section>");
    $batch_section.attr("id", "realm-user-default-settings");
    const $batch_setting_elem = $.create("<batch-time-limit-setting-stub>");
    const $batch_dropdown = $("#realm_email_notifications_batching_period_seconds");
    const $batch_input = $("#realm_email_notification_batching_period_edit_minutes");
    const $batch_dependent_block = $.create("<batch-dependent-block-stub>");

    register_select($batch_dropdown);
    $batch_dropdown.attr("id", "realm_email_notifications_batching_period_seconds");
    $batch_dropdown.attr("data-setting-widget-type", "time-limit");
    $batch_dropdown.val("custom_period");
    $batch_dropdown.set_parent($batch_setting_elem);
    $batch_dropdown.set_closest_results(".settings-section.show", $batch_section);
    $batch_input.set_closest_results(".dependent-settings-block", $batch_dependent_block);
    $batch_dependent_block.set_find_results(".time-limit-custom-unit", []);

    $batch_setting_elem.set_find_results(
        "select:not([multiple]):not(.time-limit-custom-unit)",
        $batch_dropdown,
    );
    $batch_setting_elem.set_find_results("input.time-limit-custom-input", $batch_input);
    $save_button_header.set_find_results(".time-limit-setting", [$batch_setting_elem]);
    $save_button_header.set_find_results(".prop-element", [$batch_dropdown]);

    override(realm_user_settings_defaults, "email_notifications_batching_period_seconds", 120);
    // Preserves legacy behavior: 1.25 minutes is allowed and rounded to 1.3 min (78s),
    // while values < 1 minute (like 0.5 or 0.122) remain disabled.
    $batch_input.val("1.25");
    assert.equal(settings_components.parse_time_limit($batch_input), 78);
    settings_components.save_discard_default_realm_settings_widget_status_handler(
        $save_button_header,
    );
    assert.equal($save_button.prop("disabled"), false);

    $batch_input.val("0.5");
    settings_components.save_discard_default_realm_settings_widget_status_handler(
        $save_button_header,
    );
    assert.equal($save_button.prop("disabled"), true);

    $batch_input.val("0.122");
    settings_components.save_discard_default_realm_settings_widget_status_handler(
        $save_button_header,
    );
    assert.equal($save_button.prop("disabled"), true);

    $batch_input.val("0");
    settings_components.save_discard_default_realm_settings_widget_status_handler(
        $save_button_header,
    );
    assert.equal($save_button.prop("disabled"), true);

    // Waiting period threshold (days) keeps allowing 0 and rejecting negative/invalid values.
    const $waiting_setting_elem = $.create("<waiting-time-limit-setting-stub>");
    const $waiting_dropdown = $("#id_realm_waiting_period_threshold");
    const $waiting_input = $("#id_realm_waiting_period_threshold_custom_input");
    register_select($waiting_dropdown);
    $waiting_dropdown.attr("id", "id_realm_waiting_period_threshold");
    $waiting_dropdown.attr("data-setting-widget-type", "time-limit");
    $waiting_dropdown.val("custom_period");
    $waiting_dropdown.set_parent($waiting_setting_elem);
    $waiting_dropdown.set_closest_results(".settings-section.show", $settings_section);
    $waiting_setting_elem.set_find_results(
        "select:not([multiple]):not(.time-limit-custom-unit)",
        $waiting_dropdown,
    );
    $waiting_setting_elem.set_find_results("input.time-limit-custom-input", $waiting_input);
    $save_button_header.set_find_results(".time-limit-setting", [$waiting_setting_elem]);
    $save_button_header.set_find_results(".prop-element", [$waiting_dropdown]);
    override(realm, "realm_waiting_period_threshold", 3);

    $waiting_input.val("0");
    settings_components.save_discard_realm_settings_widget_status_handler($save_button_header);
    assert.equal($save_button.prop("disabled"), false);

    $waiting_input.val("-1");
    settings_components.save_discard_realm_settings_widget_status_handler($save_button_header);
    assert.equal($save_button.prop("disabled"), true);
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
