var ui = zrequire('ui');
set_global('i18n', global.stub_i18n);

run_test('get_hotkey_deprecation_notice', () => {
    var expected = 'translated: We\'ve replaced the "*" hotkey with "Ctrl + s" to make this common shortcut easier to trigger.';
    var actual = ui.get_hotkey_deprecation_notice('*', 'Ctrl + s');
    assert.equal(expected, actual);
});
