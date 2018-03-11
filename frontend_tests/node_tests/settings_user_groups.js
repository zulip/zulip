zrequire('dict');
zrequire('user_pill');
zrequire('settings_user_groups');

set_global('$', global.make_zjquery());
set_global('i18n', global.stub_i18n);

var noop = function () {};

var pills = {
    pill: {},
};
set_global('channel', {});
set_global('templates', {});
set_global('blueslip', {});
set_global('typeahead_helper', {});
set_global('user_groups', {
    get_user_group_from_id: noop,
    remove: noop,
    add: noop,
});
set_global('ui_report', {});
set_global('people', {
    my_current_user_id: noop,
});

(function test_populate_user_groups() {
    var realm_user_group = {
        id: 1,
        name: 'Mobile',
        description: 'All mobile people',
        members: Dict.from_array([2, 4]),
    };
    var iago = {
        email: 'iago@zulip.com',
        user_id: 2,
        full_name: 'Iago',
    };
    var alice = {
        email: 'alice@example.com',
        user_id: 31,
        full_name: 'Alice',
    };
    var bob = {
        email: 'bob@example.com',
        user_id: 32,
        full_name: 'Bob',
    };

    people.get_realm_persons = function () {
        return [iago, alice, bob];
    };

    user_groups.get_realm_user_groups = function () {
        return [realm_user_group];
    };
    var templates_render_called = false;
    var fake_rendered_temp = $.create('fake_admin_user_group_list_template_rendered');
    templates.render = function (template, args) {
        assert.equal(template, 'admin_user_group_list');
        assert.equal(args.user_group.id, 1);
        assert.equal(args.user_group.name, 'Mobile');
        assert.equal(args.user_group.description, 'All mobile people');
        templates_render_called = true;
        return fake_rendered_temp;
    };

    var user_groups_list_append_called = false;
    $('#user-groups').append = function (rendered_temp) {
        assert.equal(rendered_temp, fake_rendered_temp);
        user_groups_list_append_called = true;
    };

    var get_person_from_user_id_called = false;
    var blueslip_warn_called = false;
    people.get_person_from_user_id = function (user_id) {
        if (user_id === iago.user_id) {
            return iago;
        }
        assert.equal(user_id, 4);
        blueslip.warn = function (err_msg) {
            assert.equal(err_msg, 'Unknown user ID 4 in members of user group Mobile');
            blueslip_warn_called = true;
        };
        get_person_from_user_id_called = true;
    };

    var all_pills = {};

    var pill_container_stub = $('.pill-container[data-group-pills="Mobile"]');
    pills.appendValidatedData = function (item) {
        var id = item.user_id;
        assert.equal(all_pills[id], undefined);
        all_pills[id] = item;
    };
    pills.items = function () {
        return _.values(all_pills);
    };

    var text_cleared;
    pills.clear_text = function () {
        text_cleared = true;
    };

    var create_item_handler;

    function input_pill_stub(opts) {
        assert.equal(opts.container, pill_container_stub);
        create_item_handler = opts.create_item_from_text;
        assert(create_item_handler);
        return pills;
    }
    var input_field_stub = $.create('fake-input-field');
    pill_container_stub.children = function () {
        return input_field_stub;
    };

    var input_typeahead_called = false;
    var sibling_context = {};
    var fade_to_called = false;
    var fade_out_called = false;
    input_field_stub.typeahead = function (config) {
        assert.equal(config.items, 5);
        assert(config.fixed);
        assert(config.dropup);
        assert(config.stopAdvance);
        assert.equal(typeof(config.source), 'function');
        assert.equal(typeof(config.highlighter), 'function');
        assert.equal(typeof(config.matcher), 'function');
        assert.equal(typeof(config.sorter), 'function');
        assert.equal(typeof(config.updater), 'function');

        (function test_highlighter() {
            var fake_person = $.create('fake-person');
            typeahead_helper.render_person = function () {
                return fake_person;
            };
            assert.equal(config.highlighter(), fake_person);
        }());

        var fake_context = {
            query: 'ali',
        };

        (function test_source() {
            var result = config.source.call(fake_context, iago);
            var emails = _.pluck(result, 'email').sort();
            assert.deepEqual(emails, [alice.email, bob.email]);
        }());

        (function test_matcher() {
            /* Here the query doesn't begin with an '@' because typeahead is triggered
            by the '@' sign and thus removed in the query. */
            var result = config.matcher.call(fake_context, iago);
            assert(!result);

            result = config.matcher.call(fake_context, alice);
            assert(result);
        }());

        (function test_sorter() {
            var sort_recipientbox_typeahead_called = false;
            typeahead_helper.sort_recipientbox_typeahead = function () {
                sort_recipientbox_typeahead_called = true;
            };
            config.sorter.call(fake_context);
            assert(sort_recipientbox_typeahead_called);
        }());

        (function test_updater() {
            input_field_stub.text('@ali');
            user_groups.get_user_group_from_id = function () {
                return realm_user_group;
            };
            pill_container_stub.siblings = function (sel) {
                assert.equal(sel, '.save-member-changes');
                return sibling_context;
            };
            text_cleared = false;
            config.updater(alice);
            assert.equal(text_cleared, true);
            assert.equal(pill_container_stub
                .siblings('.save-member-changes')
                .css('display'), 'inline-block');
        }());
        assert(fade_to_called);
        assert(!fade_out_called);
        input_typeahead_called = true;
    };

    sibling_context.display_val = 'none';
    sibling_context.fadeOut = function () {
        fade_out_called = true;
    };
    sibling_context.fadeTo = function () {
        fade_to_called = true;
    };
    sibling_context.css = function (prop) {
        if (typeof(prop)  === 'string') {
            assert.equal(prop, 'display');
            return this.display_val;
        }
        assert.equal(typeof(prop), 'object');
        assert.equal(prop.display, 'inline-block');
        assert.equal(prop.opacity, '0');
        this.display_val = 'inline-block';
        return this;
    };

    var get_by_email_called = false;
    people.get_by_email = function (user_email) {
        get_by_email_called = true;
        if (user_email === iago.email) {
            return iago;
        }
        if (user_email === bob.email) {
            return bob;
        }
        assert.equal(user_email,
            'Expected user email to be of Alice or Iago here.');
    };
    pills.onPillCreate = function (handler) {
        assert.equal(typeof(handler), 'function');
        handler();
    };

    function test_create_item(handler) {
        (function test_rejection_path() {
            var item = handler(iago.email, pills.items());
            assert(get_by_email_called);
            assert.equal(item, undefined);
        }());

        (function test_success_path() {
            get_by_email_called = false;
            var res = handler(bob.email, pills.items());
            assert(get_by_email_called);
            assert.equal(typeof(res), 'object');
            assert.equal(res.user_id, bob.user_id);
            assert.equal(res.display_value, bob.full_name);
        }());
    }

    pills.onPillRemove = function (handler) {
        realm_user_group.members = Dict.from_array([2, 31]);
        fade_to_called = false;
        fade_out_called = false;
        handler();
        assert(!fade_to_called);
        assert(fade_out_called);
    };

    set_global('input_pill', {
        create: input_pill_stub,
    });
    settings_user_groups.set_up();
    assert(templates_render_called);
    assert(user_groups_list_append_called);
    assert(get_person_from_user_id_called);
    assert(blueslip_warn_called);
    assert(input_typeahead_called);
    test_create_item(create_item_handler);

    // Tests for settings_user_groups.set_up workflow.
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

(function test_reset() {
    settings_user_groups.reset();
    var result = settings_user_groups.reload();
    assert.equal(result, undefined);
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
        channel.post = function (opts) {
            var data = {
                members: '[null]',
            };
            data[fake_object_array[1].name] = fake_object_array[1].value;
            assert.equal(opts.url, "/json/user_groups/create");
            assert.deepEqual(opts.data, data);

            (function test_post_success() {
                $('#admin-user-group-status').show();
                $("form.admin-user-group-form input[type='text']").val('fake-content');
                ui_report.success = function (text, ele) {
                    assert.equal(text, 'translated: User group added!');
                    assert.equal(ele, $('#admin-user-group-status'));
                };

                opts.success();

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
                opts.error(xhr);

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

        channel.del = function (opts) {
            var data = {
                id: 1,
            };
            var settings_user_groups_reload_called = false;
            assert.equal(opts.url, "/json/user_groups/1");
            assert.deepEqual(opts.data, data);

            settings_user_groups.reload = function () {
                settings_user_groups_reload_called = true;
            };
            opts.success();
            assert(settings_user_groups_reload_called);

            fake_this.text(i18n.t('fake-text'));
            opts.error();
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

        channel.patch = function (opts) {
            assert.equal(opts.url, "/json/user_groups/3");
            assert.equal(opts.data.name, 'translated: mobile');
            assert.equal(opts.data.description, 'translated: All mobile members');

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
                opts.success();
                assert(save_btn_fade_out_called);
                assert.equal(fake_this.html(), '<i class="fa fa-check" aria-hidden="true"></i>');
                assert.equal(fake_this.text(), 'translated: Saved!');
            }());

            (function test_post_error() {
                fake_this.text(i18n.t('fake-text'));
                opts.error();
                assert.equal(fake_this.text(), 'translated: Failed!');
            }());
        };

        handler.call(fake_this);
        assert.equal(group_data.name, 'translated: mobile');
        assert.equal(group_data.description, 'translated: All mobile members');
    }());

    (function test_user_groups_click_save_member_changes_triggered() {
        var handler = $('#user-groups #1').get_on_handler("click", ".save-member-changes");
        var realm_user_group = {
            id: 1,
            name: 'Mobile',
            description: 'All mobile people',
            members: Dict.from_array([2, 4]),
        };
        var fake_this = $.create('fake-#user-groups_click_save_member_changes');
        user_groups.get_user_group_from_id = function (id) {
            assert.equal(id, 1);
            return realm_user_group;
        };

        channel.post = function (opts) {
            assert.equal(opts.url, "/json/user_groups/1/members");
            assert.equal(opts.data.add, '[31]');
            assert.equal(opts.data.delete, '[4]');

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
                opts.success();
                assert(save_btn_fade_out_called);
                assert.equal(fake_this.html(), '<i class="fa fa-check" aria-hidden="true"></i>');
                assert.equal(fake_this.text(), 'translated: Saved!');
            }());

            (function test_post_error() {
                fake_this.text(i18n.t('fake-text'));
                opts.error();
                assert.equal(fake_this.text(), 'translated: Failed!');
            }());
        };

        handler.call(fake_this);
    }());
}());
