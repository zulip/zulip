var common = require('../casper_lib/common.js');

function stream_checkbox(stream_name) {
    const stream_id = common.get_stream_id(stream_name);
    return '#stream-checkboxes [data-stream-id="' + stream_id + '"]';
}

function stream_span(stream_name) {
    return stream_checkbox(stream_name) + ' input ~ span';
}

function user_checkbox(email) {
    var user_id = common.get_user_id(email);
    return '#user-checkboxes [data-user-id="' + user_id + '"]';
}

function user_span(email) {
    return user_checkbox(email) + ' input ~ span';
}

function is_checked(email) {
    var sel = user_checkbox(email);
    return casper.evaluate(function (sel) {
        return $(sel).find('input')[0].checked;
    }, {
        sel: sel,
    });
}

common.start_and_log_in();

casper.then(function () {
    var menu_selector = '#settings-dropdown';

    casper.test.info('Streams page');

    casper.waitUntilVisible(menu_selector, function () {
        casper.click(menu_selector);
        casper.then(function () {
            casper.click('a[href^="#streams"]');
            casper.test.assertUrlMatch(
                /^http:\/\/[^/]+\/#streams/,
                'URL suggests we are on streams page');
            casper.waitUntilVisible('#subscription_overlay.new-style', function () {
                casper.test.assertExists('#subscription_overlay.new-style', 'Streams page is active');
            });
        });
    });
});

casper.waitUntilVisible('.sub_unsub_button.checked', function () {
    casper.test.assertExists('.sub_unsub_button.checked', 'Initial subscriptions loaded');
    casper.click('#add_new_subscription .create_stream_button');
});

casper.then(function () {
    casper.test.assertExists(user_checkbox('cordelia@zulip.com'), 'Original user list contains Cordelia');
    casper.test.assertExists(user_checkbox('othello@zulip.com'), 'Original user list contains Othello');
});

casper.waitUntilVisible("#copy-from-stream-expand-collapse", function () {
    casper.click('#copy-from-stream-expand-collapse');
});

casper.waitUntilVisible("#stream-checkboxes", function () {
    casper.test.assertExists(stream_checkbox('Scotland'), 'Original stream list contains Scotland');
    casper.test.assertExists(stream_checkbox('Rome'), 'Original stream list contains Rome');
});

casper.waitUntilVisible("form#stream_creation_form", function () {
    casper.test.info("Filtering with keyword 'ot'");
    casper.fill('form#stream_creation_form', {user_list_filter: 'ot'});
});
casper.waitUntilVisible("#user-checkboxes", function () {
    casper.test.assertEquals(casper.visible(user_checkbox('cordelia@zulip.com')),
                             false,
                             "Cordelia is not visible");
    casper.test.assertEquals(casper.visible(user_checkbox('othello@zulip.com')),
                             true,
                             "Othello is visible");

    /* The filter should not impact streams */
    casper.test.assertEquals(casper.visible(stream_checkbox('Scotland')),
                             true,
                             "Scotland is visible");
    casper.test.assertEquals(casper.visible(stream_checkbox('Rome')),
                             true,
                             "Rome is visible");
});
casper.then(function () {
    casper.test.info("Check Uncheck only visible users for new stream");
    casper.click('.subs_set_all_users');
    casper.wait(100, function () {
        casper.test.assert(
            !is_checked('cordelia@zulip.com'),
            "Cordelia is unchecked");
        casper.test.assert(
            is_checked('othello@zulip.com'),
            "Othello is checked");
    });
});
casper.then(function () {
    casper.test.info("Check Uncheck only visible users for new stream");
    casper.click('.subs_unset_all_users');
    casper.wait(100, function () {
        casper.test.assert(
            !is_checked('othello@zulip.com'),
            "Othello is unchecked");
    });
});
casper.then(function () {
    casper.test.info("Clearing user filter search box");
    casper.fill('form#stream_creation_form', {user_list_filter: ''});
});
casper.then(function () {
    casper.test.assertEquals(casper.visible(user_checkbox('cordelia@zulip.com')),
                             true,
                             "Cordelia is visible again");
    casper.test.assertEquals(casper.visible(user_checkbox('othello@zulip.com')),
                             true,
                             "Othello is visible again");
    casper.test.assertEquals(casper.visible(stream_checkbox('Scotland')),
                             true,
                             "Scotland is visible again");
    casper.test.assertEquals(casper.visible(stream_checkbox('Rome')),
                             true,
                             "Rome is visible again");
});
casper.then(function () {
    casper.waitUntilVisible('#stream_creation_form', function () {
        casper.test.assertTextExists('Create stream', 'New stream creation panel');
        casper.fill('form#stream_creation_form', {stream_name: 'Waseemio', stream_description: 'Oimeesaw'});
        casper.click(stream_span('Scotland'));
        casper.click(user_span('cordelia@zulip.com'));
        casper.click(user_span('othello@zulip.com'));
        casper.click('form#stream_creation_form button.button.sea-green');
    });
});

