"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const navigator = set_global("navigator", {platform: ""});

mock_esm("../src/scroll_util", {
    scroll_element_into_container() {},
});

const bootstrap_typeahead = zrequire("bootstrap_typeahead");

class FakeCollection {
    constructor(items) {
        this.items = items;
        this.length = items.length;
        for (const [index, item] of items.entries()) {
            this[index] = item;
        }
    }

    addClass(class_name) {
        for (const item of this.items) {
            item.classes.add(class_name);
        }
        return this;
    }

    removeClass(class_name) {
        for (const item of this.items) {
            item.classes.delete(class_name);
        }
        return this;
    }

    next() {
        return new FakeCollection(this.items.flatMap((item) => item.next ?? []));
    }

    prev() {
        return new FakeCollection(this.items.flatMap((item) => item.prev ?? []));
    }

    first() {
        return new FakeCollection(this.items.slice(0, 1));
    }

    last() {
        return new FakeCollection(this.items.slice(-1));
    }
}

function make_menu(names) {
    const items = names.map((name) => ({
        classes: new Set(),
        name,
        next: undefined,
        prev: undefined,
    }));

    for (const [index, item] of items.entries()) {
        item.prev = items[index - 1];
        item.next = items[index + 1];
    }

    return {
        find(selector) {
            switch (selector) {
                case ".active":
                    return new FakeCollection(items.filter((item) => item.classes.has("active")));
                case "li":
                    return new FakeCollection(items);
                /* istanbul ignore next */
                default:
                    throw new Error(`unexpected selector: ${selector}`);
            }
        },
        items,
    };
}

function make_typeahead({active_index = 0} = {}) {
    const $menu = make_menu(["first", "second", "third"]);
    $menu.items[active_index].classes.add("active");

    const typeahead = Object.create(bootstrap_typeahead.Typeahead.prototype);
    Object.assign(typeahead, {
        $menu,
        advanceKeys: [],
        lookup_count: 0,
        mouse_moved_since_typeahead: false,
        shown: true,
        stopAdvance: false,
        suppressKeyPressRepeat: false,
        suppressKeyUpAfterMacCtrlNavigation: false,
        tabIsEnter: true,
        trigger_selection: () => false,
        lookup() {
            this.lookup_count += 1;
        },
    });

    return {typeahead, $menu};
}

function active_item_name($menu) {
    const active_items = $menu.items.filter((item) => item.classes.has("active"));
    assert.equal(active_items.length, 1);
    return active_items[0].name;
}

function make_keyboard_event(overrides) {
    return {
        altKey: false,
        code: "",
        ctrlKey: false,
        default_prevented: false,
        key: "",
        metaKey: false,
        propagation_stopped: false,
        shiftKey: false,
        type: "keydown",
        preventDefault() {
            this.default_prevented = true;
        },
        stopPropagation() {
            this.propagation_stopped = true;
        },
        ...overrides,
    };
}

run_test("move supports mac ctrl navigation keys", () => {
    navigator.platform = "MacIntel";
    const {typeahead, $menu} = make_typeahead();

    const ctrl_n = make_keyboard_event({
        code: "KeyN",
        ctrlKey: true,
        key: "т",
    });
    typeahead.move(ctrl_n);
    assert.equal(active_item_name($menu), "second");
    assert.equal(ctrl_n.default_prevented, true);
    assert.equal(ctrl_n.propagation_stopped, true);

    const ctrl_p = make_keyboard_event({
        code: "KeyP",
        ctrlKey: true,
        key: "з",
    });
    typeahead.move(ctrl_p);
    assert.equal(active_item_name($menu), "first");
    assert.equal(ctrl_p.default_prevented, true);
    assert.equal(ctrl_p.propagation_stopped, true);

    navigator.platform = "";
});

run_test("move ignores mac ctrl navigation keys with extra modifiers", () => {
    navigator.platform = "MacIntel";

    for (const modifier of [{shiftKey: true}, {altKey: true}, {metaKey: true}]) {
        const {typeahead, $menu} = make_typeahead();
        const event = make_keyboard_event({
            code: "KeyN",
            ctrlKey: true,
            key: "n",
            ...modifier,
        });

        typeahead.move(event);
        assert.equal(active_item_name($menu), "first");
        assert.equal(event.default_prevented, false);
    }

    navigator.platform = "";
});

