zrequire('common');

set_global('$', global.make_zjquery());

run_test('basics', () => {
    common.autofocus('#home');
    assert($('#home').is_focused());
});
