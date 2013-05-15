var common = (function () {

var exports = {};

function timestamp() {
    return new Date().getTime();
}

// The timestamp of the last message send or get_events result.
var last_send_or_update = -1;

function log_in(credentials) {
    if (credentials === undefined) {
        credentials = {username: 'iago@humbughq.com', password: 'FlokrWdZefyEWkfI'};
    }

    casper.test.info('Logging in');
    casper.fill('form[action^="/accounts/login"]', {
        username: credentials.username,
        password: credentials.password
    }, true /* submit form */);
}

exports.initialize_casper = function (viewport) {
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

exports.send_message = function (type, params) {
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
        casper.waitWhileVisible('#stream,#private-message', function () {
            last_send_or_update = timestamp();
        });
    });
};

// Wait for any previous send to finish, then send a message.
exports.wait_and_send = function (type, params) {
    casper.waitForSelector('#compose-send-button:enabled', function () {
        exports.send_message(type, params);
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
            headings: $.map(tbl.find('.recipient_row .right_part'), function (elem) {
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

// Send a whole list of messages using wait_and_send.
exports.send_many = function (msgs) {
    msgs.forEach(function (msg) {
        exports.wait_and_send(
            (msg.stream !== undefined) ? 'stream' : 'private',
            msg);
    });
};

// Wait to receive queued messages.
exports.wait_for_receive = function (step) {
    // Wait until the last send or get_events result was more than 300 ms ago.
    casper.waitFor(function () {
        return (timestamp() - last_send_or_update) > 300;
    }, step);
};

// innerText sometimes gives us non-breaking space characters, and occasionally
// a different number of spaces than we expect.
exports.normalize_spaces = function (str) {
    return str.replace(/\s+/g, ' ');
};

// Call get_rendered_messages and then check that the last few headings and
// bodies match the specified arrays.
exports.expected_messages = function (table, headings, bodies) {
    casper.test.assertVisible('#'+table,
        table + ' is visible');

    var msg = exports.get_rendered_messages(table);

    casper.test.assertEquals(
        msg.headings.slice(-headings.length).map(exports.normalize_spaces),
        headings,
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
