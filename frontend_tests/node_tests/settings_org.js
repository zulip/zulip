set_global('$', global.make_zjquery());
set_global('i18n', global.stub_i18n);
set_global('blueslip', global.make_zblueslip());

const noop = () => {};

var form_data;

const _jQuery = {
    each: function (lst, f) {
        _.each(lst, function (v, k) {
            f(k, v);
        });
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
        { domain: 'example.com', allow_subdomains: true },
        { domain: 'example.org', allow_subdomains: false },
    ],
};

const _realm_icon = {};
const _channel = {};

const _templates = {
    render: function (name, data) {
        if (name === 'admin-realm-domains-list') {
            assert(data.realm_domain.domain);
            return 'stub-domains-list';
        }
    },
};

const _overlays = {};

const _ui_report = {
    success: function (msg, elem) {
        elem.val(msg);
    },

    error: function (msg, xhr, elem) {
        elem.val(msg);
    },
};

const _realm_logo = {
    build_realm_logo_widget: noop,
    build_realm_night_logo_widget: noop,
};

set_global('channel', _channel);
set_global('csrf_token', 'token-stub');
set_global('FormData', _FormData);
set_global('jQuery', _jQuery);
set_global('loading', _loading);
set_global('overlays', _overlays);
set_global('page_params', _page_params);
set_global('realm_icon', _realm_icon);
set_global('realm_logo', _realm_logo);
set_global('templates', _templates);
set_global('ui_report', _ui_report);

zrequire('stream_data');
zrequire('settings_account');
zrequire('settings_org');
zrequire('settings_ui');

run_test('unloaded', () => {
    // This test mostly gets us line coverage, and makes
    // sure things don't explode before set_up is called.

    settings_org.reset();
    settings_org.populate_realm_domains();
    settings_org.populate_auth_methods();
});

function simulate_auth_methods() {
    $('#admin_auth_methods_table').set_find_results(
        'tr.method_row',
        $.create('admin-tr-stub')
    );

    var controls = $.create('auth-methods-controls-stub');

    $(".organization-box [data-name='auth-methods']").set_find_results(
        'input, button, select, checked',
        controls
    );

    controls.attr = function (name, val) {
        assert.equal(name, 'disabled');
        assert.equal(val, true);
    };

    var non_editables = $.create('auth-methods-not-edit-stub');
    $('.organization-box').set_find_results(
        '.settings-section:not(.can-edit)',
        non_editables
    );

    non_editables.not = function () { return this; };
    non_editables.prepend = noop;
}

function simulate_realm_domains_table() {
    $('#realm_domains_table tbody').set_find_results(
        'tr',
        $.create('realm-tr-stub')
    );

    var appended;
    $("#realm_domains_table tbody").append = function (html) {
        appended = true;
        assert.equal(html, 'stub-domains-list');
    };

    return function verify() {
        assert(appended);
    };
}

function test_realms_domain_modal(add_realm_domain) {
    var info = $('.realm_domains_info');

    $('#add-realm-domain-widget').set_find_results(
        '.new-realm-domain',
        $.create('new-realm-domain-stub')
    );

    $('#add-realm-domain-widget').set_find_results(
        '.new-realm-domain-allow-subdomains',
        $.create('new-realm-domain-allow-subdomains-stub')
    );

    var posted;
    var success_callback;
    var error_callback;
    channel.post = function (req) {
        posted = true;
        assert.equal(req.url, '/json/realm/domains');
        success_callback = req.success;
        error_callback = req.error;
    };

    add_realm_domain();

    assert(posted);

    success_callback();
    assert.equal(info.val(), 'translated: Added successfully!');

    error_callback({});
    assert.equal(info.val(), 'translated: Failed');
}

function createSaveButtons(subsection) {
    const stub_save_button_header = $('.subsection-header');
    const save_btn_controls = $('.save-btn-controls');
    const stub_save_button = $(`#org-submit-${subsection}`);
    const stub_save_button_text = $('.icon-button-text');
    stub_save_button_header.set_find_results(
        '.subsection-failed-status p', $('<failed status element>')
    );
    stub_save_button.closest = () => stub_save_button_header;
    save_btn_controls.set_find_results(
        '.save-button', stub_save_button
    );
    stub_save_button.set_find_results(
        '.icon-button-text', stub_save_button_text
    );
    stub_save_button_header.set_find_results(
        '.save-button-controls', save_btn_controls
    );
    stub_save_button_header.set_find_results(
        '.subsection-changes-discard .button', $(`#org-discard-${subsection}`)
    );
    const props  = {};
    props.hidden = false;
    save_btn_controls.fadeIn = () => {
        props.hidden = false;
    };
    save_btn_controls.fadeOut = () => {
        props.hidden = true;
    };
    return {
        props: props,
        save_button: stub_save_button,
        save_button_header: stub_save_button_header,
        save_button_controls: save_btn_controls,
        save_button_text: stub_save_button_text,
    };
}