run_test("move ignores ctrl-n and ctrl-p on non-mac keyboards", () => {
    navigator.platform = "Linux x86_64";

    for (const key_event of [
        {code: "KeyN", key: "n"},
        {code: "KeyP", key: "p"},
    ]) {
        const {typeahead, $menu} = make_typeahead();
        const event = make_keyboard_event({
            ctrlKey: true,
            ...key_event,
        });

        typeahead.move(event);
        assert.equal(active_item_name($menu), "first");
        assert.equal(event.default_prevented, false);
    }

    navigator.platform = "";
});

run_test("mac ctrl navigation keyup does not re-render typeahead", () => {
    navigator.platform = "MacIntel";

    for (const key_event of [
        {active_index: 0, code: "KeyN", key: "n", selected_item: "second"},
        {active_index: 1, code: "KeyP", key: "p", selected_item: "first"},
    ]) {
        const {typeahead, $menu} = make_typeahead({active_index: key_event.active_index});

        typeahead.keydown(
            make_keyboard_event({
                code: key_event.code,
                ctrlKey: true,
                key: key_event.key,
            }),
        );
        assert.equal(active_item_name($menu), key_event.selected_item);
        assert.equal(typeahead.lookup_count, 0);

        const letter_keyup = make_keyboard_event({
            code: key_event.code,
            ctrlKey: true,
            key: key_event.key,
            type: "keyup",
        });
        typeahead.keyup(letter_keyup);
        assert.equal(active_item_name($menu), key_event.selected_item);
        assert.equal(typeahead.lookup_count, 0);
        assert.equal(letter_keyup.default_prevented, true);

        const ctrl_keyup = make_keyboard_event({
            code: "ControlLeft",
            key: "Control",
            type: "keyup",
        });
        typeahead.keyup(ctrl_keyup);
        assert.equal(active_item_name($menu), key_event.selected_item);
        assert.equal(typeahead.lookup_count, 0);
        assert.equal(ctrl_keyup.default_prevented, true);
    }

    navigator.platform = "";
});

run_test("mac ctrl navigation keyup ignores control-first release order", () => {
    navigator.platform = "MacIntel";
    const {typeahead, $menu} = make_typeahead();

    typeahead.keydown(
        make_keyboard_event({
            code: "KeyN",
            ctrlKey: true,
            key: "n",
        }),
    );
    assert.equal(active_item_name($menu), "second");

    typeahead.keyup(
        make_keyboard_event({
            code: "ControlLeft",
            key: "Control",
            type: "keyup",
        }),
    );
    assert.equal(active_item_name($menu), "second");
    assert.equal(typeahead.lookup_count, 0);

    const letter_keyup = make_keyboard_event({
        code: "KeyN",
        key: "n",
        type: "keyup",
    });
    typeahead.keyup(letter_keyup);
    assert.equal(active_item_name($menu), "second");
    assert.equal(typeahead.lookup_count, 0);
    assert.equal(letter_keyup.default_prevented, true);

    navigator.platform = "";
});

run_test("non-mac and modified ctrl navigation keyup keeps normal lookup behavior", () => {
    for (const test_case of [
        {
            keydown_platform: "Linux x86_64",
            keyup_platform: "Linux x86_64",
            event: {code: "KeyN", ctrlKey: true, key: "n"},
        },
        {
            keydown_platform: "MacIntel",
            keyup_platform: "MacIntel",
            event: {code: "KeyN", ctrlKey: true, key: "n", shiftKey: true},
        },
    ]) {
        navigator.platform = test_case.keydown_platform;
        const {typeahead, $menu} = make_typeahead();
        typeahead.keydown(make_keyboard_event(test_case.event));
        assert.equal(active_item_name($menu), "first");

        navigator.platform = test_case.keyup_platform;
        typeahead.keyup(make_keyboard_event({...test_case.event, type: "keyup"}));
        assert.equal(active_item_name($menu), "first");
        assert.equal(typeahead.lookup_count, 1);
    }

    navigator.platform = "";
});
