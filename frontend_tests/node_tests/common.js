set_global('$', global.make_zjquery());

zrequire('common');

run_test('basics', () => {
    common.autofocus('#home');
    assert($('#home').is_focused());
});

run_test('phrase_match', () => {
    assert(common.phrase_match('tes', 'test'));
    assert(common.phrase_match('Tes', 'test'));
    assert(common.phrase_match('Tes', 'Test'));
    assert(common.phrase_match('tes', 'Stream Test'));

    assert(!common.phrase_match('tests', 'test'));
    assert(!common.phrase_match('tes', 'hostess'));
});