function test_submit_settings_form(submit_form) {
    global.patch_builtin('setTimeout', func => func());
    const ev = {
        preventDefault: noop,
        stopPropagation: noop,
    };

    let patched;
    let data;
    let success_callback;
    channel.patch = (req) => {
        patched = true;
        assert.equal(req.url, '/json/realm');
        data = req.data;
        success_callback = req.success;
    };

    ev.currentTarget = '#org-submit-other-permissions';
    let stubs = createSaveButtons('other-permissions');
    let save_button = stubs.save_button;
    save_button.attr('id', 'org-submit-other-permissions');
    $("#id_realm_create_stream_permission").val("by_anyone");
    $("#id_realm_add_emoji_by_admins_only").val("by_anyone");
    $("#id_realm_message_retention_days").val("15");
    $("#id_realm_bot_creation_policy").val("1");
    $("#id_realm_email_address_visibility").val("1");

    patched = false;
    submit_form(ev);
    assert(patched);

    let expected_value = {
        bot_creation_policy: '1',
        email_address_visibility: '1',
        message_retention_days: '15',
        add_emoji_by_admins_only: false,
        create_stream_by_admins_only: false,
        waiting_period_threshold: 0,
    };
    assert.deepEqual(data, expected_value);


    ev.currentTarget = '#org-submit-user-defaults';
    stubs = createSaveButtons('user-defaults');
    save_button = stubs.save_button;
    save_button.attr('id', 'org-submit-user-defaults');

    $("#id_realm_default_language").val("en");
    $("#id_realm_default_twenty_four_hour_time").prop("checked", true);

    submit_form(ev);
    assert(patched);

    expected_value = {
        default_language: '"en"',
        default_twenty_four_hour_time: 'true',
    };
    assert.deepEqual(data, expected_value);


    // Testing only once for since callback is same for all cases
    success_callback();
    assert.equal(stubs.props.hidden, true);
    assert.equal(save_button.attr("data-status"), "saved");
    assert.equal(stubs.save_button_text.text(), 'translated: Saved');
}

function test_change_save_button_state() {
    var stubs = createSaveButtons('msg-editing');
    var $save_btn_controls = stubs.save_button_controls;
    var $save_btn_text = stubs.save_button_text;
    var $save_btn = stubs.save_button;
    $save_btn.attr("id", "org-submit-msg-editing");
    var props = stubs.props;
    settings_org.change_save_button_state($save_btn_controls, "unsaved");
    assert.equal($save_btn_text.text(), 'translated: Save changes');
    assert.equal(props.hidden, false);
    assert.equal($save_btn.attr("data-status"), "unsaved");
    settings_org.change_save_button_state($save_btn_controls, "saved");
    assert.equal($save_btn_text.text(), 'translated: Save changes');
    assert.equal(props.hidden, true);
    assert.equal($save_btn.attr("data-status"), "");
    settings_org.change_save_button_state($save_btn_controls, "saving");
    assert.equal($save_btn_text.text(), 'translated: Saving');
    assert.equal($save_btn.attr("data-status"), "saving");
    assert.equal($save_btn.hasClass('saving'), true);
    settings_org.change_save_button_state($save_btn_controls, "discarded");
    assert.equal(props.hidden, true);
    assert.equal($save_btn.hasClass('saving'), false);
    settings_org.change_save_button_state($save_btn_controls, "succeeded");
    assert.equal(props.hidden, true);
    assert.equal($save_btn.attr("data-status"), "saved");
    assert.equal($save_btn_text.text(), 'translated: Saved');
    settings_org.change_save_button_state($save_btn_controls, "failed");
    assert.equal(props.hidden, false);
    assert.equal($save_btn.attr("data-status"), "failed");
    assert.equal($save_btn_text.text(), 'translated: Save changes');
}

