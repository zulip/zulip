zrequire('settings_user_groups');

set_global('$', global.make_zjquery());
set_global('i18n', global.stub_i18n);

var noop = function () {};

set_global('channel', {});
set_global('user_groups', {
    get_user_group_from_id: noop,
    remove: noop,
    add: noop,
});
set_global('ui_report', {});
set_global('people', {
    my_current_user_id: noop,
});

(function test_set_up() {
    var populate_user_groups_called = false;
    settings_user_groups.populate_user_groups = function () {
        populate_user_groups_called = true;
    };
    settings_user_groups.set_up();
    assert(populate_user_groups_called);
    assert.equal(typeof($('.organization').get_on_handler("submit", "form.admin-user-group-form")), 'function');
    assert.equal(typeof($('#user-groups').get_on_handler('click', '.delete')), 'function');
    assert.equal(typeof($('#user-groups').get_on_handler('keypress', '.user-group h4 > span')), 'function');
    assert.equal(typeof($('#user-groups').get_on_handler('input', '.user-group h4 > span')), 'function');
    assert.equal(typeof($('#user-groups').get_on_handler('click', '.save-group-changes')), 'function');
}());

(function test_reload() {
    $('#user-groups').html('Some text');
    var populate_user_groups_called = false;
    settings_user_groups.populate_user_groups = function () {
        populate_user_groups_called = true;
    };
    settings_user_groups.reload();
    assert(populate_user_groups_called);
    assert.equal($('#user-groups').html(), '');
}());

