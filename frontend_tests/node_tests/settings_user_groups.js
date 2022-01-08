"use strict";

const {strict: assert} = require("assert");

const _ = require("lodash");

const {$t} = require("../zjsunit/i18n");
const {mock_esm, set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const blueslip = require("../zjsunit/zblueslip");
const $ = require("../zjsunit/zjquery");
const {page_params} = require("../zjsunit/zpage_params");

const noop = () => {};

const pills = {
    pill: {},
};

let create_item_handler;

const channel = mock_esm("../../static/js/channel");
const confirm_dialog = mock_esm("../../static/js/confirm_dialog");
const input_pill = mock_esm("../../static/js/input_pill");
const typeahead_helper = mock_esm("../../static/js/typeahead_helper");
const user_groups = mock_esm("../../static/js/user_groups", {
    get_user_group_from_id: noop,
    remove: noop,
    add: noop,
});
const ui_report = mock_esm("../../static/js/ui_report");

const people = zrequire("people");
const settings_config = zrequire("settings_config");
const settings_data = zrequire("settings_data");
const settings_user_groups = zrequire("settings_user_groups");
const user_pill = zrequire("user_pill");

function reset_test_setup(pill_container_stub) {
    function input_pill_stub(opts) {
        assert.equal(opts.container, pill_container_stub);
        create_item_handler = opts.create_item_from_text;
        assert.ok(create_item_handler);
        return pills;
    }
    input_pill.create = input_pill_stub;
}

function test_ui(label, f) {
    // The sloppy_$ flag lets us re-use setup from prior tests.
    run_test(label, f, {sloppy_$: true});
}

test_ui("can_edit", () => {
    settings_data.user_can_edit_user_groups = () => false;
    assert.ok(!settings_user_groups.can_edit(1));

    settings_data.user_can_edit_user_groups = () => true;
    user_groups.is_member_of = (group_id, user_id) => {
        assert.equal(group_id, 1);
        assert.equal(user_id, undefined);
        return false;
    };
    assert.ok(!settings_user_groups.can_edit(1));

    page_params.is_admin = true;
    assert.ok(settings_user_groups.can_edit(1));

    page_params.is_admin = false;
    page_params.is_moderator = true;
    assert.ok(settings_user_groups.can_edit(1));

    page_params.is_admin = false;
    page_params.is_moderator = false;
    user_groups.is_member_of = (group_id, user_id) => {
        assert.equal(group_id, 1);
        assert.equal(user_id, undefined);
        return true;
    };
    assert.ok(settings_user_groups.can_edit(1));
});

const user_group_selector = `#user-groups #${CSS.escape(1)}`;
const cancel_selector = `#user-groups #${CSS.escape(1)} .save-status.btn-danger`;
const saved_selector = `#user-groups #${CSS.escape(1)} .save-status.sea-green`;
const name_selector = `#user-groups #${CSS.escape(1)} .name`;
const description_selector = `#user-groups #${CSS.escape(1)} .description`;
const instructions_selector = `#user-groups #${CSS.escape(1)} .save-instructions`;

test_ui("populate_user_groups", ({override_rewire, mock_template}) => {
    const realm_user_group = {
        id: 1,
        name: "Mobile",
        description: "All mobile people",
        members: new Set([2, 4]),
    };
    const iago = {
        email: "iago@zulip.com",
        user_id: 2,
        full_name: "Iago",
    };
    const alice = {
        email: "alice@example.com",
        user_id: 31,
        full_name: "Alice",
    };
    const bob = {
        email: "bob@example.com",
        user_id: 32,
        full_name: "Bob",
    };

    people.add_active_user(iago);
    people.add_active_user(alice);
    people.add_active_user(bob);

    people.get_realm_users = () => [iago, alice, bob];

    user_groups.get_realm_user_groups = () => [realm_user_group];

    people.get_visible_email = () => bob.email;

    let templates_render_called = false;
    const fake_rendered_temp = $.create("fake_admin_user_group_list_template_rendered");
    mock_template("settings/admin_user_group_list.hbs", false, (args) => {
        assert.equal(args.user_group.id, 1);
        assert.equal(args.user_group.name, "Mobile");
        assert.equal(args.user_group.description, "All mobile people");
        templates_render_called = true;
        return fake_rendered_temp;
    });

    let user_groups_list_append_called = false;
    $("#user-groups").append = (rendered_temp) => {
        assert.equal(rendered_temp, fake_rendered_temp);
        user_groups_list_append_called = true;
    };

    let get_by_user_id_called = false;
    people.get_by_user_id = (user_id) => {
        if (user_id === iago.user_id) {
            return iago;
        }
        if (user_id === alice.user_id) {
            return alice;
        }
        if (user_id === undefined) {
            return noop;
        }
        assert.equal(user_id, 4);
        blueslip.expect("warn", "Undefined user in function append_user");
        get_by_user_id_called = true;
        return undefined;
    };
    people.is_known_user = function () {
        return people.get_by_user_id !== undefined && people.get_by_user_id !== noop;
    };

    override_rewire(settings_user_groups, "can_edit", () => true);

    const all_pills = new Map();

    const pill_container_stub = $(`.pill-container[data-group-pills="${CSS.escape(1)}"]`);
    pills.appendValidatedData = (item) => {
        const id = item.user_id;
        assert.ok(!all_pills.has(id));
        all_pills.set(id, item);
    };
    pills.items = () => Array.from(all_pills.values());

    let text_cleared;
    pills.clear_text = () => {
        text_cleared = true;
    };

    const input_field_stub = $.create("fake-input-field");
    pill_container_stub.children = () => input_field_stub;

    let input_typeahead_called = false;
    input_field_stub.typeahead = (config) => {
        assert.equal(config.items, 5);
        assert.ok(config.fixed);
        assert.ok(config.dropup);
        assert.ok(config.stopAdvance);
        assert.equal(typeof config.source, "function");
        assert.equal(typeof config.highlighter, "function");
        assert.equal(typeof config.matcher, "function");
        assert.equal(typeof config.sorter, "function");
        assert.equal(typeof config.updater, "function");

        (function test_highlighter() {
            const fake_person = $.create("fake-person");
            typeahead_helper.render_person = () => fake_person;
            assert.equal(config.highlighter(), fake_person);
        })();

        const fake_context = {
            query: "ali",
        };

        const fake_context_for_email = {
            query: "am",
        };

        (function test_source() {
            const result = config.source.call(fake_context, iago);
            const emails = result.map((user) => user.email).sort();
            assert.deepEqual(emails, [alice.email, bob.email]);
        })();

        (function test_matcher() {
            /* Here the query doesn't begin with an '@' because typeahead is triggered
            by the '@' sign and thus removed in the query. */
            let result = config.matcher.call(fake_context, iago);
            assert.ok(!result);

            result = config.matcher.call(fake_context, alice);
            assert.ok(result);

            page_params.realm_email_address_visibility =
                settings_config.email_address_visibility_values.admins_only.code;
            page_params.is_admin = false;
            result = config.matcher.call(fake_context_for_email, bob);
            assert.ok(!result);

            page_params.is_admin = true;
            result = config.matcher.call(fake_context_for_email, bob);
            assert.ok(result);
        })();

        (function test_sorter() {
            let sort_recipients_typeahead_called = false;
            typeahead_helper.sort_recipients = function () {
                sort_recipients_typeahead_called = true;
            };
            config.sorter.call(fake_context, []);
            assert.ok(sort_recipients_typeahead_called);
        })();

        (function test_updater() {
            input_field_stub.text("@ali");
            user_groups.get_user_group_from_id = () => realm_user_group;

            let saved_fade_out_called = false;
            let cancel_fade_to_called = false;
            let instructions_fade_to_called = false;
            $(saved_selector).fadeOut = () => {
                saved_fade_out_called = true;
            };
            $(cancel_selector).css = (data) => {
                if (typeof data === "string") {
                    assert.equal(data, "display");
                }
                assert.equal(typeof data, "object");
                assert.equal(data.display, "inline-block");
                assert.equal(data.opacity, "0");
                return $(cancel_selector);
            };
            $(cancel_selector).fadeTo = () => {
                cancel_fade_to_called = true;
            };
            $(instructions_selector).css = (data) => {
                if (typeof data === "string") {
                    assert.equal(data, "display");
                }
                assert.equal(typeof data, "object");
                assert.equal(data.display, "block");
                assert.equal(data.opacity, "0");
                return $(instructions_selector);
            };
            $(instructions_selector).fadeTo = () => {
                instructions_fade_to_called = true;
            };

            text_cleared = false;
            config.updater(alice);
            // update_cancel_button is called.
            assert.ok(saved_fade_out_called);
            assert.ok(cancel_fade_to_called);
            assert.ok(instructions_fade_to_called);
            assert.equal(text_cleared, true);
        })();
        input_typeahead_called = true;
    };

    let get_by_email_called = false;
    people.get_by_email = (user_email) => {
        get_by_email_called = true;
        if (user_email === iago.email) {
            return iago;
        }
        if (user_email === bob.email) {
            return bob;
        }
        throw new Error("Expected user email to be of Alice or Iago here.");
    };
    pills.onPillCreate = (handler) => {
        assert.equal(typeof handler, "function");
        handler();
    };

    function test_create_item(handler) {
        (function test_rejection_path() {
            const item = handler(iago.email, pills.items());
            assert.ok(get_by_email_called);
            assert.equal(item, undefined);
        })();

        (function test_success_path() {
            get_by_email_called = false;
            const res = handler(bob.email, pills.items());
            assert.ok(get_by_email_called);
            assert.equal(typeof res, "object");
            assert.equal(res.user_id, bob.user_id);
            assert.equal(res.display_value, bob.full_name);
        })();

        (function test_deactivated_pill() {
            people.deactivate(bob);
            get_by_email_called = false;
            const res = handler(bob.email, pills.items());
            assert.ok(get_by_email_called);
            assert.equal(typeof res, "object");
            assert.equal(res.user_id, bob.user_id);
            assert.equal(res.display_value, bob.full_name + " (deactivated)");
            assert.ok(res.deactivated);
            people.add_active_user(bob);
        })();
    }

    pills.onPillRemove = (handler) => {
        set_global("setTimeout", (func) => {
            func();
        });
        realm_user_group.members = new Set([2, 31]);
        handler();
    };

    reset_test_setup(pill_container_stub);
    settings_user_groups.set_up();
    assert.ok(templates_render_called);
    assert.ok(user_groups_list_append_called);
    assert.ok(get_by_user_id_called);
    assert.ok(input_typeahead_called);
    test_create_item(create_item_handler);

    // Tests for settings_user_groups.set_up workflow.
    assert.equal(
        typeof $(".organization form.admin-user-group-form").get_on_handler("submit"),
        "function",
    );
    assert.equal(typeof $("#user-groups").get_on_handler("click", ".delete"), "function");
    assert.equal(
        typeof $("#user-groups").get_on_handler("keypress", ".user-group h4 > span"),
        "function",
    );
});
test_ui("with_external_user", ({override_rewire, mock_template}) => {
    const realm_user_group = {
        id: 1,
        name: "Mobile",
        description: "All mobile people",
        members: new Set([2, 4]),
    };

    user_groups.get_realm_user_groups = () => [realm_user_group];

    // We return noop because these are already tested, so we skip them
    people.get_realm_users = () => noop;

    mock_template(
        "settings/admin_user_group_list.hbs",
        false,
        () => "settings/admin_user_group_list.hbs",
    );

    people.get_by_user_id = () => noop;

    override_rewire(user_pill, "append_person", () => noop);

    let can_edit_called = 0;
    override_rewire(settings_user_groups, "can_edit", () => {
        can_edit_called += 1;
        return false;
    });

    // Reset zjquery to test stuff with user who cannot edit
    $.clear_all_elements();

    let user_group_find_called = 0;
    const user_group_stub = $(`div.user-group[id="${CSS.escape(1)}"]`);
    const name_field_stub = $.create("fake-name-field");
    const description_field_stub = $.create("fake-description-field");
    const input_stub = $.create("fake-input");
    user_group_stub.find = (elem) => {
        if (elem === ".name") {
            user_group_find_called += 1;
            return name_field_stub;
        }
        if (elem === ".description") {
            user_group_find_called += 1;
            return description_field_stub;
        }
        throw new Error(`Unknown element ${elem}`);
    };

    const pill_container_stub = $(`.pill-container[data-group-pills="${CSS.escape(1)}"]`);
    const pill_stub = $.create("fake-pill");
    let pill_container_find_called = 0;
    pill_container_stub.find = (elem) => {
        if (elem === ".input") {
            pill_container_find_called += 1;
            return input_stub;
        }
        if (elem === ".pill") {
            pill_container_find_called += 1;
            return pill_stub;
        }
        throw new Error(`Unknown element ${elem}`);
    };

    input_stub.css = (property, val) => {
        assert.equal(property, "display");
        assert.equal(val, "none");
    };

    // Test the 'off' handlers on the pill-container
    const turned_off = {};
    pill_container_stub.off = (event_name, sel = "whole") => {
        turned_off[event_name + "/" + sel] = true;
    };

    const exit_button = $.create("fake-pill-exit");
    pill_stub.set_find_results(".exit", exit_button);
    let exit_button_called = false;
    exit_button.css = (property, value) => {
        exit_button_called = true;
        assert.equal(property, "opacity");
        assert.equal(value, "0.5");
    };

    // We return noop because these are already tested, so we skip them
    pill_container_stub.children = () => noop;

    $("#user-groups").append = () => noop;

    reset_test_setup(pill_container_stub);

    settings_user_groups.set_up();

    let set_parents_result_called = 0;
    let set_attributes_called = 0;

    // Test different handlers with an external user
    const delete_handler = $("#user-groups").get_on_handler("click", ".delete");
    const fake_delete = $.create("fk-#user-groups.delete_btn");
    fake_delete.set_parents_result(".user-group", $(".user-group"));
    set_parents_result_called += 1;
    $(".user-group").attr("id", "1");
    set_attributes_called += 1;

    const name_update_handler = $(user_group_selector).get_on_handler("input", ".name");

    const des_update_handler = $(user_group_selector).get_on_handler("input", ".description");

    const member_change_handler = $(user_group_selector).get_on_handler("blur", ".input");

    const name_change_handler = $(user_group_selector).get_on_handler("blur", ".name");

    const des_change_handler = $(user_group_selector).get_on_handler("blur", ".description");

    const event = {
        stopPropagation: noop,
    };
    const pill_mouseenter_handler = pill_stub.get_on_handler("mouseenter");
    const pill_click_handler = pill_container_stub.get_on_handler("click");
    pill_mouseenter_handler(event);
    pill_click_handler(event);
    assert.equal(delete_handler.call(fake_delete), undefined);
    assert.equal(name_update_handler(), undefined);
    assert.equal(des_update_handler(), undefined);
    assert.equal(member_change_handler(), undefined);
    assert.equal(name_change_handler(), undefined);
    assert.equal(des_change_handler(), undefined);
    assert.equal(set_parents_result_called, 1);
    assert.equal(set_attributes_called, 1);
    assert.equal(can_edit_called, 9);
    assert.ok(exit_button_called);
    assert.equal(user_group_find_called, 2);
    assert.equal(pill_container_find_called, 4);
    assert.equal(turned_off["keydown/.pill"], true);
    assert.equal(turned_off["keydown/.input"], true);
    assert.equal(turned_off["click/whole"], true);
});

test_ui("reload", ({override_rewire}) => {
    $("#user-groups").html("Some text");
    let populate_user_groups_called = false;
    override_rewire(settings_user_groups, "populate_user_groups", () => {
        populate_user_groups_called = true;
    });
    settings_user_groups.reload();
    assert.ok(populate_user_groups_called);
    assert.equal($("#user-groups").html(), "");
});

test_ui("reset", () => {
    settings_user_groups.reset();
    const result = settings_user_groups.reload();
    assert.equal(result, undefined);
});

test_ui("on_events", ({override_rewire, mock_template}) => {
    mock_template("confirm_dialog/confirm_delete_user.hbs", false, (data) => {
        assert.deepEqual(data, {
            group_name: "Mobile",
        });
        return "stub";
    });

    override_rewire(settings_user_groups, "can_edit", () => true);

    (function test_admin_user_group_form_submit_triggered() {
        const handler = $(".organization form.admin-user-group-form").get_on_handler("submit");
        const event = {
            stopPropagation: noop,
            preventDefault: noop,
        };
        const fake_this = $.create("fake-form.admin-user-group-form");
        const fake_object_array = [
            {
                name: "fake-name",
                value: "",
            },
            {
                name: "fake-name",
                value: "fake-value",
            },
        ];
        fake_this.serializeArray = () => fake_object_array;
        channel.post = (opts) => {
            const data = {
                members: "[null]",
            };
            data[fake_object_array[1].name] = fake_object_array[1].value;
            assert.equal(opts.url, "/json/user_groups/create");
            assert.deepEqual(opts.data, data);

            (function test_post_success() {
                $("#admin-user-group-status").show();
                $("form.admin-user-group-form input[type='text']").val("fake-content");
                ui_report.success = (text, ele) => {
                    assert.equal(text, "translated HTML: User group added!");
                    assert.equal(ele, $("#admin-user-group-status"));
                };

                opts.success();

                assert.ok(!$("#admin-user-group-status").visible());
                assert.equal($("form.admin-user-group-form input[type='text']").val(), "");
            })();

            (function test_post_error() {
                $("#admin-user-group-status").show();
                ui_report.error = (error_msg, error_obj, ele) => {
                    const xhr = {
                        responseText: '{"msg":"fake-msg"}',
                    };
                    assert.equal(error_msg, "translated HTML: Failed");
                    assert.deepEqual(error_obj, xhr);
                    assert.equal(ele, $("#admin-user-group-status"));
                };
                const xhr = {
                    responseText: '{"msg":"fake-msg", "attrib":"val"}',
                };
                opts.error(xhr);

                assert.ok(!$("#admin-user-group-status").visible());
            })();
        };

        handler.call(fake_this, event);
    })();

    (function test_user_groups_delete_click_triggered() {
        const handler = $("#user-groups").get_on_handler("click", ".delete");
        const fake_this = $.create("fake-#user-groups.delete_btn");
        fake_this.set_parents_result(".user-group", $(".user-group"));
        $(".user-group").attr("id", "1");

        channel.del = (opts) => {
            const data = {
                id: 1,
            };
            assert.equal(opts.url, "/json/user_groups/1");
            assert.deepEqual(opts.data, data);

            fake_this.text($t({defaultMessage: "fake-text"}));
            opts.error();
            assert.equal(fake_this.text(), "translated: Failed!");
        };

        confirm_dialog.launch = (conf) => {
            conf.on_click();
        };

        handler.call(fake_this);
    })();

    (function test_user_groups_keypress_enter_triggered() {
        const handler = $("#user-groups").get_on_handler("keypress", ".user-group h4 > span");
        let default_action_for_enter_stopped = false;
        const event = {
            key: "Enter",
            preventDefault() {
                default_action_for_enter_stopped = true;
            },
        };
        handler(event);
        assert.ok(default_action_for_enter_stopped);
    })();

    (function test_do_not_blur() {
        const blur_event_classes = [".name", ".description", ".input"];
        let api_endpoint_called = false;
        channel.post = () => {
            api_endpoint_called = true;
        };
        channel.patch = noop;
        const fake_this = $.create("fake-#user-groups_do_not_blur");
        const event = {
            relatedTarget: fake_this,
        };

        // Any of the blur_exceptions trigger blur event.
        for (const class_name of blur_event_classes) {
            const handler = $(user_group_selector).get_on_handler("blur", class_name);
            const blur_exceptions = _.without(
                [".pill-container", ".name", ".description", ".input", ".delete"],
                class_name,
            );

            for (const blur_exception of blur_exceptions) {
                api_endpoint_called = false;
                fake_this.closest = (class_name) => {
                    if (class_name === blur_exception || class_name === user_group_selector) {
                        return [1];
                    }
                    return [];
                };
                handler.call(fake_this, event);
                assert.ok(!api_endpoint_called);
            }

            api_endpoint_called = false;
            fake_this.closest = (class_name) => {
                if (class_name === ".typeahead") {
                    return [1];
                }
                return [];
            };
            handler.call(fake_this, event);
            assert.ok(!api_endpoint_called);

            // Cancel button triggers blur event.
            let settings_user_groups_reload_called = false;
            override_rewire(settings_user_groups, "reload", () => {
                settings_user_groups_reload_called = true;
            });
            api_endpoint_called = false;
            fake_this.closest = (class_name) => {
                if (
                    class_name === ".save-status.btn-danger" ||
                    class_name === user_group_selector
                ) {
                    return [1];
                }
                return [];
            };
            handler.call(fake_this, event);
            assert.ok(!api_endpoint_called);
            assert.ok(settings_user_groups_reload_called);
        }
    })();

    (function test_update_cancel_button() {
        const handler_name = $(user_group_selector).get_on_handler("input", ".name");
        const handler_desc = $(user_group_selector).get_on_handler("input", ".description");
        const sib_des = $(description_selector);
        const sib_name = $(name_selector);
        sib_name.text($t({defaultMessage: "mobile"}));
        sib_des.text($t({defaultMessage: "All mobile members"}));

        const group_data = {
            name: "translated: mobile",
            description: "translated: All mobile members",
            members: new Set([2, 31]),
        };
        user_groups.get_user_group_from_id = () => group_data;

        let cancel_fade_out_called = false;
        let instructions_fade_out_called = false;
        $(cancel_selector).show();
        $(cancel_selector).fadeOut = () => {
            cancel_fade_out_called = true;
        };
        $(instructions_selector).fadeOut = () => {
            instructions_fade_out_called = true;
        };

        // Cancel button removed if user group if user group has no changes.
        const fake_this = $.create("fake-#update_cancel_button");
        handler_name.call(fake_this);
        assert.ok(cancel_fade_out_called);
        assert.ok(instructions_fade_out_called);

        // Check if cancel button removed if user group error is showing.
        $(user_group_selector + " .user-group-status").show();
        cancel_fade_out_called = false;
        instructions_fade_out_called = false;
        handler_name.call(fake_this);
        assert.ok(cancel_fade_out_called);
        assert.ok(instructions_fade_out_called);

        // Check for handler_desc to achieve 100% coverage.
        cancel_fade_out_called = false;
        instructions_fade_out_called = false;
        handler_desc.call(fake_this);
        assert.ok(cancel_fade_out_called);
        assert.ok(instructions_fade_out_called);
    })();

    (function test_user_groups_save_group_changes_triggered() {
        const handler_name = $(user_group_selector).get_on_handler("blur", ".name");
        const handler_desc = $(user_group_selector).get_on_handler("blur", ".description");
        const sib_des = $(description_selector);
        const sib_name = $(name_selector);
        sib_name.text($t({defaultMessage: "mobile"}));
        sib_des.text($t({defaultMessage: "All mobile members"}));

        const group_data = {members: new Set([2, 31])};
        user_groups.get_user_group_from_id = () => group_data;
        let api_endpoint_called = false;
        let cancel_fade_out_called = false;
        let saved_fade_to_called = false;
        let instructions_fade_out_called = false;
        $(instructions_selector).fadeOut = () => {
            instructions_fade_out_called = true;
        };
        $(cancel_selector).fadeOut = () => {
            cancel_fade_out_called = true;
        };
        $(saved_selector).css = (data) => {
            if (typeof data === "string") {
                assert.equal(data, "display");
            }
            assert.equal(typeof data, "object");
            assert.equal(data.display, "inline-block");
            assert.equal(data.opacity, "0");
            return $(saved_selector);
        };
        $(saved_selector).fadeTo = () => {
            saved_fade_to_called = true;
            return $(saved_selector);
        };

        channel.patch = (opts) => {
            assert.equal(opts.url, "/json/user_groups/1");
            assert.equal(opts.data.name, "translated: mobile");
            assert.equal(opts.data.description, "translated: All mobile members");
            api_endpoint_called = true;
            (function test_post_success() {
                set_global("setTimeout", (func) => {
                    func();
                });
                opts.success();
                assert.ok(cancel_fade_out_called);
                assert.ok(instructions_fade_out_called);
                assert.ok(saved_fade_to_called);
            })();
            (function test_post_error() {
                const user_group_error = $(user_group_selector + " .user-group-status");
                user_group_error.show();
                ui_report.error = (error_msg, error_obj, ele) => {
                    const xhr = {
                        responseText: '{"msg":"fake-msg"}',
                    };
                    assert.equal(error_msg, "translated HTML: Failed");
                    assert.deepEqual(error_obj, xhr);
                    assert.equal(ele, user_group_error);
                };
                const xhr = {
                    responseText: '{"msg":"fake-msg", "attrib":"val"}',
                };
                opts.error(xhr);

                assert.ok(user_group_error.visible());
            })();
        };

        const fake_this = $.create("fake-#user-groups_blur_name");
        fake_this.closest = () => [];
        fake_this.set_parents_result(user_group_selector, $(user_group_selector));
        const event = {
            relatedTarget: fake_this,
        };

        api_endpoint_called = false;
        handler_name.call(fake_this, event);
        assert.ok(api_endpoint_called);

        // Check API endpoint isn't called if name and desc haven't changed.
        group_data.name = "translated: mobile";
        group_data.description = "translated: All mobile members";
        api_endpoint_called = false;
        handler_name.call(fake_this, event);
        assert.ok(!api_endpoint_called);

        // Check for handler_desc to achieve 100% coverage.
        api_endpoint_called = false;
        handler_desc.call(fake_this, event);
        assert.ok(!api_endpoint_called);
    })();

    (function test_user_groups_save_member_changes_triggered() {
        const handler = $(user_group_selector).get_on_handler("blur", ".input");
        const realm_user_group = {
            id: 1,
            name: "Mobile",
            description: "All mobile people",
            members: new Set([2, 4]),
        };

        user_groups.get_user_group_from_id = (id) => {
            assert.equal(id, 1);
            return realm_user_group;
        };

        let cancel_fade_out_called = false;
        let saved_fade_to_called = false;
        let instructions_fade_out_called = false;
        $(instructions_selector).fadeOut = () => {
            instructions_fade_out_called = true;
        };
        $(cancel_selector).fadeOut = () => {
            cancel_fade_out_called = true;
        };
        $(saved_selector).css = () => $(saved_selector);
        $(saved_selector).fadeTo = () => {
            saved_fade_to_called = true;
            return $(saved_selector);
        };

        let api_endpoint_called = false;
        channel.post = (opts) => {
            assert.equal(opts.url, "/json/user_groups/1/members");
            assert.equal(opts.data.add, "[31]");
            assert.equal(opts.data.delete, "[4]");
            api_endpoint_called = true;

            (function test_post_success() {
                opts.success();
                assert.ok(cancel_fade_out_called);
                assert.ok(instructions_fade_out_called);
                assert.ok(saved_fade_to_called);
            })();
        };

        const fake_this = $.create("fake-#user-groups_blur_input");
        fake_this.set_parents_result(user_group_selector, $(user_group_selector));
        fake_this.closest = () => [];
        const event = {
            relatedTarget: fake_this,
        };

        api_endpoint_called = false;
        handler.call(fake_this, event);
        assert.ok(api_endpoint_called);
    })();
});
