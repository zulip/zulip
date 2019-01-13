set_global('$', global.make_zjquery());

zrequire('keydown_util');

run_test('test_early_returns', () => {
    const stub = $.create('stub');
    const opts = {
        elem: stub,
        handlers: {
            left_arrow: () => {
                throw Error('do not dispatch this with alt key');
            },
        },
    };

    keydown_util.handle(opts);
    const keydown_f = stub.keydown;

    const e1 = {
        which: 17, // not in keys
    };

    keydown_f(e1);

    const e2 = {
        which: 13, // no handler
    };

    keydown_f(e2);

    const e3 = {
        which: 37,
        altKey: true, // let browser handle
    };

    keydown_f(e3);
});
