const requires = [];
const new_globals = new Set();
let old_globals = {};

exports.set_global = function (name, val) {
    if (!(name in old_globals)) {
        if (!(name in global)) {
            new_globals.add(name);
        }
        old_globals[name] = global[name];
    }
    global[name] = val;
    return val;
};

exports.zrequire = function (name, fn) {
    if (fn === undefined) {
        fn = '../../static/js/' + name;
    } else if (/^generated\/|^js\/|^shared\/|^third\//.test(fn)) {
        // FIXME: Stealing part of the NPM namespace is confusing.
        fn = '../../static/' + fn;
    }
    delete require.cache[require.resolve(fn)];
    requires.push(fn);
    return require(fn);
};

exports.clear_zulip_refs = function () {
    /*
        This is a big hammer to make sure
        we are not "borrowing" a transitively
        required module from a previous test.
        This kind of leak can make it seems
        like we've written the second test
        correctly, but it will fail if we
        run it standalone.
    */
    _.each(require.cache, (_, fn) => {
        if (fn.indexOf('static/') >= 0) {
            if (fn.indexOf('static/templates') < 0) {
                delete require.cache[fn];
            }
        }
    });
};

exports.restore = function () {
    requires.forEach(function (fn) {
        delete require.cache[require.resolve(fn)];
    });
    Object.assign(global, old_globals);
    old_globals = {};
    for (const name of new_globals) {
        delete global[name];
    }
    new_globals.clear();
};

exports.stub_out_jquery = function () {
    set_global('$', function () {
        return {
            on: function () {},
            trigger: function () {},
            hide: function () {},
            removeClass: function () {},
        };
    });
    $.fn = {};
    $.now = function () {};
};

exports.with_overrides = function (test_function) {
    // This function calls test_function() and passes in
    // a way to override the namespace temporarily.

    const clobber_callbacks = [];

    const override = function (name, f) {
        const parts = name.split('.');
        const module = parts[0];
        const func_name = parts[1];

        if (!Object.prototype.hasOwnProperty.call(global, module)) {
            set_global(module, {});
        }

        global[module][func_name] = f;

        clobber_callbacks.push(function () {
            // If you get a failure from this, you probably just
            // need to have your test do its own overrides and
            // not cherry-pick off of the prior test's setup.
            global[module][func_name] =
                'ATTEMPTED TO REUSE OVERRIDDEN VALUE FROM PRIOR TEST';
        });
    };

    test_function(override);

    for (const f of clobber_callbacks) {
        f();
    }
};
