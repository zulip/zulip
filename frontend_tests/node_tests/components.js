"use strict";

const {strict: assert} = require("assert");

const _ = require("lodash");

const {set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

zrequire("keydown_util");
zrequire("components");

const noop = function () {};

const LEFT_KEY = {which: 37, preventDefault: noop, stopPropagation: noop};
const RIGHT_KEY = {which: 39, preventDefault: noop, stopPropagation: noop};

run_test("basics", () => {
    let keydown_f;
    let click_f;
    const tabs = [];
    let focused_tab;
    let callback_args;

    function make_tab(i) {
        const self = {};

        assert.equal(tabs.length, i);

        self.stub = true;
        self.class = [];

        self.addClass = function (c) {
            self.class += " " + c;
            const tokens = self.class.trim().split(/ +/);
            self.class = _.uniq(tokens).join(" ");
        };

        self.removeClass = function (c) {
            const tokens = self.class.trim().split(/ +/);
            self.class = _.without(tokens, c).join(" ");
        };

        self.hasClass = function (c) {
            const tokens = self.class.trim().split(/ +/);
            return tokens.includes(c);
        };

        self.data = function (name) {
            assert.equal(name, "tab-id");
            return i;
        };

        self.trigger = function (type) {
            if (type === "focus") {
                focused_tab = i;
            }
        };

        tabs.push(self);

        return self;
    }

    const ind_tab = (function () {
        const self = {};

        self.stub = true;

        self.on = function (name, f) {
            if (name === "click") {
                click_f = f;
            } else if (name === "keydown") {
                keydown_f = f;
            }
        };

        self.removeClass = function (c) {
            for (const tab of tabs) {
                tab.removeClass(c);
            }
        };

        self.eq = function (idx) {
            return tabs[idx];
        };

        return self;
    })();

    const switcher = (function () {
        const self = {};

        self.stub = true;

        self.children = [];

        self.classList = new Set();

        self.append = function (child) {
            self.children.push(child);
        };

        self.addClass = function (c) {
            self.classList.add(c);
            self.addedClass = c;
        };

        self.find = function (sel) {
            switch (sel) {
                case ".ind-tab":
                    return ind_tab;
                default:
                    throw new Error("unknown selector: " + sel);
            }
        };

        return self;
    })();

    set_global("$", (sel, attributes) => {
        if (sel.stub) {
            // The component often redundantly re-wraps objects.
            return sel;
        }

        switch (sel) {
            case "<div class='tab-switcher'></div>":
                return switcher;
            case "<div class='tab-switcher stream_sorter_toggle'></div>":
                return switcher;
            case "<div>": {
                const tab_id = attributes["data-tab-id"];
                assert.deepEqual(
                    attributes,
                    [
                        {
                            class: "ind-tab",
                            "data-tab-key": "keyboard-shortcuts",
                            "data-tab-id": 0,
                            tabindex: 0,
                        },
                        {
                            class: "ind-tab",
                            "data-tab-key": "message-formatting",
                            "data-tab-id": 1,
                            tabindex: 0,
                        },
                        {
                            class: "ind-tab",
                            "data-tab-key": "search-operators",
                            "data-tab-id": 2,
                            tabindex: 0,
                        },
                    ][tab_id],
                );
                return {
                    text: (text) => {
                        assert.equal(
                            text,
                            [
                                "translated: Keyboard shortcuts",
                                "translated: Message formatting",
                                "translated: Search operators",
                            ][tab_id],
                        );
                        return make_tab(tab_id);
                    },
                };
            }
            default:
                throw new Error("unknown selector: " + sel);
        }
    });

    let callback_value;

    let widget = null;
    widget = components.toggle({
        selected: 0,
        values: [
            {label: i18n.t("Keyboard shortcuts"), key: "keyboard-shortcuts"},
            {label: i18n.t("Message formatting"), key: "message-formatting"},
            {label: i18n.t("Search operators"), key: "search-operators"},
        ],
        html_class: "stream_sorter_toggle",
        callback(name, key) {
            assert.equal(callback_args, undefined);
            callback_args = [name, key];

            // The subs code tries to get a widget value in the middle of a
            // callback, which can lead to obscure bugs.
            if (widget) {
                callback_value = widget.value();
            }
        },
    });

    assert.equal(widget.get(), switcher);

    assert.deepEqual(switcher.children, tabs);

    assert.equal(switcher.addedClass, "stream_sorter_toggle");

    assert.equal(focused_tab, 0);
    assert.equal(tabs[0].class, "first selected");
    assert.equal(tabs[1].class, "middle");
    assert.equal(tabs[2].class, "last");
    assert.deepEqual(callback_args, ["translated: Keyboard shortcuts", "keyboard-shortcuts"]);
    assert.equal(widget.value(), "translated: Keyboard shortcuts");

    callback_args = undefined;

    widget.goto("message-formatting");
    assert.equal(focused_tab, 1);
    assert.equal(tabs[0].class, "first");
    assert.equal(tabs[1].class, "middle selected");
    assert.equal(tabs[2].class, "last");
    assert.deepEqual(callback_args, ["translated: Message formatting", "message-formatting"]);
    assert.equal(widget.value(), "translated: Message formatting");

    // Go to same tab twice and make sure we get callback.
    callback_args = undefined;
    widget.goto("message-formatting");
    assert.deepEqual(callback_args, ["translated: Message formatting", "message-formatting"]);

    callback_args = undefined;
    keydown_f.call(tabs[focused_tab], RIGHT_KEY);
    assert.equal(focused_tab, 2);
    assert.equal(tabs[0].class, "first");
    assert.equal(tabs[1].class, "middle");
    assert.equal(tabs[2].class, "last selected");
    assert.deepEqual(callback_args, ["translated: Search operators", "search-operators"]);
    assert.equal(widget.value(), "translated: Search operators");
    assert.equal(widget.value(), callback_value);

    // try to crash the key handler
    keydown_f.call(tabs[focused_tab], RIGHT_KEY);
    assert.equal(widget.value(), "translated: Search operators");

    callback_args = undefined;

    keydown_f.call(tabs[focused_tab], LEFT_KEY);
    assert.equal(widget.value(), "translated: Message formatting");

    callback_args = undefined;

    keydown_f.call(tabs[focused_tab], LEFT_KEY);
    assert.equal(widget.value(), "translated: Keyboard shortcuts");

    // try to crash the key handler
    keydown_f.call(tabs[focused_tab], LEFT_KEY);
    assert.equal(widget.value(), "translated: Keyboard shortcuts");

    callback_args = undefined;
    widget.disable_tab("message-formatting");

    keydown_f.call(tabs[focused_tab], RIGHT_KEY);
    assert.equal(widget.value(), "translated: Search operators");

    callback_args = undefined;

    keydown_f.call(tabs[focused_tab], LEFT_KEY);
    assert.equal(widget.value(), "translated: Keyboard shortcuts");

    widget.enable_tab("message-formatting");

    callback_args = undefined;

    click_f.call(tabs[1]);
    assert.equal(widget.value(), "translated: Message formatting");

    callback_args = undefined;
    widget.disable_tab("search-operators");
    assert.equal(tabs[2].hasClass("disabled"), true);
    assert.equal(tabs[2].class, "last disabled");

    widget.goto("keyboard-shortcuts");
    assert.equal(focused_tab, 0);
    widget.goto("search-operators");
    assert.equal(focused_tab, 0);
});
