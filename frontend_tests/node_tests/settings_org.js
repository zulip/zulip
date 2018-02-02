set_global('$', global.make_zjquery());
set_global('i18n', global.stub_i18n);

zrequire('stream_data');
zrequire('settings_org');

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
    settings_org.reset_realm_default_language();
    settings_org.toggle_allow_message_editing_pencil();
    settings_org.toggle_name_change_display();
    settings_org.toggle_email_change_display();
    settings_org.update_realm_description();
    settings_org.update_message_retention_days();
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

function test_submit_profile_form(submit_form) {
    var ev = {
        preventDefault: noop,
        stopPropagation: noop,
    };

    $('#id_realm_name').val('Acme');
    $('#id_realm_description').val('makes widgets');

    var patched;
    var success_callback;

    channel.patch = function (req) {
        patched = true;
        assert.equal(req.url, '/json/realm');

        var data = req.data;

        assert.equal(data.name, '"Acme"');
        assert.equal(data.description, '"makes widgets"');

        success_callback = req.success;
    };

    submit_form(ev);
    assert(patched);

    var response_data = {
        name: 'Acme',
    };
    success_callback(response_data);

    assert.equal($('#admin-realm-name-status').val(),
                 'translated: Name changed!');
}

function test_submit_settings_form(submit_form) {
    var ev = {
        preventDefault: noop,
        stopPropagation: noop,
    };

    $('#id_realm_default_language').val('fr');

    var patched;
    var success_callback;

    channel.patch = function (req) {
        patched = true;
        assert.equal(req.url, '/json/realm');

        var data = req.data;

        assert.equal(data.default_language, '"fr"');

        success_callback = req.success;
    };

    submit_form(ev);
    assert(patched);

    var response_data = {
        allow_message_editing: true,
        message_content_edit_limit_seconds: 210,
    };

    success_callback(response_data);

    var editing_status = $('#admin-realm-message-editing-status').val();
    assert(editing_status.indexOf('content of messages which are less than') > 0);

    response_data = {
        allow_message_editing: true,
        message_content_edit_limit_seconds: 0,
    };
    success_callback(response_data);

    assert.equal($('#admin-realm-message-editing-status').val(),
                 'translated: Users can now edit the content and topics ' +
                 'of all their past messages!');

    response_data = {
        allow_message_editing: false,
    };
    success_callback(response_data);

    assert.equal($('#admin-realm-message-editing-status').val(),
          'translated: Users can no longer edit their past messages!');
}

function test_submit_permissions_form(submit_form) {
    var ev = {
        preventDefault: noop,
        stopPropagation: noop,
    };

    $('#id_realm_add_emoji_by_admins_only').prop('checked', true);
    $("#id_realm_create_stream_permission").val("by_admin_user_with_custom_time").change();
    $("#id_realm_waiting_period_threshold").val("55");

    var patched;
    var success_callback;
    var error_callback;
    channel.patch = function (req) {
        patched = true;
        assert.equal(req.url, '/json/realm');

        var data = req.data;
        assert.equal(data.add_emoji_by_admins_only, 'true');
        assert.equal(data.create_stream_by_admins_only, false);
        assert.equal(data.waiting_period_threshold, '55');

        success_callback = req.success;
        error_callback = req.error;
    };

    submit_form(ev);
    assert(patched);

    var response_data = {
        waiting_period_threshold: 55,
        add_emoji_by_admins_only: true,
        create_stream_by_admins_only: false,
    };
    success_callback(response_data);

    assert.equal($('#admin-realm-add-emoji-by-admins-only-status').val(),
                 'translated: Only administrators may now add new emoji!');
    assert.equal($('#admin-realm-create-stream-by-admins-only-status').val(),
                  'translated: Stream creation permission changed!');

    // TODO: change the code to have a better place to report status.
    var status_elem = $('#admin-realm-restricted-to-domain-status');

    success_callback({});

    assert.equal(status_elem.val(),
                 'translated: No changes to save!');

    error_callback({});
    assert.equal(status_elem.val(),
                 'translated: Failed');
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
    assert.equal($('#id_realm_message_content_edit_limit_minutes').attr('disabled'), true);

    change_message_editing.apply({checked: true});
    assert(!parent_elem.hasClass('control-label-disabled'));
    assert.equal($('#id_realm_message_content_edit_limit_minutes').prop('disabled'), false);
}