function test_upload_realm_icon(upload_realm_icon) {
    form_data = {
        append: function (field, val) {
            form_data[field] = val;
        },
    };

    var file_input = [
        {files: ['image1.png', 'image2.png']},
    ];

    var posted;
    channel.post = function (req) {
        posted = true;
        assert.equal(req.url, '/json/realm/icon');
        assert.equal(req.data.csrfmiddlewaretoken, 'token-stub');
        assert.equal(req.data['file-0'], 'image1.png');
        assert.equal(req.data['file-1'], 'image2.png');
    };

    upload_realm_icon(file_input);
    assert(posted);
}

function test_disable_notifications_stream(disable_notifications_stream) {
    var success_callback;
    var error_callback;
    channel.patch = function (req) {
        assert.equal(req.url, '/json/realm');
        assert.equal(req.data.notifications_stream_id, '-1');
        success_callback = req.success;
        error_callback = req.error;
    };

    disable_notifications_stream();

    var response_data = {
        notifications_stream_id: -1,
    };

    success_callback(response_data);
    assert.equal($('#admin-realm-notifications-stream-status').val(),
                 'translated: Notifications stream disabled!');

    error_callback({});
    assert.equal($('#admin-realm-notifications-stream-status').val(),
                 'translated: Failed to change notifications stream!');
}

function test_disable_signup_notifications_stream(disable_signup_notifications_stream) {
    var success_callback;
    var error_callback;
    channel.patch = function (req) {
        assert.equal(req.url, '/json/realm');
        assert.equal(req.data.signup_notifications_stream_id, '-1');
        success_callback = req.success;
        error_callback = req.error;
    };

    disable_signup_notifications_stream();

    var response_data = {
        signup_notifications_stream_id: -1,
    };

    success_callback(response_data);
    assert.equal($('#admin-realm-signup-notifications-stream-status').val(),
                 'translated: Signup notifications stream disabled!');

    error_callback({});
    assert.equal($('#admin-realm-signup-notifications-stream-status').val(),
                 'translated: Failed to change signup notifications stream!');
}

function test_change_allow_subdomains(change_allow_subdomains) {
    var ev = {
        stopPropagation: noop,
    };

    var info = $('.realm_domains_info');
    info.fadeOut = noop;
    var domain = 'example.com';
    var allow = true;

    var success_callback;
    var error_callback;
    channel.patch = function (req) {
        assert.equal(req.url, '/json/realm/domains/example.com');
        assert.equal(req.data.allow_subdomains, JSON.stringify(allow));
        success_callback = req.success;
        error_callback = req.error;
    };

    var domain_obj = $.create('domain object');
    domain_obj.text(domain);


    var elem_obj = $.create('<elem html>');
    var parents_obj = $.create('parents object');

    elem_obj.set_parents_result('tr', parents_obj);
    parents_obj.set_find_results('.domain', domain_obj);
    elem_obj.prop('checked', allow);

    change_allow_subdomains.apply(elem_obj, [ev]);

    success_callback();
    assert.equal(info.val(),
                 'translated: Update successful: Subdomains allowed for example.com');

    error_callback({});
    assert.equal(info.val(), 'translated: Failed');

    allow = false;
    elem_obj.prop('checked', allow);
    change_allow_subdomains.apply(elem_obj, [ev]);
    success_callback();
    assert.equal(info.val(),
                 'translated: Update successful: Subdomains no longer allowed for example.com');
}

function test_extract_property_name() {
    $('#id_realm_allow_message_editing').attr('id', 'id_realm_allow_message_editing');
    assert.equal(
        settings_org.extract_property_name($('#id_realm_allow_message_editing')),
        'realm_allow_message_editing'
    );

    $('#id_realm_message_content_edit_limit_minutes_label').attr(
        'id', 'id_realm_message_content_edit_limit_minutes_label');
    assert.equal(
        settings_org.extract_property_name($('#id_realm_message_content_edit_limit_minutes_label')),
        'realm_message_content_edit_limit_minutes_label'
    );

    $('#id-realm-allow-message-deleting').attr(
        'id', 'id-realm-allow-message-deleting');
    assert.equal(
        settings_org.extract_property_name($('#id-realm-allow-message-deleting')),
        'realm_allow_message_deleting'
    );
}

