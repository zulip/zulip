var common = (function () {

var exports = {};

var test_credentials = require('../casper_lib/test_credentials.js').test_credentials;

function timestamp() {
    return new Date().getTime();
}

// The timestamp of the last message send or get_events result.
var last_send_or_update = -1;

function log_in(credentials) {
    if (credentials === undefined) {
        credentials = test_credentials.default_user;
    }

    casper.test.info('Logging in');
    casper.fill('form[action^="/accounts/login"]', {
        username: credentials.username,
        password: credentials.password
    }, true /* submit form */);
}

exports.initialize_casper = function (viewport) {
    if (casper.zulip_initialized !== undefined) {
        return;
    }
    casper.zulip_initialized = true;
    // These initialization steps will fail if they run before
    // casper.start has been called.

    // Set default viewport size to something reasonable
    casper.page.viewportSize = viewport || {width: 1280, height: 768};

    // Fail if we get a JavaScript error in the page's context.
    // Based on the example at http://phantomjs.org/release-1.5.html
    //
    // casper.on('error') doesn't work (it never gets called) so we
    // set this at the PhantomJS level.
    casper.page.onError = function (msg, trace) {
        casper.test.error(msg);
        casper.echo('Traceback:');
        trace.forEach(function (item) {
            casper.echo('  ' + item.file + ':' + item.line);
        });
        casper.exit(1);
    };

    // Capture screens from all failures
    var casper_failure_count = 1;
    casper.test.on('fail', function failure() {
        if (casper_failure_count <= 10) {
            casper.capture("/tmp/casper-failure" + casper_failure_count + ".png");
            casper_failure_count++;
        }
    });

    // Update last_send_or_update whenever get_events returns.
    casper.on('resource.received', function (resource) {
        if (/\/json\/get_events/.test(resource.url)) {
            last_send_or_update = timestamp();
        }
    });

    casper.on('load.finished', function () {
        casper.evaluateOrDie(function () {
            $(document).trigger($.Event('phantom_page_loaded'));
            return true;
        });
    });

    casper.evaluate(function () {
        window.localStorage.clear();
    });
};

exports.then_log_in = function (credentials) {
    casper.then(function () {
        log_in(credentials);
    });
};

exports.start_and_log_in = function (credentials, viewport) {
    casper.start('http://localhost:9981/accounts/login', function () {
        exports.initialize_casper(viewport);
        log_in(credentials);
    });
};

exports.then_log_out = function () {
    casper.then(function () {
        casper.test.info('Logging out');
        casper.click('li[title="Log out"] a');
    });
};

exports.enable_page_console = function () {
    // Call this (after casper.start) to enable printing page-context
    // console.log (plus some CasperJS-specific messages) to the
    // terminal.
    casper.on('remote.message', function (msg) {
        casper.echo(msg);
    });
};

exports.check_form = function (form_selector, expected, test_name) {
    var values = casper.getFormValues(form_selector);
    var k;
    for (k in expected) {
        if (expected.hasOwnProperty(k)) {
            casper.test.assertEqual(values[k], expected[k],
                                    test_name ? (test_name + ": " + k) : undefined);
        }
    }
};

// Wait for any previous send to finish, then send a message.
exports.then_send_message = function (type, params) {
    casper.waitForSelector('#compose-send-button:enabled');
    casper.waitForSelector('#new_message_content', function () {
        if(type === "stream") {
            casper.page.sendEvent('keypress', "c");
        }
        else if (type === "private") {
            casper.page.sendEvent('keypress', "C");
        }
        else {
            casper.test.assertTrue(false, "send_message got valid message type");
        }
        casper.fill('form[action^="/json/send_message"]', params);
        casper.click('#compose-send-button');
    });
    casper.waitFor(function emptyComposeBox() {
        return casper.getFormValues('form[action^="/json/send_message"]').content === '';
    }, function () {
        last_send_or_update = timestamp();
    });
};

// Get message headings (recipient rows) and bodies out of the DOM.
// casper.evaluate plays weird tricks with a closure, evaluating
// it in the web page's context.  Passing arguments from the test
// script's context is awkward (c.f. the various appearances of
// 'table' here).
exports.get_rendered_messages = function (table) {
    return casper.evaluate(function (table) {
        var tbl = $('#'+table);
        return {
            headings: $.map(tbl.find('.recipient_row .message-header-contents'), function (elem) {
                return elem.innerText;
            }),

            bodies: $.map(tbl.find('.message_content'), function (elem) {
                return elem.innerHTML;
            })
        };
    }, {
        table: table
    });
};

exports.get_form_field_value = function (selector) {
    return casper.evaluate(function (selector) {
        return $(selector).val();
    }, selector);
};

// Inject key presses by running some jQuery code in page context.
// PhantomJS and CasperJS don't provide a clean way to insert key
// presses by code, only strings of printable characters.
exports.keypress = function (code) {
    casper.evaluate(function (code) {
        $('body').trigger($.Event('keydown', { which: code }));
    }, {
        code: code
    });
};

// Send a whole list of messages using then_send_message.
exports.then_send_many = function (msgs) {
    msgs.forEach(function (msg) {
        exports.then_send_message(
            (msg.stream !== undefined) ? 'stream' : 'private',
            msg);
    });
};

// Wait to receive queued messages.
exports.wait_for_receive = function (step) {
    // Wait until the last send or get_events result was more than 1000 ms ago.
    casper.waitFor(function () {
        return (timestamp() - last_send_or_update) > 1000;
    }, step);
};

// Wait until the loading spinner goes away (helpful just after logging in).
exports.wait_for_load = function (step) {
    casper.waitWhileVisible('#page_loading_indicator', step);
};

// innerText sometimes gives us non-breaking space characters, and occasionally
// a different number of spaces than we expect.
exports.normalize_spaces = function (str) {
    return str.replace(/\s+/g, ' ');
};

exports.ltrim = function (str) {
    return str.replace(/^\s+/g, '');
};

exports.rtrim = function (str) {
    return str.replace(/\s+$/g, '');
};

exports.trim = function (str) {
    return exports.rtrim(exports.ltrim(str));
};

// Call get_rendered_messages and then check that the last few headings and
// bodies match the specified arrays.
exports.expected_messages = function (table, headings, bodies) {
    casper.test.assertVisible('#'+table,
        table + ' is visible');

    var msg = exports.get_rendered_messages(table);

    casper.test.assertEquals(
        msg.headings.slice(-headings.length).map(exports.normalize_spaces).map(exports.trim),
        headings.map(exports.trim),
        'Got expected message headings');

    casper.test.assertEquals(
        msg.bodies.slice(-bodies.length),
        bodies,
        'Got expected message bodies');
};

exports.un_narrow = function () {
    casper.test.info('Un-narrowing');
    common.keypress(27); // Esc
};

return exports;

}());

// For inclusion with CasperJS
try {
    exports.common = common;
} catch (e) {
}
