"use strict";

const {strict: assert} = require("assert");

const {$t} = require("../zjsunit/i18n");
const {mock_esm, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

const channel = mock_esm("../../static/js/channel");

const alert_words = zrequire("alert_words");
const alert_words_ui = zrequire("alert_words_ui");

alert_words.initialize({
    alert_words: ["foo", "bar"],
});
const noop = () => {};

run_test("rerender_alert_words_ui", ({mock_template}) => {
    let list_widget_create_called = false;
    alert_words_ui.reset();
    assert.ok(!$("#create_alert_word_name").is_focused());
    const ListWidget = mock_esm("../../static/js/list_widget", {
        modifier: noop,
        create: (container, words, opts) => {
            const alert_words = [];
            ListWidget.modifier = opts.modifier;
            for (const word of words) {
                alert_words.push(opts.modifier(word));
            }
            list_widget_create_called = true;
            return alert_words;
        },
    });
    mock_template("settings/alert_word_settings_item.hbs", false, (args) => {
        assert.ok(["foo", "bar"].includes(args.alert_word.word));
    });
    assert.equal(alert_words_ui.loaded, false);
    alert_words_ui.rerender_alert_words_ui();
    assert.equal(list_widget_create_called, false);
    alert_words_ui.set_up_alert_words();
    assert.equal(alert_words_ui.loaded, true);
    assert.equal(list_widget_create_called, true);
    assert.ok($("#create_alert_word_name").is_focused());
});

run_test("add_alert_word", ({override_rewire}) => {
    override_rewire(alert_words_ui, "rerender_alert_words_ui", () => {}); // we've already tested this above

    alert_words_ui.set_up_alert_words();

    const $create_form = $("#create_alert_word_form");
    const add_func = $create_form.get_on_handler("click", "#create_alert_word_button");

    const $new_alert_word = $("#create_alert_word_name");
    const $alert_word_status = $("#alert_word_status");
    const $alert_word_status_text = $(".alert_word_status_text");
    $alert_word_status.set_find_results(".alert_word_status_text", $alert_word_status_text);

    // add '' as alert word
    add_func();
    assert.equal($new_alert_word.val(), "");
    assert.ok($alert_word_status.hasClass("alert-danger"));
    assert.equal($alert_word_status_text.text(), "translated: Alert word can't be empty!");
    assert.ok($alert_word_status.visible());

    // add 'foo' as alert word (existing word)
    $new_alert_word.val("foo");

    add_func();
    assert.ok($alert_word_status.hasClass("alert-danger"));
    assert.equal($alert_word_status_text.text(), "translated: Alert word already exists!");
    assert.ok($alert_word_status.visible());

    // add 'zot' as alert word (new word)
    $new_alert_word.val("zot");

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
    assert.ok($alert_word_status.hasClass("alert-danger"));
    assert.equal($alert_word_status_text.text(), "translated: Error adding alert word!");
    assert.ok($alert_word_status.visible());

    // test success
    success_func();
    assert.ok($alert_word_status.hasClass("alert-success"));
    assert.equal(
        $alert_word_status_text.text(),
        'translated: Alert word "zot" added successfully!',
    );
    assert.ok($alert_word_status.visible());
});

run_test("add_alert_word_keypress", ({override_rewire}) => {
    override_rewire(alert_words_ui, "rerender_alert_words_ui", () => {});
    alert_words_ui.set_up_alert_words();

    const $create_form = $("#create_alert_word_form");
    const keypress_func = $create_form.get_on_handler("keypress", "#create_alert_word_name");

    const $new_alert_word = $("#create_alert_word_name");
    $new_alert_word.val("zot");

    const event = {
        preventDefault: () => {},
        key: "Enter",
        target: "#create_alert_word_name",
    };

    let called = false;
    channel.post = (opts) => {
        assert.deepEqual(opts.data, {alert_words: '["zot"]'});
        called = true;
    };

    keypress_func(event);
    assert.ok(called);
});

run_test("remove_alert_word", ({override_rewire}) => {
    override_rewire(alert_words_ui, "rerender_alert_words_ui", () => {});
    alert_words_ui.set_up_alert_words();

    const $word_list = $("#alert-words-table");
    const remove_func = $word_list.get_on_handler("click", ".remove-alert-word");

    const $remove_alert_word = $(".remove-alert-word");
    const $list_item = $("tr.alert-word-item");
    const $val_item = $("span.value");
    $val_item.text($t({defaultMessage: "zot"}));

    $remove_alert_word.set_parents_result("tr", $list_item);
    $list_item.set_find_results(".value", $val_item);

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

    const $alert_word_status = $("#alert_word_status");
    const $alert_word_status_text = $(".alert_word_status_text");
    $alert_word_status.set_find_results(".alert_word_status_text", $alert_word_status_text);

    // test failure
    fail_func();
    assert.ok($alert_word_status.hasClass("alert-danger"));
    assert.equal($alert_word_status_text.text(), "translated: Error removing alert word!");
    assert.ok($alert_word_status.visible());

    // test success
    success_func();
    assert.ok($alert_word_status.hasClass("alert-success"));
    assert.equal($alert_word_status_text.text(), "translated: Alert word removed successfully!");
    assert.ok($alert_word_status.visible());
});

run_test("close_status_message", ({override_rewire}) => {
    override_rewire(alert_words_ui, "rerender_alert_words_ui", () => {});
    alert_words_ui.set_up_alert_words();

    const $alert_word_settings = $("#alert-word-settings");
    const close = $alert_word_settings.get_on_handler("click", ".close-alert-word-status");

    const $alert = $(".alert");
    const $close_btn = $(".close-alert-word-status");
    $close_btn.set_parents_result(".alert", $alert);

    $alert.show();

    const event = {
        preventDefault: () => {},
        currentTarget: ".close-alert-word-status",
    };

    assert.ok($alert.visible());
    close(event);
    assert.ok(!$alert.visible());
});
