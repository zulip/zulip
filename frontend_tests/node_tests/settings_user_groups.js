zrequire('dict');
zrequire('user_pill');
zrequire('settings_user_groups');

set_global('$', global.make_zjquery());
set_global('i18n', global.stub_i18n);

var noop = function () {};

var pills = {
    pill: {},
};

var non_editable_pills = {
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

(function test_can_edit() {
    user_groups.is_member_of = function (group_id, user_id) {
        assert.equal(group_id, 1);
        assert.equal(user_id, undefined);
        return false;
    };
    settings_user_groups.can_edit(1);
}());

var user_group_selector = "#user-groups #1";
var cancel_selector = "#user-groups #1 .cancel";
var saved_selector = "#user-groups #1 .saved";
var name_selector = "#user-groups #1 .name";
var description_selector = "#user-groups #1 .description";
var instructions_selector = "#user-groups #1 .save-instructions";

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
        is_admin: true,
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
        assert.equal(args.id, 1);
        assert.equal(args.name, 'Mobile');
        assert.equal(args.description, 'All mobile people');
        assert(!args.is_non_member_first);
        templates_render_called = true;
        return fake_rendered_temp;
    };

    var user_groups_list_append_called = 0;
    $('#user-groups').append = function (rendered_temp) {
        if (rendered_temp === 'translated: <h3>Your groups</h3>') {
            user_groups_list_append_called += 1;
            return;
        }
        assert.equal(rendered_temp, fake_rendered_temp);
        user_groups_list_append_called += 1;
    };

    var get_person_from_user_id_called = false;
    var blueslip_warn_called = false;
    people.get_person_from_user_id = function (user_id) {
        if (user_id === iago.user_id) {
            return iago;
        }
        if (user_id === undefined) {
            return iago;
        }
        assert.equal(user_id, 4);
        blueslip.warn = function (err_msg) {
            assert.equal(err_msg, 'Unknown user ID 4 in members of user group Mobile');
            blueslip_warn_called = true;
        };
        get_person_from_user_id_called = true;
    };

    settings_user_groups.can_edit = function () {
        return true;
    };

    var pill_container_stub = $('.pill-container[data-group-pills="Mobile"]');

    var all_pills = {};

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

    var input_field_stub = $.create('fake-input-field');
    pill_container_stub.children = function () {
        return input_field_stub;
    };

    var input_typeahead_called = false;
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

            var saved_fade_out_called = false;
            var cancel_fade_to_called = false;
            var instructions_fade_to_called = false;
            $(saved_selector).fadeOut = function () {
                saved_fade_out_called = true;
            };
            $(cancel_selector).css = function (data) {
                if (typeof(data) === 'string') {
                    assert.equal(data, 'display');
                }
                assert.equal(typeof(data), 'object');
                assert.equal(data.display, 'inline-block');
                assert.equal(data.opacity, '0');
                return $(cancel_selector);
            };
            $(cancel_selector).fadeTo = function () {
                cancel_fade_to_called = true;
            };
            $(instructions_selector).css = function (data) {
                if (typeof(data) === 'string') {
                    assert.equal(data, 'display');
                }
                assert.equal(typeof(data), 'object');
                assert.equal(data.display, 'block');
                assert.equal(data.opacity, '0');
                return $(instructions_selector);
            };
            $(instructions_selector).fadeTo = function () {
                instructions_fade_to_called = true;
            };

            text_cleared = false;
            config.updater(alice);
            // update_cancel_button is called.
            assert(saved_fade_out_called);
            assert(cancel_fade_to_called);
            assert(instructions_fade_to_called);
            assert.equal(text_cleared, true);
        }());
        input_typeahead_called = true;
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
    var create_item_handler;
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
        global.patch_builtin('setTimeout', function (func) {
            func();
        });
        realm_user_group.members = Dict.from_array([2, 31]);
        handler();
    };

    function input_pill_stub(opts) {
        assert.equal(opts.container, pill_container_stub);
        create_item_handler = opts.create_item_from_text;
        assert(create_item_handler);
        return pills;
    }
    set_global('input_pill', {
        create: input_pill_stub,
    });

    settings_user_groups.set_up();
    assert(templates_render_called);
    assert.equal(user_groups_list_append_called, 2);
    assert(get_person_from_user_id_called);
    assert(blueslip_warn_called);
    assert(input_typeahead_called);
    test_create_item(create_item_handler);

    // Tests for settings_user_groups.set_up workflow.
    assert.equal(typeof($('.organization form.admin-user-group-form').get_on_handler("submit")), 'function');
    assert.equal(typeof($('#user-groups').get_on_handler('click', '.delete')), 'function');
    assert.equal(typeof($('#user-groups').get_on_handler('keypress', '.user-group h4 > span')), 'function');
}());
(function test_with_external_user() {

    var realm_user_group = {
        id: 1,
        name: 'Mobile',
        description: 'All mobile people',
        members: Dict.from_array([3, 5]),
    };
    var othello = {
        email: 'othello@zulip.com',
        user_id: 3,
        full_name: 'othello',
    };
    user_groups.get_realm_user_groups = function () {
        return [realm_user_group];
    };

    var templates_render_called = false;
    var fake_rendered_temp = $.create('fake_non_editable_user_group_template_rendered');
    templates.render = function (template, args) {
        assert.equal(template, 'non_editable_user_group');
        assert.equal(args.user_group.id, 1);
        assert.equal(args.user_group.name, 'Mobile');
        assert.equal(args.user_group.description, 'All mobile people');
        templates_render_called = true;
        return fake_rendered_temp;
    };

    var get_person_from_user_id_called = false;
    var blueslip_warn_called = false;
    people.get_person_from_user_id = function (id) {
        if (id === othello.user_id) {
            return othello;
        }
        if (id === undefined) {
            return othello;
        }
        assert.equal(id, 5);
        blueslip.warn = function (err_msg) {
            assert.equal(err_msg, 'Unknown user ID 5 in members of user group Mobile');
            blueslip_warn_called = true;
        };
        get_person_from_user_id_called = true;
    };

    var can_edit_called = 0;
    settings_user_groups.can_edit = function () {
        can_edit_called += 1;
        return false;
    };

    var pill_container_stub = $('.pill-container[data-group-pills="Mobile"]');
    var user_groups_append_called = 0;
    $('#user-groups').append = function (opts) {
        if (opts === 'translated: <h3>Other groups</h3>') {
            user_groups_append_called += 1;
            return;
        }
        if (opts === 'translated: <p>You are not a part of any groups.</p>') {
            user_groups_append_called += 1;
            return;
        }
        if (opts === 'translated: <h3>Your groups</h3>') {
            user_groups_append_called += 1;
            return;
        }
        assert.equal(opts, fake_rendered_temp);
        user_groups_append_called += 1;
    };

    var all_pills = {};

    non_editable_pills.appendValidatedData = function (item) {
        var id = item.user_id;
        assert.equal(all_pills[id], undefined);
        all_pills[id] = item;
    };

    non_editable_pills.items = function () {
        return _.values(all_pills);
    };

    function input_pill_stub(opts) {
        assert.equal(opts.container, pill_container_stub);
        return non_editable_pills;
    }
    set_global('input_pill', {
        create_non_editable_pills: input_pill_stub,
    });

    settings_user_groups.populate_user_groups();
    assert.equal(user_groups_append_called, 4);
    assert.equal(can_edit_called, 1);
    assert(templates_render_called);
    assert(get_person_from_user_id_called);
    assert(blueslip_warn_called);
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
        var handler = $('.organization form.admin-user-group-form').get_on_handler("submit");
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

    (function test_do_not_blur() {
        var blur_event_classes = [".name", ".description", ".input"];
        var api_endpoint_called = false;
        channel.post = function () {
            api_endpoint_called = true;
        };
        channel.patch = noop;
        var fake_this = $.create('fake-#user-groups_do_not_blur');
        var event = {
            relatedTarget: fake_this,
        };

        // Any of the blur_exceptions trigger blur event.
        _.each(blur_event_classes, function (class_name) {
            var handler = $(user_group_selector).get_on_handler("blur", class_name);
            var blur_exceptions = _.without([".pill-container", ".name", ".description", ".input", ".delete"],
                                            class_name);
            _.each(blur_exceptions, function (blur_exception) {
                api_endpoint_called = false;
                fake_this.closest = function (class_name) {
                    if (class_name === blur_exception || class_name === user_group_selector) {
                        return [1];
                    }
                    return [];
                };
                handler.call(fake_this, event);
                assert(!api_endpoint_called);
            });

            api_endpoint_called = false;
            fake_this.closest = function (class_name) {
                if (class_name === ".typeahead") {
                    return [1];
                }
                return [];
            };
            handler.call(fake_this, event);
            assert(!api_endpoint_called);

            // Cancel button triggers blur event.
            var settings_user_groups_reload_called = false;
            settings_user_groups.reload = function () {
                settings_user_groups_reload_called = true;
            };
            api_endpoint_called = false;
            fake_this.closest = function (class_name) {
                if (class_name === ".cancel" || class_name === user_group_selector) {
                    return [1];
                }
                return [];
            };
            handler.call(fake_this, event);
            assert(!api_endpoint_called);
            assert(settings_user_groups_reload_called);
        });

    }());

    (function test_update_cancel_button() {
        var handler_name = $(user_group_selector).get_on_handler("input", ".name");
        var handler_desc = $(user_group_selector).get_on_handler("input", ".description");
        var sib_des = $(description_selector);
        var sib_name = $(name_selector);
        sib_name.text(i18n.t('mobile'));
        sib_des.text(i18n.t('All mobile members'));

        var group_data = {
            name: 'translated: mobile',
            description: 'translated: All mobile members',
            members: Dict.from_array([2, 31])};
        user_groups.get_user_group_from_id = function () {
            return group_data;
        };

        var cancel_fade_out_called = false;
        var instructions_fade_out_called = false;
        $(cancel_selector).show();
        $(cancel_selector).fadeOut = function () {
            cancel_fade_out_called = true;
        };
        $(instructions_selector).fadeOut = function () {
            instructions_fade_out_called = true;
        };

        // Cancel button removed if user group if user group has no changes.
        var fake_this = $.create('fake-#update_cancel_button');
        handler_name.call(fake_this);
        assert(cancel_fade_out_called);
        assert(instructions_fade_out_called);

        // Check for handler_desc to achieve 100% coverage.
        cancel_fade_out_called = false;
        instructions_fade_out_called = false;
        handler_desc.call(fake_this);
        assert(cancel_fade_out_called);
        assert(instructions_fade_out_called);
    }());

    (function test_user_groups_save_group_changes_triggered() {
        var handler_name = $(user_group_selector).get_on_handler("blur", ".name");
        var handler_desc = $(user_group_selector).get_on_handler("blur", ".description");
        var sib_des = $(description_selector);
        var sib_name = $(name_selector);
        sib_name.text(i18n.t('mobile'));
        sib_des.text(i18n.t('All mobile members'));

        var group_data = {members: Dict.from_array([2, 31])};
        user_groups.get_user_group_from_id = function () {
            return group_data;
        };
        var api_endpoint_called = false;
        var cancel_fade_out_called = false;
        var saved_fade_to_called = false;
        var instructions_fade_out_called = false;
        $(instructions_selector).fadeOut = function () {
            instructions_fade_out_called = true;
        };
        $(cancel_selector).fadeOut = function () {
            cancel_fade_out_called = true;
        };
        $(saved_selector).css = function (data) {
            if (typeof(data) === 'string') {
                assert.equal(data, 'display');
            }
            assert.equal(typeof(data), 'object');
            assert.equal(data.display, 'inline-block');
            assert.equal(data.opacity, '0');
            return $(saved_selector);
        };
        $(saved_selector).fadeTo = function () {
            saved_fade_to_called = true;
        };

        channel.patch = function (opts) {
            assert.equal(opts.url, "/json/user_groups/1");
            assert.equal(opts.data.name, 'translated: mobile');
            assert.equal(opts.data.description, 'translated: All mobile members');
            api_endpoint_called = true;
            (function test_post_success() {
                global.patch_builtin('setTimeout', function (func) {
                    func();
                });
                opts.success();
                assert(cancel_fade_out_called);
                assert(instructions_fade_out_called);
                assert(saved_fade_to_called);
            }());
        };

        var fake_this = $.create('fake-#user-groups_blur_name');
        fake_this.closest = function () {
            return [];
        };
        fake_this.set_parents_result(user_group_selector, $(user_group_selector));
        var event = {
            relatedTarget: fake_this,
        };

        api_endpoint_called = false;
        handler_name.call(fake_this, event);
        assert(api_endpoint_called);

        // Check API endpoint isn't called if name and desc haven't changed.
        group_data.name = "translated: mobile";
        group_data.description = "translated: All mobile members";
        api_endpoint_called = false;
        handler_name.call(fake_this, event);
        assert(!api_endpoint_called);

        // Check for handler_desc to achieve 100% coverage.
        api_endpoint_called = false;
        handler_desc.call(fake_this, event);
        assert(!api_endpoint_called);
    }());

    (function test_user_groups_save_member_changes_triggered() {
        var handler = $(user_group_selector).get_on_handler("blur", ".input");
        var realm_user_group = {
            id: 1,
            name: 'Mobile',
            description: 'All mobile people',
            members: Dict.from_array([2, 4]),
        };

        user_groups.get_user_group_from_id = function (id) {
            assert.equal(id, 1);
            return realm_user_group;
        };

        var cancel_fade_out_called = false;
        var saved_fade_to_called = false;
        var instructions_fade_out_called = false;
        $(instructions_selector).fadeOut = function () {
            instructions_fade_out_called = true;
        };
        $(cancel_selector).fadeOut = function () {
            cancel_fade_out_called = true;
        };
        $(saved_selector).css = function () {
            return $(saved_selector);
        };
        $(saved_selector).fadeTo = function () {
            saved_fade_to_called = true;
        };

        var api_endpoint_called = false;
        channel.post = function (opts) {
            assert.equal(opts.url, "/json/user_groups/1/members");
            assert.equal(opts.data.add, '[31]');
            assert.equal(opts.data.delete, '[4]');
            api_endpoint_called = true;

            (function test_post_success() {
                opts.success();
                assert(cancel_fade_out_called);
                assert(instructions_fade_out_called);
                assert(saved_fade_to_called);
            }());
        };

        var fake_this = $.create('fake-#user-groups_blur_input');
        fake_this.set_parents_result(user_group_selector, $(user_group_selector));
        fake_this.closest = function () {
            return [];
        };
        var event = {
            relatedTarget: fake_this,
        };

        api_endpoint_called = false;
        handler.call(fake_this, event);
        assert(api_endpoint_called);
    }());
}());
