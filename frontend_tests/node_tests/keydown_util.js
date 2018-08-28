set_global('$', global.make_zjquery());

zrequire('keydown_util');

run_test('test_early_returns', () => {
    var stub = $.create('stub');
    var opts = {
        elem: stub,
        handlers: {},
    };

    keydown_util.handle(opts);
    var keydown_f = stub.keydown;

    var e1 = {
        which: 17, // not in keys
    };

    keydown_f(e1);

    var e2 = {
        which: 13, // no handler
    };

    keydown_f(e2);
});
