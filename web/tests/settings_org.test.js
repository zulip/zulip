"use strict";

const {strict: assert} = require("assert");

const {$t} = require("./lib/i18n");
const {mock_esm, zrequire, set_global} = require("./lib/namespace");
const {run_test, noop} = require("./lib/test");
const blueslip = require("./lib/zblueslip");
const $ = require("./lib/zjquery");
const {current_user, realm} = require("./lib/zpage_params");

const realm_icon = mock_esm("../src/realm_icon");

const channel = mock_esm("../src/channel");

mock_esm("../src/csrf", {csrf_token: "token-stub"});
mock_esm("../src/loading", {
    make_indicator: noop,
    destroy_indicator: noop,
});
mock_esm("../src/scroll_util", {scroll_element_into_container: noop});
set_global("document", "document-stub");

const settings_config = zrequire("settings_config");
const settings_bots = zrequire("settings_bots");
const settings_account = zrequire("settings_account");
const settings_components = zrequire("settings_components");
const settings_org = zrequire("settings_org");
const dropdown_widget = zrequire("dropdown_widget");

function test(label, f) {
    run_test(label, (helpers) => {
        $("#realm-icon-upload-widget .upload-spinner-background").css = noop;
        current_user.is_admin = false;
        realm.realm_domains = [
            {domain: "example.com", allow_subdomains: true},
            {domain: "example.org", allow_subdomains: false},
        ];
        realm.realm_authentication_methods = {};
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
    const $stub_save_button = $(".save-discard-widget-button.save-button");
    const $stub_discard_button = $(".save-discard-widget-button.discard-button");
    const $stub_save_button_text = $(".save-discard-widget-button-text");
    $stub_save_button_header.set_find_results(
        ".subsection-failed-status p",
        $("<failed-status-stub>"),
    );
    $stub_save_button.closest = () => $stub_save_button_header;
    $save_button_controls.set_find_results(".save-button", $stub_save_button);
    $stub_save_button.set_find_results(".save-discard-widget-button-text", $stub_save_button_text);
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
    $stub_save_button_header.set_find_results(".subsection-changes-save button", $stub_save_button);

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
        realm_bot_creation_policy: settings_bots.bot_creation_policy_values.restricted.code,
        realm_add_custom_emoji_policy: settings_config.common_policy_values.by_admins_only.code,
        realm_waiting_period_threshold: 1,
        realm_default_language: '"es"',
        realm_invite_to_stream_policy: settings_config.common_policy_values.by_admins_only.code,
        realm_create_private_stream_policy: settings_config.common_policy_values.by_members.code,
        realm_create_public_stream_policy: settings_config.common_policy_values.by_members.code,
        realm_invite_to_realm_policy: settings_config.common_policy_values.by_members.code,
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
    ev.currentTarget = ".save-discard-widget-button.save-button";
    let stubs = createSaveButtons(subsection);
    let $save_button = stubs.$save_button;
    let $save_button_header = stubs.$save_button_header;
    $save_button_header.attr("id", `org-${subsection}`);

    $("#id_realm_waiting_period_threshold").val(10);

    const $invite_to_stream_policy_elem = $("#id_realm_invite_to_stream_policy");
    $invite_to_stream_policy_elem.val("1");
    $invite_to_stream_policy_elem.attr("id", "id_realm_invite_to_stream_policy");
    $invite_to_stream_policy_elem.data = () => "number";

    const $create_public_stream_policy_elem = $("#id_realm_create_public_stream_policy");
    $create_public_stream_policy_elem.val("2");
    $create_public_stream_policy_elem.attr("id", "id_realm_create_public_stream_policy");
    $create_public_stream_policy_elem.data = () => "number";

    const $create_private_stream_policy_elem = $("#id_realm_create_private_stream_policy");
    $create_private_stream_policy_elem.val("2");
    $create_private_stream_policy_elem.attr("id", "id_realm_create_private_stream_policy");
    $create_private_stream_policy_elem.data = () => "number";

    const $add_custom_emoji_policy_elem = $("#id_realm_add_custom_emoji_policy");
    $add_custom_emoji_policy_elem.val("1");
    $add_custom_emoji_policy_elem.attr("id", "id_realm_add_custom_emoji_policy");
    $add_custom_emoji_policy_elem.data = () => "number";

    const $bot_creation_policy_elem = $("#id_realm_bot_creation_policy");
    $bot_creation_policy_elem.val("1");
    $bot_creation_policy_elem.attr("id", "id_realm_bot_creation_policy");
    $bot_creation_policy_elem.data = () => "number";

    const $invite_to_realm_policy_elem = $("#id_realm_invite_to_realm_policy");
    $invite_to_realm_policy_elem.val("2");
    $invite_to_realm_policy_elem.attr("id", "id_realm_invite_to_realm_policy");
    $invite_to_realm_policy_elem.data = () => "number";

    let $subsection_elem = $(`#org-${CSS.escape(subsection)}`);
    $subsection_elem.set_find_results(".prop-element", [
        $bot_creation_policy_elem,
        $add_custom_emoji_policy_elem,
        $create_public_stream_policy_elem,
        $create_private_stream_policy_elem,
        $invite_to_realm_policy_elem,
        $invite_to_stream_policy_elem,
    ]);

    patched = false;
    submit_form(ev);
    assert.ok(patched);

    let expected_value = {
        bot_creation_policy: 1,
        invite_to_realm_policy: 2,
        invite_to_stream_policy: 1,
        add_custom_emoji_policy: 1,
        create_public_stream_policy: 2,
        create_private_stream_policy: 2,
    };
    assert.deepEqual(data, expected_value);

    subsection = "user-defaults";
    ev.currentTarget = ".save-discard-widget-button.save-button";
    stubs = createSaveButtons(subsection);
    $save_button = stubs.$save_button;
    $save_button_header = stubs.$save_button_header;
    $save_button_header.attr("id", `org-${subsection}`);

    const $realm_default_language_elem = $("#id_realm_default_language");
    $realm_default_language_elem.val("en");
    $realm_default_language_elem.attr("id", "id_realm_default_language");
    $realm_default_language_elem.data = () => "string";

    $subsection_elem = $(`#org-${CSS.escape(subsection)}`);
    $subsection_elem.set_find_results(".prop-element", [$realm_default_language_elem]);

    submit_form(ev);
    assert.ok(patched);

    expected_value = {
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

    {
        settings_components.change_save_button_state($save_button_controls, "unsaved");
        assert.equal($save_button_text.text(), "translated: Save changes");
        assert.equal(props.hidden, false);
        assert.equal($save_button.attr("data-status"), "unsaved");
        assert.equal($discard_button.visible(), true);
    }
    {
        settings_components.change_save_button_state($save_button_controls, "saved");
        assert.equal($save_button_text.text(), "translated: Save changes");
        assert.equal(props.hidden, true);
        assert.equal($save_button.attr("data-status"), "");
    }
    {
        settings_components.change_save_button_state($save_button_controls, "saving");
        assert.equal($save_button_text.text(), "translated: Saving");
        assert.equal($save_button.attr("data-status"), "saving");
        assert.equal($save_button.hasClass("saving"), true);
        assert.equal($discard_button.visible(), false);
    }
    {
        settings_components.change_save_button_state($save_button_controls, "discarded");
        assert.equal(props.hidden, true);
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

function test_sync_realm_settings() {
    {
        /* Test invalid settings property sync */
        const $property_elem = $("#id_realm_invalid_settings_property");
        $property_elem.attr("id", "id_realm_invalid_settings_property");
        $property_elem.length = 1;

        blueslip.expect("error", "Element refers to unknown property");
        settings_org.sync_realm_settings("invalid_settings_property");
    }

    function test_common_policy(property_name) {
        const $property_elem = $(`#id_realm_${CSS.escape(property_name)}`);
        $property_elem.length = 1;
        $property_elem.attr("id", `id_realm_${CSS.escape(property_name)}`);

        /* Each policy is initialized to 'by_members' and then all the values are tested
        in the following order - by_admins_only, by_moderators_only, by_full_members,
        by_members. */

        realm[`realm_${property_name}`] = settings_config.common_policy_values.by_members.code;
        $property_elem.val(settings_config.common_policy_values.by_members.code);

        for (const policy_value of Object.values(settings_config.common_policy_values)) {
            realm[`realm_${property_name}`] = policy_value.code;
            settings_org.sync_realm_settings(property_name);
            assert.equal($property_elem.val(), policy_value.code);
        }
    }

    test_common_policy("create_private_stream_policy");
    test_common_policy("create_public_stream_policy");
    test_common_policy("invite_to_stream_policy");
    test_common_policy("invite_to_realm_policy");

    {
        /* Test message content edit limit minutes sync */
        const $property_elem = $("#id_realm_message_content_edit_limit_minutes");
        const $property_dropdown_elem = $("#id_realm_message_content_edit_limit_seconds");
        $property_elem.length = 1;
        $property_dropdown_elem.length = 1;
        $property_elem.attr("id", "id_realm_message_content_edit_limit_minutes");
        $property_dropdown_elem.attr("id", "id_realm_message_content_edit_limit_seconds");

        realm.realm_create_public_stream_policy = 1;
        realm.realm_message_content_edit_limit_seconds = 120;

        settings_org.sync_realm_settings("message_content_edit_limit_seconds");
        assert.equal($("#id_realm_message_content_edit_limit_minutes").val(), "2");
    }

    {
        /* Test message content edit limit dropdown value sync */
        realm.realm_message_content_edit_limit_seconds = 120;
        settings_org.sync_realm_settings("message_content_edit_limit_seconds");
        assert.equal($("#id_realm_message_content_edit_limit_seconds").val(), "120");

        realm.realm_message_content_edit_limit_seconds = 130;
        settings_org.sync_realm_settings("message_content_edit_limit_seconds");
        assert.equal($("#id_realm_message_content_edit_limit_seconds").val(), "custom_period");
    }

    {
        /* Test organization joining restrictions settings sync */
        const $property_elem = $("#id_realm_org_join_restrictions");
        $property_elem.length = 1;
        $property_elem.attr("id", "id_realm_org_join_restrictions");

        realm.realm_emails_restricted_to_domains = true;
        realm.realm_disallow_disposable_email_addresses = false;
        settings_org.sync_realm_settings("emails_restricted_to_domains");
        assert.equal($("#id_realm_org_join_restrictions").val(), "only_selected_domain");

        realm.realm_emails_restricted_to_domains = false;

        realm.realm_disallow_disposable_email_addresses = true;
        settings_org.sync_realm_settings("emails_restricted_to_domains");
        assert.equal($("#id_realm_org_join_restrictions").val(), "no_disposable_email");

        realm.realm_disallow_disposable_email_addresses = false;
        settings_org.sync_realm_settings("emails_restricted_to_domains");
        assert.equal($("#id_realm_org_join_restrictions").val(), "no_restriction");
    }
}

function test_parse_time_limit() {
    const $elem = $("#id_realm_message_content_edit_limit_minutes");
    const test_function = (value, expected_value = value) => {
        $elem.val(value);
        realm.realm_message_content_edit_limit_seconds =
            settings_components.parse_time_limit($elem);
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

function test_discard_changes_button(discard_changes) {
    const ev = {
        preventDefault: noop,
        stopPropagation: noop,
        target: ".save-discard-widget-button.discard-button",
    };

    realm.realm_allow_edit_history = true;
    realm.realm_edit_topic_policy = settings_config.common_message_policy_values.by_everyone.code;
    realm.realm_allow_message_editing = true;
    realm.realm_message_content_edit_limit_seconds = 3600;
    realm.realm_delete_own_message_policy =
        settings_config.common_message_policy_values.by_everyone.code;
    realm.realm_message_content_delete_limit_seconds = 120;

    const $allow_edit_history = $("#id_realm_allow_edit_history").prop("checked", false);
    const $edit_topic_policy = $("#id_realm_edit_topic_policy").val(
        settings_config.common_message_policy_values.by_admins_only.code,
    );
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

    $allow_edit_history.attr("id", "id_realm_allow_edit_history");
    $msg_edit_limit_setting.attr("id", "id_realm_message_content_edit_limit_seconds");
    $msg_delete_limit_setting.attr("id", "id_realm_message_content_delete_limit_seconds");
    $edit_topic_policy.attr("id", "id_realm_edit_topic_policy");
    $message_content_edit_limit_minutes.attr("id", "id_realm_message_content_edit_limit_minutes");
    $message_content_delete_limit_minutes.attr(
        "id",
        "id_realm_message_content_delete_limit_minutes",
    );

    const $discard_button_parent = $(".settings-subsection-parent");
    $discard_button_parent.find = () => [
        $allow_edit_history,
        $msg_edit_limit_setting,
        $msg_delete_limit_setting,
        $edit_topic_policy,
    ];

    const {$discard_button, props} = createSaveButtons("msg-editing");
    $discard_button.closest = (selector) => $(selector);

    discard_changes(ev);

    assert.equal($allow_edit_history.prop("checked"), true);
    assert.equal(
        $edit_topic_policy.val(),
        settings_config.common_message_policy_values.by_everyone.code,
    );
    assert.equal($msg_edit_limit_setting.val(), "3600");
    assert.equal($message_content_edit_limit_minutes.val(), "60");
    assert.equal($msg_delete_limit_setting.val(), "120");
    assert.equal($message_content_delete_limit_minutes.val(), "2");
    assert.ok(props.hidden);
}

test("set_up", ({override, override_rewire}) => {
    realm.realm_available_video_chat_providers = {
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
    };

    let upload_realm_logo_or_icon;
    realm_icon.build_realm_icon_widget = (f) => {
        upload_realm_logo_or_icon = f;
    };

    override_rewire(dropdown_widget, "DropdownWidget", () => ({
        setup: noop,
        render: noop,
    }));
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
    $("#id_realm_create_web_public_stream_policy").set_parent(
        $.create("<stub-create-web-public-stream-policy-parent>"),
    );

    override_rewire(settings_components, "get_input_element_value", (elem) => {
        if ($(elem).data() === "number") {
            return Number.parseInt($(elem).val(), 10);
        }
        return $(elem).val();
    });

    // TEST set_up() here, but this mostly just allows us to
    // get access to the click handlers.
    override(current_user, "is_owner", true);
    settings_org.set_up();

    test_submit_settings_form(
        override,
        $(".admin-realm-form").get_on_handler(
            "click",
            ".subsection-header .subsection-changes-save button",
        ),
    );
    test_upload_realm_icon(override, upload_realm_logo_or_icon);
    test_extract_property_name();
    test_change_save_button_state();
    test_sync_realm_settings();
    test_parse_time_limit();
    test_discard_changes_button(
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

test("misc", () => {
    current_user.is_admin = false;
    $("#user-avatar-upload-widget").length = 1;
    $("#user_details_section").length = 1;

    realm.realm_name_changes_disabled = false;
    realm.server_name_changes_disabled = false;
    settings_account.update_name_change_display();
    assert.ok(!$("#full_name").prop("disabled"));
    assert.ok(!$("#full_name_input_container").hasClass("disabled_setting_tooltip"));

    realm.realm_name_changes_disabled = true;
    realm.server_name_changes_disabled = false;
    settings_account.update_name_change_display();
    assert.ok($("#full_name").prop("disabled"));
    assert.ok($("#full_name_input_container").hasClass("disabled_setting_tooltip"));

    realm.realm_name_changes_disabled = true;
    realm.server_name_changes_disabled = true;
    settings_account.update_name_change_display();
    assert.ok($("#full_name").prop("disabled"));
    assert.ok($("#full_name_input_container").hasClass("disabled_setting_tooltip"));

    realm.realm_name_changes_disabled = false;
    realm.server_name_changes_disabled = true;
    settings_account.update_name_change_display();
    assert.ok($("#full_name").prop("disabled"));
    assert.ok($("#full_name_input_container").hasClass("disabled_setting_tooltip"));

    realm.realm_email_changes_disabled = false;
    settings_account.update_email_change_display();
    assert.ok(!$("#change_email_button").prop("disabled"));

    realm.realm_email_changes_disabled = true;
    settings_account.update_email_change_display();
    assert.ok($("#change_email_button").prop("disabled"));

    realm.realm_avatar_changes_disabled = false;
    realm.server_avatar_changes_disabled = false;
    settings_account.update_avatar_change_display();
    assert.ok(!$("#user-avatar-upload-widget .image_upload_button").hasClass("hide"));
    realm.realm_avatar_changes_disabled = true;
    realm.server_avatar_changes_disabled = false;
    settings_account.update_avatar_change_display();
    assert.ok($("#user-avatar-upload-widget .image_upload_button").hasClass("hide"));
    realm.realm_avatar_changes_disabled = false;
    realm.server_avatar_changes_disabled = true;
    settings_account.update_avatar_change_display();
    assert.ok($("#user-avatar-upload-widget .image_upload_button").hasClass("hide"));
    realm.realm_avatar_changes_disabled = true;
    realm.server_avatar_changes_disabled = true;
    settings_account.update_avatar_change_display();
    assert.ok($("#user-avatar-upload-widget .image_upload_button").hasClass("hide"));

    // If organization admin, these UI elements are never disabled.
    current_user.is_admin = true;
    settings_account.update_name_change_display();
    assert.ok(!$("#full_name").prop("disabled"));
    assert.ok(!$("#full_name_input_container").hasClass("disabled_setting_tooltip"));

    settings_account.update_email_change_display();
    assert.ok(!$("#change_email_button").prop("disabled"));

    settings_account.update_avatar_change_display();
    assert.ok(!$("#user-avatar-upload-widget .image_upload_button").hasClass("hide"));
});
