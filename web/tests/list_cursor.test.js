"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const blueslip = require("./lib/zblueslip");
const $ = require("./lib/zjquery");

const {ListCursor} = zrequire("list_cursor");

run_test("config errors", () => {
    blueslip.expect("error", "Programming error");
    new ListCursor({});
});

function basic_conf({first_key, prev_key, next_key}) {
    const list = {
        scroll_container_sel: "whatever",
        find_li() {},
        first_key,
        prev_key,
        next_key,
    };

    const conf = {
        list,
        highlight_class: "highlight",
    };

    return conf;
}

run_test("misc errors", ({override}) => {
    const conf = basic_conf({
        first_key: () => undefined,
        prev_key: /* istanbul ignore next */ () => undefined,
        next_key: /* istanbul ignore next */ () => undefined,
    });

    const cursor = new ListCursor(conf);

    // Test that we just ignore empty
    // lists for unknown keys.
    override(conf.list, "find_li", ({key, force_render}) => {
        assert.equal(key, "nada");
        assert.equal(force_render, true);
        return [];
    });

    cursor.get_row("nada");

    blueslip.expect("error", "Caller is not checking keys for ListCursor.go_to");
    cursor.go_to(undefined);

    blueslip.expect("error", "Cannot highlight key for ListCursor");
    cursor.go_to("nada");

    cursor.prev();
    cursor.next();
});

run_test("single item list", ({override}) => {
    const valid_key = "42";

    const conf = basic_conf({
        first_key: /* istanbul ignore next */ () => valid_key,
        next_key: () => undefined,
        prev_key: () => undefined,
    });
    const cursor = new ListCursor(conf);

    const $li_stub = {
        length: 1,
        addClass() {},
    };

    override(conf.list, "find_li", () => $li_stub);
    override(cursor, "adjust_scroll", () => {});

    cursor.go_to(valid_key);

    // Test prev/next, which should just silently do nothing.
    cursor.prev();
    cursor.next();

    // The next line is also a noop designed to just give us test
    // coverage.
    cursor.go_to(valid_key);
});

run_test("multiple item list", ({override}) => {
    const conf = basic_conf({
        first_key: /* istanbul ignore next */ () => 1,
        next_key: (key) => (key < 3 ? key + 1 : undefined),
        prev_key: (key) => (key > 1 ? key - 1 : undefined),
    });
    const cursor = new ListCursor(conf);
    override(cursor, "adjust_scroll", () => {});

    function li(key) {
        return $.create(`item-${key}`, {children: ["stub"]});
    }

    const list_items = {
        1: li(1),
        2: li(2),
        3: li(3),
    };

    override(conf.list, "find_li", ({key}) => list_items[key]);

    cursor.go_to(2);
    assert.equal(cursor.get_key(), 2);
    assert.ok(!list_items[1].hasClass("highlight"));
    assert.ok(list_items[2].hasClass("highlight"));
    assert.ok(!list_items[3].hasClass("highlight"));

    cursor.next();
    cursor.next();
    cursor.next();

    assert.equal(cursor.get_key(), 3);
    assert.ok(!list_items[1].hasClass("highlight"));
    assert.ok(!list_items[2].hasClass("highlight"));
    assert.ok(list_items[3].hasClass("highlight"));

    cursor.prev();
    cursor.prev();
    cursor.prev();

    assert.equal(cursor.get_key(), 1);
    assert.ok(list_items[1].hasClass("highlight"));
    assert.ok(!list_items[2].hasClass("highlight"));
    assert.ok(!list_items[3].hasClass("highlight"));

    cursor.clear();
    assert.equal(cursor.get_key(), undefined);
    cursor.redraw();
    assert.ok(!list_items[1].hasClass("highlight"));
});
