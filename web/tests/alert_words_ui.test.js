"use strict";

const {strict: assert} = require("assert");

const {$t} = require("./lib/i18n");
const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test, noop} = require("./lib/test");
const $ = require("./lib/zjquery");

const channel = mock_esm("../src/channel");

const alert_words = zrequire("alert_words");
const alert_words_ui = zrequire("alert_words_ui");

alert_words.initialize({
    watched_phrases: [{watched_phrase: "foo"}, {watched_phrase: "bar"}],
});

run_test("rerender_watched_phrases_ui", ({mock_template}) => {
    let list_widget_create_called = false;
    alert_words_ui.reset();
    const ListWidget = mock_esm("../src/list_widget", {
        modifier_html: noop,
        create(_container, phrases, opts) {
            const watched_phrases = [];
            ListWidget.modifier_html = opts.modifier_html;
            for (const phrase of phrases) {
                watched_phrases.push(opts.modifier_html(phrase));
            }
            list_widget_create_called = true;
            return watched_phrases;
        },
        generic_sort_functions: noop,
    });
    mock_template("settings/alert_word_settings_item.hbs", false, (args) => {
        assert.ok(["foo", "bar"].includes(args.watched_phrase.watched_phrase));
    });
    assert.equal(alert_words_ui.loaded, false);
    alert_words_ui.rerender_watched_phrases_ui();
    assert.equal(list_widget_create_called, false);
    alert_words_ui.set_up_watched_phrases();
    assert.equal(alert_words_ui.loaded, true);
    assert.equal(list_widget_create_called, true);
});

run_test("remove_watched_phrase", ({override_rewire}) => {
    override_rewire(alert_words_ui, "rerender_watched_phrases_ui", noop);
    alert_words_ui.set_up_watched_phrases();

    const $word_list = $("#watched-phrases-table");
    const remove_func = $word_list.get_on_handler("click", ".remove-watched-phrase");

    const $remove_watched_phrase = $(".remove-watched-phrase");
    const $list_item = $("tr.watched-phrase-item");
    const $val_item = $("span.value");
    $val_item.text($t({defaultMessage: "zot"}));

    $remove_watched_phrase.set_parents_result("tr", $list_item);
    $list_item.set_find_results(".value", $val_item);

    const event = {
        currentTarget: ".remove-watched-phrase",
    };

    let success_func;
    let fail_func;
    channel.del = (opts) => {
        assert.equal(opts.url, "/json/users/me/watched_phrases");
        assert.deepEqual(opts.data, {watched_phrases: '["translated: zot"]'});
        success_func = opts.success;
        fail_func = opts.error;
    };

    remove_func(event);

    const $watched_phrase_status = $("#watched_phrase_status");
    const $watched_phrase_status_text = $(".watched_phrase_status_text");
    $watched_phrase_status.set_find_results(
        ".watched_phrase_status_text",
        $watched_phrase_status_text,
    );

    // test failure
    fail_func();
    assert.ok($watched_phrase_status.hasClass("alert-danger"));
    assert.equal($watched_phrase_status_text.text(), "translated: Error removing watched phrase!");
    assert.ok($watched_phrase_status.visible());

    // test success
    success_func();
    assert.ok($watched_phrase_status.hasClass("alert-success"));
    assert.equal(
        $watched_phrase_status_text.text(),
        `translated: Watched phrase "translated: zot" removed successfully!`,
    );
    assert.ok($watched_phrase_status.visible());
});

run_test("close_status_message", ({override_rewire}) => {
    override_rewire(alert_words_ui, "rerender_watched_phrases_ui", noop);
    alert_words_ui.set_up_watched_phrases();

    const $watched_phrase_settings = $("#watched-phrase-settings");
    const close = $watched_phrase_settings.get_on_handler("click", ".close-watched-phrase-status");

    const $alert = $(".alert");
    const $close_btn = $(".close-watched-phrase-status");
    $close_btn.set_parents_result(".alert", $alert);

    $alert.show();

    const event = {
        preventDefault() {},
        currentTarget: ".close-watched-phrase-status",
    };

    assert.ok($alert.visible());
    close(event);
    assert.ok(!$alert.visible());
});