function test_sync_realm_settings() {
    overlays.settings_open = () => true;

    {
        /* Test invalid settings property sync */
        const property_elem = $('#id_realm_invalid_settings_property');
        property_elem.attr('id', 'id_realm_invalid_settings_property');
        property_elem.length = 1;

        blueslip.error = error_string => {
            assert.equal(error_string, 'Element refers to unknown property realm_invalid_settings_property');
        };
        settings_org.sync_realm_settings('invalid_settings_property');
    }

    {
        /* Test create new stream permission settings sync */
        const property_elem = $('#id_realm_create_stream_permission');
        property_elem.length = 1;
        property_elem.attr('id', 'id_realm_create_stream_permission');

        const waiting_period_input_parent = $.create('stub-waiting-period-input-parent');
        $("#id_realm_waiting_period_threshold").set_parent(waiting_period_input_parent);

        page_params.realm_create_stream_by_admins_only = false;
        page_params.realm_waiting_period_threshold = 3;

        settings_org.sync_realm_settings('create_stream_by_admins_only');
        assert.equal($("#id_realm_create_stream_permission").val(), "by_admin_user_with_three_days_old");
        assert.equal(waiting_period_input_parent.visible(), false);
    }

    {
        /* Test message content edit limit minutes sync */
        const property_elem = $('#id_realm_message_content_edit_limit_minutes');
        property_elem.length = 1;
        property_elem.attr('id', 'id_realm_message_content_edit_limit_minutes');

        page_params.realm_create_stream_by_admins_only = false;
        page_params.realm_message_content_edit_limit_seconds = 120;

        settings_org.sync_realm_settings('message_content_edit_limit_seconds');
        assert.equal($("#id_realm_message_content_edit_limit_minutes").val(), 2);
    }

    {
        /* Test message content edit limit dropdown value sync */
        const property_elem = $('#id_realm_msg_edit_limit_setting');
        property_elem.length = 1;
        property_elem.attr('id', 'id_realm_msg_edit_limit_setting');

        page_params.realm_allow_message_editing = false;
        page_params.realm_message_content_edit_limit_seconds = 120;
        settings_org.sync_realm_settings('allow_message_editing');
        assert.equal($("#id_realm_msg_edit_limit_setting").val(), "never");

        page_params.realm_allow_message_editing = true;

        page_params.realm_message_content_edit_limit_seconds = 120;
        settings_org.sync_realm_settings('allow_message_editing');
        assert.equal($("#id_realm_msg_edit_limit_setting").val(), "upto_two_min");

        page_params.realm_message_content_edit_limit_seconds = 130;
        settings_org.sync_realm_settings('allow_message_editing');
        assert.equal($("#id_realm_msg_edit_limit_setting").val(), "custom_limit");
    }

    {
        /* Test message content edit limit minutes sync */
        const property_elem = $('#id_realm_message_content_edit_limit_minutes');
        property_elem.length = 1;
        property_elem.attr('id', 'id_realm_message_content_edit_limit_minutes');

        page_params.realm_create_stream_by_admins_only = false;
        page_params.realm_message_content_edit_limit_seconds = 120;

        settings_org.sync_realm_settings('message_content_edit_limit_seconds');
        assert.equal($("#id_realm_message_content_edit_limit_minutes").val(), 2);
    }

    {
        /* Test organization joining restrictions settings sync */
        const property_elem = $('#id_realm_org_join_restrictions');
        property_elem.length = 1;
        property_elem.attr('id', 'id_realm_org_join_restrictions');

        page_params.realm_emails_restricted_to_domains = true;
        page_params.realm_disallow_disposable_email_addresses = false;
        settings_org.sync_realm_settings('emails_restricted_to_domains');
        assert.equal($("#id_realm_org_join_restrictions").val(), "only_selected_domain");

        page_params.realm_emails_restricted_to_domains = false;

        page_params.realm_disallow_disposable_email_addresses = true;
        settings_org.sync_realm_settings('emails_restricted_to_domains');
        assert.equal($("#id_realm_org_join_restrictions").val(), "no_disposable_email");

        page_params.realm_disallow_disposable_email_addresses = false;
        settings_org.sync_realm_settings('emails_restricted_to_domains');
        assert.equal($("#id_realm_org_join_restrictions").val(), "no_restriction");
    }
}

function test_parse_time_limit() {
    const elem = $('#id_realm_message_content_edit_limit_minutes');
    const test_function = (value, expected_value = value) => {
        elem.val(value);
        global.page_params.realm_message_content_edit_limit_seconds =
            settings_org.parse_time_limit(elem);
        assert.equal(expected_value,
                     settings_org.get_realm_time_limits_in_minutes(
                         'realm_message_content_edit_limit_seconds'));
    };

    test_function('0.01', '0');
    test_function('0.1');
    test_function('0.122', '0.1');
    test_function('0.155', '0.2');
    test_function('0.150', '0.1');
    test_function('0.5');
    test_function('1');
    test_function('1.1');
    test_function('10.5');
    test_function('50.3');
    test_function('100');
    test_function('100.1');
    test_function('127.79', '127.8');
    test_function('201.1');
    test_function('501.15', '501.1');
    test_function('501.34', '501.3');
}