function test_change_invite_required(change_invite_required) {
    var parent_elem = $.create('invite-parent-stub');

    $('#id_realm_invite_by_admins_only_label').set_parent(parent_elem);

    change_invite_required.apply({checked: false});
    assert(parent_elem.hasClass('control-label-disabled'));
    assert.equal($('#id_realm_invite_by_admins_only').attr('disabled'), true);

    change_invite_required.apply({checked: true});
    assert(!parent_elem.hasClass('control-label-disabled'));
    assert.equal($('#id_realm_invite_by_admins_only').prop('disabled'), false);
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


    var elem_obj = $('<elem html>');
    var parents_obj = $.create('parents object');

    elem_obj.set_parents_result('tr', parents_obj);
    parents_obj.set_find_results('.domain', domain_obj);
    elem_obj.prop('checked', allow);

    change_allow_subdomains.apply('<elem html>', [ev]);

    success_callback();
    assert.equal(info.val(),
                 'translated: Update successful: Subdomains allowed for example.com');

    error_callback({});
    assert.equal(info.val(), 'translated: Failed');

    allow = false;
    elem_obj.prop('checked', allow);
    change_allow_subdomains.apply('<elem html>', [ev]);
    success_callback();
    assert.equal(info.val(),
                 'translated: Update successful: Subdomains no longer allowed for example.com');
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
    $('#id_realm_allow_message_editing').change = set_callback('change_message_editing');
    $('#submit-add-realm-domain').click = set_callback('add_realm_domain');
    $('.notifications-stream-disable').click = set_callback('disable_notifications_stream');
    $('.signup-notifications-stream-disable').click = set_callback('disable_signup_notifications_stream');

    var submit_settings_form;
    var submit_permissions_form;
    var submit_profile_form;
    $('.organization').on = function (action, selector, f) {
        if (selector === 'button.save-message-org-settings') {
            assert.equal(action, 'click');
            submit_settings_form = f;
        }
        if (selector === 'button.save-language-org-settings') {
            assert.equal(action, 'click');
        }
        if (selector === 'form.org-permissions-form') {
            assert.equal(action, 'submit');
            submit_permissions_form = f;
        }
        if (selector === 'form.org-profile-form') {
            assert.equal(action, 'submit');
            submit_profile_form = f;
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

    var parent_elem = $.create('waiting-period-parent-stub');
    $('#id_realm_waiting_period_threshold').set_parent(parent_elem);
    // TEST set_up() here, but this mostly just allows us to
    // get access to the click handlers.
    settings_org.set_up();

    verify_realm_domains();

    test_realms_domain_modal(callbacks.add_realm_domain);

    test_submit_profile_form(submit_profile_form);
    test_submit_settings_form(submit_settings_form);
    test_submit_permissions_form(submit_permissions_form);
    test_upload_realm_icon(upload_realm_icon);
    test_change_invite_required(callbacks.change_invite_required);
    test_change_message_editing(callbacks.change_message_editing);
    test_disable_notifications_stream(callbacks.disable_notifications_stream);
    test_disable_signup_notifications_stream(callbacks.disable_signup_notifications_stream);
    test_change_allow_subdomains(change_allow_subdomains);
}());

(function test_misc() {
    page_params.realm_default_language = 'es';
    settings_org.reset_realm_default_language();
    assert.equal($('#id_realm_default_language').val(), 'es');

    page_params.is_admin = false;
    var name_toggled;
    $('.change_name_tooltip').toggle = function () {
        name_toggled = true;
    };

    name_toggled = false;

    $('#full_name').attr('disabled', 'disabled');
    settings_org.toggle_name_change_display();
    assert.equal($('#full_name').prop('disabled'), false);
    assert(name_toggled);

    settings_org.toggle_name_change_display();
    assert.equal($('#full_name').attr('disabled'), 'disabled');
    assert(name_toggled);

    var email_tooltip_toggled;
    $('.change_email_tooltip').toggle = function () {
        email_tooltip_toggled = true;
    };

    $('#change_email .button').attr('disabled', false);
    settings_org.toggle_email_change_display();
    assert.equal($("#change_email .button").attr('disabled'), 'disabled');
    assert(email_tooltip_toggled);

    // Test should't toggle name display or email display for org admins.
    page_params.is_admin = true;
    name_toggled = false;
    $('#full_name').attr('disabled', false);
    settings_org.toggle_name_change_display();
    assert.equal($('#full_name').prop('disabled'), false);
    assert(!name_toggled);

    email_tooltip_toggled = false;
    $('#change_email .button').attr('disabled', false);
    settings_org.toggle_email_change_display();
    assert.equal($("#change_email .button").attr('disabled'), false);
    assert(!email_tooltip_toggled);

    page_params.realm_description = 'realm description';
    settings_org.update_realm_description();
    assert.equal($('#id_realm_description').val(), 'realm description');

    page_params.message_retention_days = 42;
    settings_org.update_message_retention_days();
    assert.equal($('#id_realm_message_retention_days').val(), 42);

    var elem = $('#realm_notifications_stream_name');
    stream_data.get_sub_by_id = function (stream_id) {
        assert.equal(stream_id, 42);
        return { name: 'some_stream' };
    };
    settings_org.render_notifications_stream_ui(42);
    assert.equal(elem.text(), '#some_stream');
    assert(!elem.hasClass('text-warning'));

    stream_data.get_sub_by_id = noop;
    settings_org.render_notifications_stream_ui();
    assert.equal(elem.text(), 'translated: Disabled');
    assert(elem.hasClass('text-warning'));

    elem = $('#realm_signup_notifications_stream_name');
    stream_data.get_sub_by_id = function (stream_id) {
        assert.equal(stream_id, 75);
        return { name: 'some_stream' };
    };
    page_params.new_user_bot_configured = false;
    settings_org.render_signup_notifications_stream_ui(75);
    assert.equal(elem.text(), 'translated: Disabled');
    assert(elem.hasClass('text-warning'));
    page_params.new_user_bot_configured = true;
    settings_org.render_signup_notifications_stream_ui(75);
    assert.equal(elem.text(), '#some_stream');
    assert(!elem.hasClass('text-warning'));

    stream_data.get_sub_by_id = noop;
    settings_org.render_signup_notifications_stream_ui();
    assert.equal(elem.text(), 'translated: Disabled');
    assert(elem.hasClass('text-warning'));

}());
