set_global('$', global.make_zjquery());
zrequire('buddy_data');
zrequire('buddy_list');

run_test('get_items', () => {
    const alice_li = $.create('alice stub');
    const sel = 'li.user_sidebar_entry';

    buddy_list.container.set_find_results(sel, {
        map: (f) => [f(0, alice_li)],
    });
    const items = buddy_list.get_items();

    assert.deepEqual(items, [alice_li]);
});