function test_discard_changes_button(discard_changes) {
    const ev = {
        preventDefault: noop,
        stopPropagation: noop,
        target: '#org-discard-msg-editing',
    };

    page_params.realm_allow_edit_history = true;
    page_params.realm_allow_community_topic_editing = true;
    page_params.realm_allow_message_editing = true;
    page_params.realm_message_content_edit_limit_seconds = 3600;
    page_params.realm_allow_message_deleting = true;
    page_params.realm_message_content_delete_limit_seconds = 120;

    const allow_edit_history = $('#id_realm_allow_edit_history').prop('checked', false);
    const allow_community_topic_editing = $('#id_realm_allow_community_topic_editing').prop('checked', true);
    const msg_edit_limit_setting = $('#id_realm_msg_edit_limit_setting').val("custom_limit");
    const message_content_edit_limit_minutes = $('#id_realm_message_content_edit_limit_minutes').val(130);
    const msg_delete_limit_setting = $('#id_realm_msg_delete_limit_setting').val("custom_limit");
    const message_content_delete_limit_minutes = $('#id_realm_message_content_delete_limit_minutes').val(130);

    allow_edit_history.attr('id', 'id_realm_allow_edit_history');
    msg_edit_limit_setting.attr('id', 'id_realm_msg_edit_limit_setting');
    msg_delete_limit_setting.attr('id', 'id_realm_msg_delete_limit_setting');
    allow_community_topic_editing.attr('id', 'id_realm_allow_community_topic_editing');
    message_content_edit_limit_minutes.attr('id', 'id_realm_message_content_edit_limit_minutes');
    message_content_delete_limit_minutes.attr('id', 'id_realm_message_content_delete_limit_minutes');


    const discard_button_parent = $('.org-subsection-parent');
    discard_button_parent.find = () => [
        allow_edit_history,
        msg_edit_limit_setting,
        msg_delete_limit_setting,
        allow_community_topic_editing,
        message_content_edit_limit_minutes,
        message_content_delete_limit_minutes,
    ];

    $('#org-discard-msg-editing').closest = () => discard_button_parent;

    const stubbed_function = settings_org.change_save_button_state;
    settings_org.change_save_button_state = (save_btn_controls, state) => {
        assert.equal(state, "discarded");
    };

    discard_changes(ev);

    assert.equal(allow_edit_history.prop('checked'), true);
    assert.equal(allow_community_topic_editing.prop('checked'), true);
    assert.equal(msg_edit_limit_setting.val(), "upto_one_hour");
    assert.equal(message_content_edit_limit_minutes.val(), 60);
    assert.equal(msg_delete_limit_setting.val(), "upto_two_min");
    assert.equal(message_content_delete_limit_minutes.val(), 2);

    settings_org.change_save_button_state = stubbed_function;
}

