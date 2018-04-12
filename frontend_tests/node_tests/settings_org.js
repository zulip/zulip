set_global('$', global.make_zjquery());
set_global('i18n', global.stub_i18n);

zrequire('stream_data');
zrequire('settings_account');
zrequire('settings_org');
zrequire('settings_ui');
zrequire('settings_ui');

var noop = function () {};

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

(function test_unloaded() {
    // This test mostly gets us line coverage, and makes
    // sure things don't explode before set_up is called.

    settings_org.reset();
    settings_org.populate_realm_domains();
    settings_org.populate_auth_methods();
}());

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
function createSaveButtons() {
    var stub_save_button_header = $('.subsection-header');
    var save_btn_controls = $.create('.save-btn-controls');
    var stub_save_button = $('#org-submit-msg-editing');
    var stub_save_button_text = $.create('.icon-button-text');
    stub_save_button_header.prevAll = function () {
        return $.create('<stub failed alert status element>');
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
        '.subsection-changes-discard .button', $.create('#org-discard-msg-editing')
    );
    var props  = {};
    props.hidden = false;
    props.status = "";
    stub_save_button.attr = function (name, val) {
        if (name === "data-status") {
            if (val !== null) {
                props.status = val;
                return;
            }
            return props.status;
        } else if (name === "id") {
            return 'org-submit-msg-editing';
        }
    };
    save_btn_controls.animate = function (obj) {
        if (obj.opacity === 0) {
            props.hidden = true;
        } else {
            props.hidden = false;
        }
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
    var ev = {
        preventDefault: noop,
        stopPropagation: noop,
        currentTarget: '#org-submit-msg-editing',
    };

    $('#id_realm_default_language').val('fr');

    var patched;
    var success_callback;

    channel.patch = function (req) {
        patched = true;
        assert.equal(req.url, '/json/realm');
        success_callback = req.success;
    };

    createSaveButtons();

    submit_form(ev);
    assert(patched);

    var response_data = {
        allow_message_editing: true,
        message_content_edit_limit_seconds: 210,
    };
    success_callback(response_data);

    var updated_value_from_response = $('#id_realm_message_content_edit_limit_minutes').val();
    assert(updated_value_from_response, 3);

    $('#id_realm_message_content_edit_limit_minutes').val = function (time_limit) {
        updated_value_from_response = time_limit;
    };

    response_data = {
        allow_message_editing: true,
        message_content_edit_limit_seconds: 10,
    };
    success_callback(response_data);
    assert(updated_value_from_response, 0);
}

function test_change_save_button_state() {
    set_global('$', global.make_zjquery());
    var stubs = createSaveButtons();
    var $save_btn_controls = stubs.save_button_controls;
    var $save_btn_text = stubs.save_button_text;
    var $save_btn = stubs.save_button;
    var props = stubs.props;
    settings_org.change_save_button_state($save_btn_controls, "unsaved");
    assert.equal($save_btn_text.text(), 'translated: Save changes');
    assert.equal(props.hidden, false);
    assert.equal(props.status, "unsaved");
    settings_org.change_save_button_state($save_btn_controls, "saved");
    assert.equal($save_btn_text.text(), 'translated: Save changes');
    assert.equal(props.hidden, true);
    assert.equal(props.status, "");
    settings_org.change_save_button_state($save_btn_controls, "saving");
    assert.equal($save_btn_text.text(), 'translated: Saving');
    assert.equal(props.status, "saving");
    assert.equal($save_btn.hasClass('saving'), true);
    settings_org.change_save_button_state($save_btn_controls, "discarded");
    assert.equal(props.hidden, true);
    assert.equal($save_btn.hasClass('saving'), false);
    settings_org.change_save_button_state($save_btn_controls, "succeeded");
    assert.equal(props.hidden, true);
    assert.equal(props.status, "saved");
    assert.equal($save_btn_text.text(), 'translated: Saved');
    settings_org.change_save_button_state($save_btn_controls, "failed");
    assert.equal(props.hidden, false);
    assert.equal(props.status, "failed");
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

function test_change_message_editing(change_message_editing) {
    var parent_elem = $.create('editing-parent-stub');

    $('#id_realm_message_content_edit_limit_minutes_label').set_parent(parent_elem);

    change_message_editing.apply({checked: false});
    assert(parent_elem.hasClass('control-label-disabled'));
    assert.equal($('#id_realm_message_content_edit_limit_minutes').attr('disabled'), 'disabled');

    change_message_editing.apply({checked: true});
    assert(!parent_elem.hasClass('control-label-disabled'));
    assert.equal($('#id_realm_message_content_edit_limit_minutes').attr('disabled'), false);
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

(function test_set_up() {
    var callbacks = {};

    function set_callback(name) {
        return function (f) {
            callbacks[name] = f;
        };
    }

    var verify_realm_domains = simulate_realm_domains_table();
    simulate_auth_methods();

    $('#id_realm_create_stream_permission').change = set_callback('realm_create_stream_permission');
    $('#id_realm_invite_required').change = set_callback('change_invite_required');
    $('#id_realm_restricted_to_domain').change = set_callback('id_realm_restricted_to_domain');
    $('#id_realm_allow_message_editing').change = set_callback('change_message_editing');
    $('#submit-add-realm-domain').click = set_callback('add_realm_domain');
    $('.notifications-stream-disable').click = set_callback('disable_notifications_stream');
    $('.signup-notifications-stream-disable').click = set_callback('disable_signup_notifications_stream');

    var submit_settings_form;
    $('.organization').on = function (action, selector, f) {
        if (selector === '.subsection-header .subsection-changes-save .button') {
            assert.equal(action, 'click');
            submit_settings_form = f;
        }
        if (selector === 'button.save-language-org-settings') {
            assert.equal(action, 'click');
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
    var parent_elem = $.create('waiting-period-parent-stub');
    $('#id_realm_waiting_period_threshold').set_parent(parent_elem);
    // TEST set_up() here, but this mostly just allows us to
    // get access to the click handlers.
    settings_org.set_up();

    verify_realm_domains();

    test_realms_domain_modal(callbacks.add_realm_domain);
    test_submit_settings_form(submit_settings_form);
    test_upload_realm_icon(upload_realm_icon);
    test_change_invite_required(callbacks.change_invite_required);
    test_change_message_editing(callbacks.change_message_editing);
    test_disable_notifications_stream(callbacks.disable_notifications_stream);
    test_disable_signup_notifications_stream(callbacks.disable_signup_notifications_stream);
    test_change_allow_subdomains(change_allow_subdomains);
    test_extract_property_name();
    settings_org.render_notifications_stream_ui = stub_render_notifications_stream_ui;
    test_change_save_button_state();
}());

(function test_misc() {
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

}());
