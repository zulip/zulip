var util = require("util");
var common = (function () {

var exports = {};

var test_credentials = require('../../var/casper/test_credentials.js').test_credentials;

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
    casper.fill('form[action^="/accounts/login/"]', {
        username: credentials.username,
        password: credentials.password,
    }, true /* submit form */);
}


exports.init_viewport = function () {
    casper.options.viewportSize = {width: 1280, height: 1024};
};

exports.initialize_casper = function () {
    if (casper.zulip_initialized !== undefined) {
        return;
    }
    casper.zulip_initialized = true;
    // These initialization steps will fail if they run before
    // casper.start has been called.

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
            casper.capture("var/casper/casper-failure" + casper_failure_count + ".png");
            casper_failure_count += 1;
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

    // This function should always be enclosed within a then() otherwise
    // it might not exist on casper object.
    casper.waitForSelectorText = function (selector, text, then, onTimeout, timeout) {
        this.waitForSelector(selector, function _then() {
            this.waitFor(function _check() {
                var content = this.fetchText(selector);
                if (util.isRegExp(text)) {
                    return text.test(content);
                }
                return content.indexOf(text) !== -1;
            }, then, onTimeout, timeout);
        }, onTimeout, timeout);
        return this;
    };

    casper.evaluate(function () {
        window.localStorage.clear();
    });

    // This captures console messages from the app.
    casper.on('remote.message', function (msg) {
        casper.echo("app console: " + msg);
    });
};

exports.then_log_in = function (credentials) {
    casper.then(function () {
        log_in(credentials);
    });
};

exports.start_and_log_in = function (credentials, viewport) {
    var log_in_url = "http://zulip.zulipdev.com:9981/accounts/login/";
    exports.init_viewport();
    casper.start(log_in_url, function () {
        exports.initialize_casper(viewport);
        log_in(credentials);
    });
};

exports.then_click = function (selector) {
    casper.then(function () {
        casper.waitUntilVisible(selector, function () {
            casper.click(selector);
        });
    });
};

exports.then_log_out = function () {
    var menu_selector = '#settings-dropdown';
    var logout_selector = 'a[href="#logout"]';

    casper.waitUntilVisible(menu_selector, function () {
        casper.click(menu_selector);

        casper.waitUntilVisible(logout_selector, function () {
            casper.test.info('Logging out');
            casper.click(logout_selector);

        });

    });
    casper.waitUntilVisible(".login-page-container", function () {
        casper.test.assertUrlMatch(/accounts\/login\/$/);
        casper.test.info("Logged out");
    });
};

// Put the specified string into the field_selector, then
// select the menu item matching item by typing str.
exports.select_item_via_typeahead = function (field_selector, str, item) {
    casper.then(function () {
        casper.test.info('Looking in ' + field_selector + ' to select ' + str + ', ' + item);

        casper.evaluate(function (field_selector, str, item) {
            // Set the value and then send a bogus keyup event to trigger
            // the typeahead.
            $(field_selector)
                .focus()
                .val(str)
                .trigger($.Event('keyup', { which: 0 }));

            // You might think these steps should be split by casper.then,
            // but apparently that's enough to make the typeahead close (??),
            // but not the first time.

            // Trigger the typeahead.
            // Reaching into the guts of Bootstrap Typeahead like this is not
            // great, but I found it very hard to do it any other way.

            var tah = $(field_selector).data().typeahead;
            tah.mouseenter({
                currentTarget: $('.typeahead:visible li:contains("' + item + '")')[0],
            });
            tah.select();
        }, {field_selector: field_selector, str: str, item: item});
    });
};

exports.check_form = function (form_selector, expected, test_name) {
    var values = casper.getFormValues(form_selector);
    var k;
    for (k in expected) {
        if (expected.hasOwnProperty(k)) {
            casper.test.assertEqual(values[k], expected[k],
                                    test_name ? test_name + ": " + k : undefined);
        }
    }
};

exports.wait_for_message_actually_sent = function () {
    casper.waitFor(function () {
        return casper.evaluate(function () {
            return !current_msg_list.last().locally_echoed;
        });
    });
};

exports.turn_off_press_enter_to_send = function () {
    var enter_send_selector = '#enter_sends';
    casper.waitForSelector(enter_send_selector);

    var is_checked = casper.evaluate(function (enter_send_selector) {
        return document.querySelector(enter_send_selector).checked;
    }, enter_send_selector);

    if (is_checked) {
        casper.click(enter_send_selector);
    }
};

exports.pm_recipient = {
    set: function (recip) {
        casper.evaluate(function (recipient) {
            $("#private_message_recipient").text(recipient)
                .trigger({ type: "keydown", keyCode: 13 });
        }, { recipient: recip });
    },

    expect: function (expected_value) {
        var displayed_recipients = casper.evaluate(function () {
            return compose_state.recipient();
        });
        casper.test.assertEquals(displayed_recipients, expected_value);
    },
};

// Wait for any previous send to finish, then send a message.
exports.then_send_message = function (type, params) {
    casper.then(function () {
        casper.waitForSelector('#compose-send-button:enabled');
        casper.waitForSelector('#compose-textarea');
    });

    casper.then(function () {
        if (type === "stream") {
            casper.page.sendEvent('keypress', "c");
        } else if (type === "private") {
            casper.page.sendEvent('keypress', "x");
        } else {
            casper.test.assertTrue(false, "send_message got valid message type");
        }

        exports.pm_recipient.set(params.recipient);
        delete params.recipient;

        if (params.stream) {
            params.stream_message_recipient_stream = params.stream;
            delete params.stream;
        }

        if (params.subject) {
            params.stream_message_recipient_topic = params.subject;
            delete params.subject;
        }

        casper.fill('form[action^="/json/messages"]', params);

        exports.turn_off_press_enter_to_send();

        casper.then(function () {
            casper.click('#compose-send-button');
        });
    });

    casper.then(function () {
        casper.waitFor(function emptyComposeBox() {
            return casper.getFormValues('form[action^="/json/messages"]').content === '';
        });
        exports.wait_for_message_actually_sent();
        casper.evaluate(function () {
            compose_actions.cancel();
        });
    });

    casper.then(function () {
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
        var tbl = $('#' + table);
        return {
            headings: $.map(tbl.find('.recipient_row .message-header-contents'), function (elem) {
                var $clone = $(elem).clone(true);
                $clone.find(".recipient_row_date").remove();

                return $clone.text();
            }),

            bodies: $.map(tbl.find('.message_content'), function (elem) {
                return elem.innerHTML;
            }),
        };
    }, {
        table: table,
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
        code: code,
    });
};

// Send a whole list of messages using then_send_message.
exports.then_send_many = function (msgs) {
    msgs.forEach(function (msg) {
        exports.then_send_message(
            msg.stream !== undefined ? 'stream' : 'private',
            msg);
    });
};

// Wait to receive queued messages.
exports.wait_for_receive = function (step) {
    // Wait until the last send or get_events result was more than 1000 ms ago.
    casper.waitFor(function () {
        return timestamp() - last_send_or_update > 1000;
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
    casper.test.assertVisible('#' + table, table + ' is visible');

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
    if (casper.visible('.message_comp')) {
        // close the compose box
        common.keypress(27); // Esc
    }
    common.keypress(27); // Esc
};

return exports;

}());

// For inclusion with CasperJS
try {
    exports.common = common;
} catch (e) {
    // continue regardless of error
}