casper.then(function () {
    casper.waitFor(function () {
        return casper.evaluate(function () {
            return $('.stream-name').is(':contains("Waseemio")');
        });
    });
});

casper.then(function () {
    casper.test.info("User should be subscribed to stream Waseemio");
    casper.test.assertSelectorHasText('.stream-name', 'Waseemio');
    casper.test.assertSelectorHasText('.description', 'Oimeesaw');
    // Based on the selected checkboxes while creating stream,
    // 4 users from Scotland are added.
    // 1 user, Cordelia, is added. Othello (subscribed to Scotland) is removed.
    // FIXME: This assertion may pick up the count from a random other stream.
    casper.test.assertSelectorHasText('.subscriber-count-text', '4');
    casper.fill('form#stream_creation_form', {stream_name: '  '});
    casper.click('form#stream_creation_form button.button.sea-green');
});
casper.then(function () {
    common.wait_for_text('#stream_name_error', 'A stream needs to have a name', function () {
        casper.test.assertTextExists('A stream needs to have a name', "Can't create a stream with an empty name");
        casper.click('form#stream_creation_form button.button.white');
        casper.fill('form#stream_creation_form', {stream_name: 'Waseemio'});
        casper.click('form#stream_creation_form button.button.sea-green');
    });
});
casper.then(function () {
    common.wait_for_text('#stream_name_error', 'A stream with this name already exists', function () {
        casper.test.assertTextExists('A stream with this name already exists', "Can't create a stream with a duplicate name");
        casper.test.info('Streams should be filtered when typing in the create box');
        casper.click('form#stream_creation_form button.button.white');
    });
});
casper.then(function () {
    common.wait_for_text('#search_stream_name', '', function () {
        casper.test.assertSelectorHasText('.stream-row[data-stream-name="Verona"] .stream-name', 'Verona', 'Verona stream exists before filtering');
        casper.test.assertSelectorDoesntHaveText('.stream-row.notdisplayed .stream-name', 'Verona', 'Verona stream shown before filtering');
    });
});
casper.then(function () {
    casper.evaluate(function () {
        $('#stream_filter input[type="text"]')
            .expectOne()
            .val('waseem')
            .trigger($.Event('input'));
    });
});
casper.waitForSelectorTextChange('.streams-list', function () {
    casper.test.assertSelectorHasText('.stream-row .stream-name', 'Waseemio', 'Waseemio stream exists after filtering');
    casper.test.assertSelectorHasText('.stream-row.notdisplayed .stream-name', 'Verona', 'Verona stream not shown after filtering');
    casper.test.assertSelectorDoesntHaveText('.stream-row.notdisplayed .stream-name', 'Waseemio', 'Waseemio stream shown after filtering');
});

common.then_log_out();

casper.run(function () {
    casper.test.done();
});
