const noop = () => {};

set_global('$', global.make_zjquery());
const input = $.create('input');
set_global('document', {
    createElement: () => input,
    execCommand: noop,
});

$("body").append = noop;
$(input).val = (arg) => {
    assert.equal(arg, "iago@zulip.com");
    return {
        select: noop,
    };
};

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

run_test('copy_data_attribute_value', () => {
    var elem = $.create('.envelope-link');
    elem.data = (key) => {
        if (key === "admin-emails") {
            return "iago@zulip.com";
        }
        return "";
    };
    elem.fadeOut = (val) => {
        assert.equal(val, 250);
    };
    elem.fadeIn = (val) => {
        assert.equal(val, 1000);
    };
    common.copy_data_attribute_value(elem, 'admin-emails');
});
