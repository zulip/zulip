"use strict";

zrequire("list_cursor");

run_test("config errors", () => {
    blueslip.expect("error", "Programming error");
    new ListCursor({});
});

function basic_conf() {
    const list = {
        scroll_container_sel: "whatever",
        find_li: () => {},
        first_key: () => {},
        prev_key: () => {},
        next_key: () => {},
    };

    const conf = {
        list,
        highlight_class: "highlight",
    };

    return conf;
}

run_test("misc errors", () => {
    const conf = basic_conf();

    const cursor = new ListCursor(conf);

    // Test that we just ignore empty
    // lists for unknown keys.
    conf.list.find_li = (opts) => {
        assert.equal(opts.key, "nada");
        assert.equal(opts.force_render, true);
        return [];
    };

    cursor.get_row("nada");

    blueslip.expect("error", "Caller is not checking keys for ListCursor.go_to");
    cursor.go_to(undefined);

    blueslip.expect("error", "Cannot highlight key for ListCursor: nada");
    cursor.go_to("nada");

    cursor.prev();
    cursor.next();
});

run_test("single item list", () => {
    const conf = basic_conf();
    const cursor = new ListCursor(conf);

    const valid_key = "42";
    const li_stub = {
        length: 1,
        addClass: () => {},
    };

    cursor.adjust_scroll = () => {};

    conf.list.find_li = () => li_stub;

    cursor.go_to(valid_key);

    // Test prev/next, which should just silently do nothing.
    // (Our basic_conf() has prev_key and next_key return undefined.)
    cursor.prev();
    cursor.next();

    // The next line is also a noop designed to just give us test
    // coverage.
    cursor.go_to(valid_key);
});
