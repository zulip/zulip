"use strict";

const assert = require("node:assert/strict");

const {$t} = require("./lib/i18n.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const channel = mock_esm("../src/channel");
const settings_ui = mock_esm("../src/settings_ui");

const alert_words = zrequire("alert_words");
const alert_words_ui = zrequire("alert_words_ui");
const banners = mock_esm("../src/banners");

alert_words.initialize({
    watched_phrases: [
        {watched_phrase: "foo", automatically_follow_topics: true},
        {watched_phrase: "bar", automatically_follow_topics: false},
    ],
});

run_test("rerender_alert_words_ui", ({mock_template}) => {
    let list_widget_create_called = false;
    alert_words_ui.reset();

    mock_esm("../src/list_widget", {
        create(_container, words, opts) {
            assert.deepEqual(words, [
                {word: "bar", automatically_follow_topics: false},
                {word: "foo", automatically_follow_topics: true},
            ]);
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
        // "foo" is the only word configured to follow topics.
        assert.equal(html.includes("checked"), args.alert_word.automatically_follow_topics);
        return "<alert-word-settings-item-stub>";
    });

    assert.equal(alert_words_ui.loaded, false);
    assert.equal(list_widget_create_called, false);

    // Invoke list_widget.create indirectly via these calls.
    alert_words_ui.rerender_alert_words_ui();
    alert_words_ui.set_up_alert_words();

    assert.equal(alert_words_ui.loaded, true);
    assert.equal(list_widget_create_called, true);
});

run_test("toggle_automatically_follow_topics", () => {
    alert_words_ui.set_up_alert_words();

    const $word_list = $("#alert-words-table");
    const toggle_func = $word_list.get_on_handler("click", "input.alert-word-follow-topic");

    const $checkbox = $("input.alert-word-follow-topic");
    $checkbox.attr("data-word", "foo");
    const checkbox_element = {checked: true, to_$: () => $checkbox};

    let error_continuation;
    settings_ui.do_settings_change = (
        _request_method,
        url,
        data,
        _$status_element,
        {error_continuation: on_error},
    ) => {
        assert.equal(url, "/json/users/me/watched_phrases");
        assert.deepEqual(data, {
            watched_phrases: '[{"watched_phrase":"foo","automatically_follow_topics":true}]',
        });
        error_continuation = on_error;
    };

    toggle_func.call(checkbox_element, {});

    // A failed request reverts the checkbox, since no event will
    // arrive to re-render the table.
    error_continuation();
    assert.equal($checkbox.prop("checked"), false);
});

run_test("remove_alert_word", () => {
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
        assert.equal(opts.url, "/json/users/me/watched_phrases");
        assert.deepEqual(opts.data, {watched_phrases: '["translated: zot"]'});
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
        `translated: Error removing alert word <b>translated: zot</b>!`,
    );

    // test success
    success_func();
    assert.ok($alert_word_status_banner.hasClass("banner-success"));
    assert.equal(
        $alert_word_status_banner_label.text(),
        `translated: Alert word <b>translated: zot</b> removed successfully!`,
    );
});
