const rm = zrequire('rendered_markdown');
set_global('$', global.make_zjquery());

run_test('misc_helpers', () => {
    const elem = $.create('.user-mention');
    rm.set_name_in_mention_element(elem, 'Aaron');
    assert.equal(elem.text(), '@Aaron');
    elem.addClass('silent');
    rm.set_name_in_mention_element(elem, 'Aaron, but silent');
    assert.equal(elem.text(), 'Aaron, but silent');
});