(function test_on_events() {
    (function test_admin_user_group_form_submit_triggered() {
        var handler = $('.organization').get_on_handler("submit", "form.admin-user-group-form");
        var event = {
            stopPropagation: noop,
            preventDefault: noop,
        };
        var fake_this = $.create('fake-form.admin-user-group-form');
        var fake_object_array = [{
            name: 'fake-name',
            value: '',
        }, {
            name: 'fake-name',
            value: 'fake-value',
        }];
        fake_this.serializeArray = function () {
            return fake_object_array;
        };
        channel.post = function (payload) {
            var data = {
                members: '[null]',
            };
            data[fake_object_array[1].name] = fake_object_array[1].value;
            assert.equal(payload.url, "/json/user_groups/create");
            assert.deepEqual(payload.data, data);

            (function test_post_success() {
                $('#admin-user-group-status').show();
                $("form.admin-user-group-form input[type='text']").val('fake-content');
                ui_report.success = function (text, ele) {
                    assert.equal(text, 'translated: User group added!');
                    assert.equal(ele, $('#admin-user-group-status'));
                };

                payload.success();

                assert(!$('#admin-user-group-status').visible());
                assert.equal($("form.admin-user-group-form input[type='text']").val(), '');
            }());

            (function test_post_error() {
                $('#admin-user-group-status').show();
                ui_report.error = function (error_msg, error_obj, ele) {
                    var xhr = {
                        responseText: '{"msg":"fake-msg"}',
                    };
                    assert.equal(error_msg, 'translated: Failed');
                    assert.deepEqual(error_obj, xhr);
                    assert.equal(ele, $('#admin-user-group-status'));
                };
                var xhr = {
                    responseText: '{"msg":"fake-msg", "attrib":"val"}',
                };
                payload.error(xhr);

                assert(!$('#admin-user-group-status').visible());
            }());
        };

        handler.call(fake_this, event);
    }());

    (function test_user_groups_delete_click_triggered() {
        var handler = $('#user-groups').get_on_handler("click", ".delete");
        var fake_this = $.create('fake-#user-groups.delete_btn');
        fake_this.set_parents_result('.user-group', $('.user-group'));
        $('.user-group').attr('id', '1');

        channel.del = function (payload) {
            var data = {
                id: 1,
            };
            var settings_user_groups_reload_called = false;
            assert.equal(payload.url, "/json/user_groups/1");
            assert.deepEqual(payload.data, data);

            settings_user_groups.reload = function () {
                settings_user_groups_reload_called = true;
            };
            payload.success();
            assert(settings_user_groups_reload_called);

            fake_this.text(i18n.t('fake-text'));
            payload.error();
            assert.equal(fake_this.text(), 'translated: Failed!');
        };

        handler.call(fake_this);
    }());

    (function test_user_groups_keypress_enter_triggered() {
        var handler = $('#user-groups').get_on_handler("keypress", ".user-group h4 > span");
        var default_action_for_enter_stopped = false;
        var event = {
            which: 13,
            preventDefault: function () {
                default_action_for_enter_stopped = true;
            },
        };
        handler(event);
        assert(default_action_for_enter_stopped);
    }());

    (function test_user_groups_title_description_input_triggered() {
        var handler = $('#user-groups').get_on_handler("input", ".user-group h4 > span");
        var sib_span = $.create('fake-input-span');
        var sib_save = $.create('fake-input-save');
        var sib_save_display = 'none';
        $('.user-group').attr('id', '2');
        sib_span.attr('class', 'description');
        sib_span.text(i18n.t('All mobile members'));
        var fake_this = $.create('fake-#user-groups_input');
        fake_this.className = 'name';
        fake_this.text(i18n.t('mobile'));
        fake_this.siblings = function (sel) {
            function first() {
                return this;
            }
            sib_span.first = first;
            sib_save.first = first;
            if (sel === 'span') {
                return sib_span;
            } else if (sel === '.save-group-changes') {
                return sib_save;
            }
        };
        fake_this.set_parents_result('.user-group', $('.user-group'));
        sib_save.css = function (data) {
            if (typeof(data) === 'string') {
                assert.equal(data, 'display');
                return sib_save_display;
            }
            assert.equal(typeof(data), 'object');
            assert.equal(data.display, 'inline');
            assert.equal(data.opacity, '0');
            sib_save_display = 'inline';
            return sib_save;
        };
        var save_btn_fade_out_called = false;
        sib_save.fadeOut = function () {
            save_btn_fade_out_called = true;
            sib_save_display = 'none';
        };

        user_groups.get_user_group_from_id = function () {
            return {
                name: 'mob',
                description: 'all mob members',
            };
        };
        handler.call(fake_this);
        assert(!save_btn_fade_out_called);

        user_groups.get_user_group_from_id = function () {
            return {
                name: 'translated: mobile',
                description: 'translated: All mobile members',
            };
        };
        handler.call(fake_this);
        assert(save_btn_fade_out_called);
    }());

    (function test_user_groups_click_save_group_changes_triggered() {
        var handler = $('#user-groups').get_on_handler("click", ".save-group-changes");
        var sib_name = $.create('.name');
        var sib_des = $.create('.description');
        var fake_this = $.create('fake-#user-groups_click_save');
        $('.user-group').attr('id', '3');
        sib_name.text(i18n.t('mobile'));
        sib_des.text(i18n.t('All mobile members'));
        fake_this.set_parents_result('.user-group', $('.user-group'));
        fake_this.siblings = function (sel) {
            if (sel === '.description') {
                return sib_des;
            } else if (sel === '.name') {
                return sib_name;
            }
        };
        var group_data = {};
        user_groups.get_user_group_from_id = function () {
            return group_data;
        };

        channel.patch = function (payload) {
            assert.equal(payload.url, "/json/user_groups/3");
            assert.equal(payload.data.name, 'translated: mobile');
            assert.equal(payload.data.description, 'translated: All mobile members');

            (function test_post_success() {
                fake_this.text(i18n.t('fake-text'));
                fake_this.delay = function (time) {
                    assert.equal(time, 200);
                    return fake_this;
                };
                fake_this.html('');
                var save_btn_fade_out_called = false;
                fake_this.fadeOut = function (func) {
                    assert.equal(typeof(func), 'function');
                    save_btn_fade_out_called = true;
                    func.call(fake_this);
                };
                payload.success();
                assert(save_btn_fade_out_called);
                assert.equal(fake_this.html(), '<i class="fa fa-check" aria-hidden="true"></i>');
                assert.equal(fake_this.text(), 'translated: Saved!');
            }());

            (function test_post_error() {
                fake_this.text(i18n.t('fake-text'));
                payload.error();
                assert.equal(fake_this.text(), 'translated: Failed!');
            }());
        };

        handler.call(fake_this);
        assert.equal(group_data.name, 'translated: mobile');
        assert.equal(group_data.description, 'translated: All mobile members');
    }());
}());
