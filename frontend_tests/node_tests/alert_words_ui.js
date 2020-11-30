"use strict";

const {strict: assert} = require("assert");

const {stub_templates} = require("../zjsunit/handlebars");
const {set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const {make_zjquery} = require("../zjsunit/zjquery");

set_global("$", make_zjquery());

set_global("channel", {});

zrequire("alert_words");
zrequire("alert_words_ui");

alert_words.initialize({
    alert_words: ["foo", "bar"],
});

run_test("render_alert_words_ui", () => {
    const word_list = $("#alert_words_list");
    const appended = [];
    word_list.append = (rendered) => {
        appended.push(rendered);
    };

    const alert_word_items = $.create("alert_word_items");
    word_list.set_find_results(".alert-word-item", alert_word_items);

    stub_templates((name, args) => {
        assert.equal(name, "settings/alert_word_settings_item");
        return "stub-" + args.word;
    });

    const new_alert_word = $("#create_alert_word_name");
    assert(!new_alert_word.is_focused());

    alert_words_ui.render_alert_words_ui();

    assert.deepEqual(appended, ["stub-bar", "stub-foo"]);
    assert(new_alert_word.is_focused());
});

run_test("add_alert_word", () => {
    alert_words_ui.render_alert_words_ui = () => {}; // we've already tested this above

    alert_words_ui.set_up_alert_words();

    const create_form = $("#create_alert_word_form");
    const add_func = create_form.get_on_handler("click", "#create_alert_word_button");

    const new_alert_word = $("#create_alert_word_name");
    const alert_word_status = $("#alert_word_status");
    const alert_word_status_text = $(".alert_word_status_text");
    alert_word_status.set_find_results(".alert_word_status_text", alert_word_status_text);

    // add '' as alert word
    add_func();
    assert.equal(new_alert_word.val(), "");
    assert(alert_word_status.hasClass("alert-danger"));
    assert.equal(alert_word_status_text.text(), "translated: Alert word can't be empty!");
    assert(alert_word_status.visible());

    // add 'foo' as alert word (existing word)
    new_alert_word.val("foo");

    add_func();
    assert(alert_word_status.hasClass("alert-danger"));
    assert.equal(alert_word_status_text.text(), "translated: Alert word already exists!");
    assert(alert_word_status.visible());

    // add 'zot' as alert word (new word)
    new_alert_word.val("zot");

    let success_func;
    let fail_func;
    channel.post = (opts) => {
        assert.equal(opts.url, "/json/users/me/alert_words");
        assert.deepEqual(opts.data, {alert_words: '["zot"]'});
        success_func = opts.success;
        fail_func = opts.error;
    };

    add_func();

    // test failure
    fail_func();
    assert(alert_word_status.hasClass("alert-danger"));
    assert.equal(alert_word_status_text.text(), "translated: Error adding alert word!");
    assert(alert_word_status.visible());

    // test success
    success_func();
    assert(alert_word_status.hasClass("alert-success"));
    assert.equal(alert_word_status_text.text(), 'translated: Alert word "zot" added successfully!');
    assert(alert_word_status.visible());
});

run_test("add_alert_word_keypress", () => {
    const create_form = $("#create_alert_word_form");
    const keypress_func = create_form.get_on_handler("keypress", "#create_alert_word_name");

    const new_alert_word = $("#create_alert_word_name");
    new_alert_word.val("zot");

    const event = {
        preventDefault: () => {},
        which: 13,
        target: "#create_alert_word_name",
    };

    let called = false;
    channel.post = (opts) => {
        assert.deepEqual(opts.data, {alert_words: '["zot"]'});
        called = true;
    };

    keypress_func(event);
    assert(called);
});

run_test("remove_alert_word", () => {
    const word_list = $("#alert_words_list");
    const remove_func = word_list.get_on_handler("click", ".remove-alert-word");

    const remove_alert_word = $(".remove-alert-word");
    const list_item = $("li.alert-word-item");
    const val_item = $("span.value");
    val_item.text(i18n.t("zot"));

    remove_alert_word.set_parents_result("li", list_item);
    list_item.set_find_results(".value", val_item);

    const event = {
        currentTarget: ".remove-alert-word",
    };

    let success_func;
    let fail_func;
    channel.del = (opts) => {
        assert.equal(opts.url, "/json/users/me/alert_words");
        assert.deepEqual(opts.data, {alert_words: '["translated: zot"]'});
        success_func = opts.success;
        fail_func = opts.error;
    };

    remove_func(event);

    const alert_word_status = $("#alert_word_status");
    const alert_word_status_text = $(".alert_word_status_text");
    alert_word_status.set_find_results(".alert_word_status_text", alert_word_status_text);

    // test failure
    fail_func();
    assert(alert_word_status.hasClass("alert-danger"));
    assert.equal(alert_word_status_text.text(), "translated: Error removing alert word!");
    assert(alert_word_status.visible());

    // test success
    success_func();
    assert(alert_word_status.hasClass("alert-success"));
    assert.equal(alert_word_status_text.text(), "translated: Alert word removed successfully!");
    assert(alert_word_status.visible());
});

run_test("close_status_message", () => {
    const alert_word_settings = $("#alert-word-settings");
    const close = alert_word_settings.get_on_handler("click", ".close-alert-word-status");

    const alert = $(".alert");
    const close_btn = $(".close-alert-word-status");
    close_btn.set_parents_result(".alert", alert);

    alert.show();

    const event = {
        preventDefault: () => {},
        currentTarget: ".close-alert-word-status",
    };

    assert(alert.visible());
    close(event);
    assert(!alert.visible());
});
