set_global('$', global.make_zjquery());
set_global('i18n', global.stub_i18n);

zrequire('stream_data');
zrequire('settings_account');
zrequire('settings_org');
zrequire('settings_ui');
zrequire('settings_ui');

const noop = () => {};

set_global('loading', {
    make_indicator: noop,
    destroy_indicator: noop,
});

set_global('page_params', {
    is_admin: false,
    realm_domains: [
        { domain: 'example.com', allow_subdomains: true },
        { domain: 'example.org', allow_subdomains: false },
    ],
});

set_global('realm_icon', {
});

set_global('channel', {
});

set_global('templates', {
});

set_global('overlays', {
});

run_test('unloaded', () => {
    // This test mostly gets us line coverage, and makes
    // sure things don't explode before set_up is called.

    settings_org.reset();
    settings_org.populate_realm_domains();
    settings_org.populate_auth_methods();
});

(function stub_rendering() {
    templates.render = function (name, data) {
        if (name === 'admin-realm-domains-list') {
            assert(data.realm_domain.domain);
            return 'stub-domains-list';
        }
    };
}());

set_global('ui_report', {
    success: function (msg, elem) {
        elem.val(msg);
    },

    error: function (msg, xhr, elem) {
        elem.val(msg);
    },
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
    var stub_save_button_header = $('.subsection-header');
    var save_btn_controls = $('.save-btn-controls');
    var stub_save_button = $(`#org-submit-${subsection}`);
    var stub_save_button_text = $('.icon-button-text');
    stub_save_button_header.prevAll = function () {
        return $('<stub failed alert status element>');
    };
    stub_save_button.closest = function () {
        return stub_save_button_header;
    };
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
    var props  = {};
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
    global.patch_builtin('setTimeout', (func) => func());
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
    patched = false;
    $("#id_realm_create_stream_permission").val("by_anyone");
    $("#id_realm_add_emoji_by_admins_only").val("by_anyone");
    $("#id_realm_message_retention_days").val("15");
    $("#id_realm_bot_creation_policy").val("1");

    submit_form(ev);
    assert(patched);

    let expected_value = {
        bot_creation_policy: '1',
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
    var form_data = {
        append: function (field, val) {
            form_data[field] = val;
        },
    };

    set_global('csrf_token', 'token-stub');
    set_global('jQuery', {
        each: function (lst, f) {
            _.each(lst, function (v, k) {
                f(k, v);
            });
        },
    });

    set_global('FormData', function () {
        return form_data;
    });

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

function test_change_invite_required(change_invite_required) {
    var parent_elem = $.create('invite-parent-stub');

    $('#id_realm_invite_by_admins_only_label').set_parent(parent_elem);

    change_invite_required.apply({checked: false});
    assert(parent_elem.hasClass('control-label-disabled'));
    assert.equal($('#id_realm_invite_by_admins_only').attr('disabled'), 'disabled');

    change_invite_required.apply({checked: true});
    assert(!parent_elem.hasClass('control-label-disabled'));
    assert.equal($('#id_realm_invite_by_admins_only').attr('disabled'), false);
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

run_test('set_up', () => {
    var callbacks = {};

    var set_callback = (name) => {
        return (f) => {
            callbacks[name] = f;
        };
    };

    var verify_realm_domains = simulate_realm_domains_table();
    simulate_auth_methods();

    $('#id_realm_create_stream_permission').change = set_callback('realm_create_stream_permission');
    $('#id_realm_video_chat_provider').change = set_callback('realm_video_chat_provider');
    $('#id_realm_invite_required').change = set_callback('change_invite_required');
    $("#id_realm_org_join_restrictions").change = set_callback('change_org_join_restrictions');
    $('#submit-add-realm-domain').click = set_callback('add_realm_domain');
    $('#admin_auth_methods_table').change = set_callback('admin_auth_methods_table');
    $('.notifications-stream-disable').click = set_callback('disable_notifications_stream');
    $('.signup-notifications-stream-disable').click = set_callback('disable_signup_notifications_stream');

    var submit_settings_form;
    $('.organization').on = function (action, selector, f) {
        if (selector === '.subsection-header .subsection-changes-save .button') {
            assert.equal(action, 'click');
            submit_settings_form = f;
        }
    };

    var change_allow_subdomains;
    $('#realm_domains_table').on = function (action, selector, f) {
        if (action === 'change') {
            assert.equal(selector, '.allow-subdomains');
            change_allow_subdomains = f;
        }
    };

    var upload_realm_icon;
    realm_icon.build_realm_icon_widget = function (f) {
        upload_realm_icon = f;
    };

    var stub_render_notifications_stream_ui = settings_org.render_notifications_stream_ui;
    settings_org.render_notifications_stream_ui = noop;
    $("#id_realm_message_content_edit_limit_minutes").set_parent($.create('<stub edit limit parent>'));
    $("#id_realm_message_content_delete_limit_minutes").set_parent($.create('<stub delete limti parent>'));
    $("#id_realm_msg_edit_limit_setting").change = noop;
    $('#id_realm_msg_delete_limit_setting').change = noop;
    var parent_elem = $.create('waiting-period-parent-stub');
    $('#id_realm_waiting_period_threshold').set_parent(parent_elem);
    $("#allowed_domains_label").set_parent($.create('<stub-allowed-domain-label-parent>'));
    // TEST set_up() here, but this mostly just allows us to
    // get access to the click handlers.
    settings_org.set_up();

    verify_realm_domains();

    test_realms_domain_modal(callbacks.add_realm_domain);
    test_submit_settings_form(submit_settings_form);
    test_upload_realm_icon(upload_realm_icon);
    test_change_invite_required(callbacks.change_invite_required);
    test_disable_notifications_stream(callbacks.disable_notifications_stream);
    test_disable_signup_notifications_stream(callbacks.disable_signup_notifications_stream);
    test_change_allow_subdomains(change_allow_subdomains);
    test_extract_property_name();
    test_change_save_button_state();
    test_sync_realm_settings();
    test_parse_time_limit();

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
