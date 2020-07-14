const ui = zrequire("ui");

set_global("navigator", {
    userAgent: "",
});

run_test("get_hotkey_deprecation_notice", () => {
    const expected = 'translated: We\'ve replaced the "*" hotkey with "Ctrl + s" to make this common shortcut easier to trigger.';
    const actual = ui.get_hotkey_deprecation_notice("*", "Ctrl + s");
    assert.equal(expected, actual);
});

run_test("get_hotkey_deprecation_notice_mac", () => {
    global.navigator.userAgent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.167 Safari/537.36";
    const expected = 'translated: We\'ve replaced the "*" hotkey with "Cmd + s" to make this common shortcut easier to trigger.';
    const actual = ui.get_hotkey_deprecation_notice("*", "Cmd + s");
    assert.equal(expected, actual);
    // Reset userAgent
    global.navigator.userAgent = "";
});
