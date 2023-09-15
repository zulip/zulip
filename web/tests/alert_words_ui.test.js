"use strict";

const {strict: assert} = require("assert");

const {$t} = require("./lib/i18n");
const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");

const channel = mock_esm("../src/channel");

const alert_words = zrequire("alert_words");
const alert_words_ui = zrequire("alert_words_ui");

alert_words.initialize({
    alert_words: ["foo", "bar"],
});
const noop = () => {};

run_test("rerender_alert_words_ui", ({mock_template}) => {
    let list_widget_create_called = false;
    alert_words_ui.reset();
    const ListWidget = mock_esm("../src/list_widget", {
        modifier_html: noop,
        create(_container, words, opts) {
            const alert_words = [];
            ListWidget.modifier_html = opts.modifier_html;
            for (const word of words) {
                alert_words.push(opts.modifier_html(word));
            }
            list_widget_create_called = true;
            return alert_words;
        },
        generic_sort_functions: noop,
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
    assert.equal(
        $alert_word_status_text.text(),
        `translated: Alert word "translated: zot" removed successfully!`,
    );
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
        preventDefault() {},
        currentTarget: ".close-alert-word-status",
    };

    assert.ok($alert.visible());
    close(event);
    assert.ok(!$alert.visible());
});
