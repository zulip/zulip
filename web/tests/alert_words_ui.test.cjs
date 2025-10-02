"use strict";

const assert = require("node:assert/strict");

const {$t} = require("./lib/i18n.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const channel = mock_esm("../src/channel");

const alert_words = zrequire("alert_words");
const alert_words_ui = zrequire("alert_words_ui");
const banners = mock_esm("../src/banners");

alert_words.initialize({
    alert_words: ["foo", "bar"],
});

run_test("rerender_alert_words_ui", ({mock_template}) => {
    let list_widget_create_called = false;
    alert_words_ui.reset();

    mock_esm("../src/list_widget", {
        create(_container, words, opts) {
            assert.deepEqual(words, [{word: "foo"}, {word: "bar"}]);
            for (const word of words) {
                opts.modifier_html(word);
            }
            list_widget_create_called = true;
        },
        generic_sort_functions: noop,
    });

    mock_template("settings/alert_word_settings_item.hbs", true, (args, html) => {
        assert.ok(["foo", "bar"].includes(args.alert_word.word));
        // do a super easy sanity check
        assert.ok(html.includes("alert_word_listing"));
    });

    assert.equal(alert_words_ui.loaded, false);
    assert.equal(list_widget_create_called, false);

    // Invoke list_widget.create indirectly via these calls.
    alert_words_ui.rerender_alert_words_ui();
    alert_words_ui.set_up_alert_words();

    assert.equal(alert_words_ui.loaded, true);
    assert.equal(list_widget_create_called, true);
});

run_test("remove_alert_word", ({override_rewire}) => {
    override_rewire(alert_words_ui, "rerender_alert_words_ui", noop);
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

    const $alert_word_status_banner = $(".alert-word-status-banner");
    const $alert_word_status_banner_label = $(".alert-word-status-banner .banner-label");
    banners.open = (banner, _container) => {
        $alert_word_status_banner.addClass(`banner-${banner.intent}`);
        $alert_word_status_banner_label.text(banner.label);
    };

    // test failure
    fail_func();
    assert.ok($alert_word_status_banner.hasClass("banner-danger"));
    assert.equal(
        $alert_word_status_banner_label.text(),
        `translated HTML: Error removing alert word <b>translated: zot</b>!`,
    );

    // test success
    success_func();
    assert.ok($alert_word_status_banner.hasClass("banner-success"));
    assert.equal(
        $alert_word_status_banner_label.text(),
        `translated HTML: Alert word <b>translated: zot</b> removed successfully!`,
    );
});
