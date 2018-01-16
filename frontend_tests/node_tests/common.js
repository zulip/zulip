zrequire('common');

set_global('$', global.make_zjquery());

(function test_basics() {
    common.autofocus('#home');
    assert($('#home').is_focused());
}());