run_test('set_up', () => {
    const callbacks = {};

    const set_callback = (name) => {
        return (f) => {
            callbacks[name] = f;
        };
    };

    const verify_realm_domains = simulate_realm_domains_table();
    simulate_auth_methods();

    $('#id_realm_create_stream_permission').change = set_callback('realm_create_stream_permission');
    $('#id_realm_video_chat_provider').change = set_callback('realm_video_chat_provider');
    $("#id_realm_org_join_restrictions").change = set_callback('change_org_join_restrictions');
    $('#submit-add-realm-domain').click = set_callback('add_realm_domain');
    $('#admin_auth_methods_table').change = set_callback('admin_auth_methods_table');
    $('.notifications-stream-disable').click = set_callback('disable_notifications_stream');
    $('.signup-notifications-stream-disable').click = set_callback('disable_signup_notifications_stream');

    let submit_settings_form;
    let discard_changes;
    $('.organization').on = function (action, selector, f) {
        if (selector === '.subsection-header .subsection-changes-save .button') {
            assert.equal(action, 'click');
            submit_settings_form = f;
        } else if (selector === '.subsection-header .subsection-changes-discard .button') {
            assert.equal(action, 'click');
            discard_changes = f;
        }
    };

    let change_allow_subdomains;
    $('#realm_domains_table').on = function (action, selector, f) {
        if (action === 'change') {
            assert.equal(selector, '.allow-subdomains');
            change_allow_subdomains = f;
        }
    };

    let upload_realm_icon;
    realm_icon.build_realm_icon_widget = function (f) {
        upload_realm_icon = f;
    };

    const stub_render_notifications_stream_ui = settings_org.render_notifications_stream_ui;
    settings_org.render_notifications_stream_ui = noop;
    $("#id_realm_message_content_edit_limit_minutes").set_parent($.create('<stub edit limit parent>'));
    $("#id_realm_message_content_delete_limit_minutes").set_parent($.create('<stub delete limti parent>'));
    $("#message_content_in_email_notifications_label").set_parent($.create('<stub in-content setting checkbox>'));
    $("#id_realm_msg_edit_limit_setting").change = noop;
    $('#id_realm_msg_delete_limit_setting').change = noop;
    const parent_elem = $.create('waiting-period-parent-stub');
    $('#id_realm_waiting_period_threshold').set_parent(parent_elem);
    $("#allowed_domains_label").set_parent($.create('<stub-allowed-domain-label-parent>'));

    const allow_topic_edit_label_parent = $.create('allow-topic-edit-label-parent');
    $('#id_realm_allow_community_topic_editing_label').set_parent(allow_topic_edit_label_parent);

    // TEST set_up() here, but this mostly just allows us to
    // get access to the click handlers.
    settings_org.maybe_disable_widgets = noop;
    settings_org.set_up();

    verify_realm_domains();

    test_realms_domain_modal(callbacks.add_realm_domain);
    test_submit_settings_form(submit_settings_form);
    test_upload_realm_icon(upload_realm_icon);
    test_disable_notifications_stream(callbacks.disable_notifications_stream);
    test_disable_signup_notifications_stream(callbacks.disable_signup_notifications_stream);
    test_change_allow_subdomains(change_allow_subdomains);
    test_extract_property_name();
    test_change_save_button_state();
    test_sync_realm_settings();
    test_parse_time_limit();
    test_discard_changes_button(discard_changes);

    settings_org.render_notifications_stream_ui = stub_render_notifications_stream_ui;
});

run_test('misc', () => {
    page_params.is_admin = false;

    var stub_notification_disable_parent = $.create('<stub notification_disable parent');
    stub_notification_disable_parent.set_find_results('.notification-disable',
                                                      $.create('<disable link>'));

    page_params.realm_name_changes_disabled = false;
    settings_account.update_name_change_display();
    assert.equal($('#full_name').attr('disabled'), false);

    page_params.realm_name_changes_disabled = true;
    settings_account.update_name_change_display();
    assert.equal($('#full_name').attr('disabled'), 'disabled');

    page_params.realm_email_changes_disabled = false;
    settings_account.update_email_change_display();
    assert.equal($("#change_email .button").attr('disabled'), false);

    page_params.realm_email_changes_disabled = true;
    settings_account.update_email_change_display();
    assert.equal($("#change_email .button").attr('disabled'), 'disabled');

    // If organization admin, these UI elements are never disabled.
    page_params.is_admin = true;
    settings_account.update_name_change_display();
    assert.equal($('#full_name').attr('disabled'), false);

    settings_account.update_email_change_display();
    assert.equal($("#change_email .button").attr('disabled'), false);

    var elem = $('#realm_notifications_stream_name');
    elem.closest = function () {
        return stub_notification_disable_parent;
    };
    stream_data.get_sub_by_id = function (stream_id) {
        assert.equal(stream_id, 42);
        return { name: 'some_stream' };
    };
    settings_org.render_notifications_stream_ui(42, elem);
    assert.equal(elem.text(), '#some_stream');
    assert(!elem.hasClass('text-warning'));

    stream_data.get_sub_by_id = noop;
    settings_org.render_notifications_stream_ui(undefined, elem);
    assert.equal(elem.text(), 'translated: Disabled');
    assert(elem.hasClass('text-warning'));

    elem = $('#realm_signup_notifications_stream_name');
    elem.closest = function () {
        return stub_notification_disable_parent;
    };
    stream_data.get_sub_by_id = function (stream_id) {
        assert.equal(stream_id, 75);
        return { name: 'some_stream' };
    };
    settings_org.render_notifications_stream_ui(75, elem);
    assert.equal(elem.text(), '#some_stream');
    assert(!elem.hasClass('text-warning'));

    stream_data.get_sub_by_id = noop;
    settings_org.render_notifications_stream_ui(undefined, elem);
    assert.equal(elem.text(), 'translated: Disabled');
    assert(elem.hasClass('text-warning'));

});
