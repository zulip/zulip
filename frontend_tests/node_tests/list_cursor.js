zrequire('list_cursor');

set_global('blueslip', global.make_zblueslip());

run_test('config errors', () => {
    blueslip.set_test_data('error', 'Programming error');
    list_cursor({});
});

function basic_conf() {
    const list = {
        scroll_container_sel: 'whatever',
        find_li: () => {},
        first_key: () => {},
        prev_key: () => {},
        next_key: () => {},
    };

    const conf = {
        list: list,
        highlight_class: 'highlight',
    };

    return conf;
}

run_test('misc errors', () => {
    const conf = basic_conf();

    const cursor = list_cursor(conf);

    // Test that we just ignore empty
    // lists for unknown keys.
    conf.list.find_li = (opts) => {
        assert.equal(opts.key, 'nada');
        assert.equal(opts.force_render, true);
        return [];
    };

    cursor.get_row('nada');

    blueslip.set_test_data('error', 'Caller is not checking keys for list_cursor.go_to');
    cursor.go_to(undefined);

    blueslip.set_test_data('error', 'Cannot highlight key for list_cursor: nada');
    cursor.go_to('nada');

    blueslip.clear_test_data();
    cursor.prev();
    cursor.next();
});

run_test('single item list', () => {
    const conf = basic_conf();
    const cursor = list_cursor(conf);

    const valid_key = '42';
    const li_stub = {
        length: 1,
        addClass: () => {},
    };

    cursor.adjust_scroll = () => {};

    conf.list.find_li = () => {
        return li_stub;
    };

    cursor.go_to(valid_key);

    // Test prev/next, which should just silently do nothing.
    // (Our basic_conf() has prev_key and next_key return undefined.)
    blueslip.clear_test_data();
    cursor.prev();
    cursor.next();

    // The next line is also a noop designed to just give us test
    // coverage.
    cursor.go_to(valid_key);
});
