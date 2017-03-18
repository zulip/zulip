var common = require('../casper_lib/common.js').common;

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
    casper.click('#create_stream_button');
});

casper.then(function () {
    casper.test.assertExists('#user-checkboxes [data-email="cordelia@zulip.com"]', 'Original user list contains Cordelia');
    casper.test.assertExists('#user-checkboxes [data-email="othello@zulip.com"]', 'Original user list contains Othello');
});

casper.waitUntilVisible("#copy-from-stream-expand-collapse", function () {
    casper.click('#copy-from-stream-expand-collapse');
});

casper.waitUntilVisible("#stream-checkboxes", function () {
    casper.test.assertExists('#stream-checkboxes [data-stream-name="Scotland"]', 'Original stream list contains Scotland');
    casper.test.assertExists('#stream-checkboxes [data-stream-name="Rome"]', 'Original stream list contains Rome');
});

casper.waitUntilVisible("form#stream_creation_form", function () {
    casper.test.info("Filtering with keyword 'ot'");
    casper.fill('form#stream_creation_form', {user_list_filter: 'ot'});
});
casper.waitUntilVisible("#user-checkboxes", function () {
    casper.test.assertEquals(casper.visible('#user-checkboxes [data-email="cordelia@zulip.com"]'),
                             false,
                             "Cordelia is not visible");
    casper.test.assertEquals(casper.visible('#user-checkboxes [data-email="othello@zulip.com"]'),
                             true,
                             "Othello is visible");

    /* The filter should not impact streams */
    casper.test.assertEquals(casper.visible('#stream-checkboxes [data-stream-name="Scotland"]'),
                             true,
                             "Scotland is visible");
    casper.test.assertEquals(casper.visible('#stream-checkboxes [data-stream-name="Rome"]'),
                             true,
                             "Rome is visible");
});
casper.then(function () {
    casper.test.info("Check Uncheck only visible users for new stream");
    casper.click('.subs_set_all_users');
    casper.wait(100, function () {
        casper.test.assert(casper.evaluate(function () {
            return !$('#user-checkboxes [value="cordelia@zulip.com"]')[0].checked;
        }), "Cordelia is unchecked");
        casper.test.assert(casper.evaluate(function () {
            return $('#user-checkboxes [value="othello@zulip.com"]')[0].checked;
        }), "Othello is checked");
    });
});
casper.then(function () {
    casper.test.info("Check Uncheck only visible users for new stream");
    casper.click('.subs_unset_all_users');
    casper.wait(100, function () {
        casper.test.assert(casper.evaluate(function () {
            return !$('#user-checkboxes [value="othello@zulip.com"]')[0].checked;
        }), "Othello is unchecked");
    });
});
casper.then(function () {
    casper.test.info("Clearing user filter search box");
    casper.fill('form#stream_creation_form', {user_list_filter: ''});
});
casper.then(function () {
    casper.test.assertEquals(casper.visible('#user-checkboxes [data-email="cordelia@zulip.com"]'),
                             true,
                             "Cordelia is visible again");
    casper.test.assertEquals(casper.visible('#user-checkboxes [data-email="othello@zulip.com"]'),
                             true,
                             "Othello is visible again");
    casper.test.assertEquals(casper.visible('#stream-checkboxes [data-stream-name="Scotland"]'),
                             true,
                             "Scotland is visible again");
    casper.test.assertEquals(casper.visible('#stream-checkboxes [data-stream-name="Rome"]'),
                             true,
                             "Rome is visible again");
});
casper.waitUntilVisible('#stream_creation_form', function () {
    casper.test.assertTextExists('Create stream', 'New stream creation panel');
    casper.fill('form#stream_creation_form', {stream_name: 'Waseemio', stream_description: 'Oimeesaw'});
    casper.click('input[value="Scotland"] ~ span');
    casper.click('input[value="cordelia@zulip.com"] ~ span');
    casper.click('input[value="othello@zulip.com"] ~ span');
    casper.click('form#stream_creation_form button.btn.btn-primary');
});

casper.waitFor(function () {
    return casper.evaluate(function () {
        return $('.stream-name').is(':contains("Waseemio")');
    });
});
casper.then(function () {
    casper.test.info("User should be subscribed to stream Waseemio");
    casper.test.assertSelectorHasText('.stream-name', 'Waseemio');
    casper.test.assertSelectorHasText('.description', 'Oimeesaw');
    // Based on the selected checkboxes while creating stream,
    // 4 users from Scotland are added.
    // 1 user, Cordelia, is added. Othello (subscribed to Scotland) is not added twice.
    casper.test.assertSelectorHasText('.subscriber-count-text', '5');
    casper.fill('form#add_new_subscription', {stream_name: 'WASeemio'});
    casper.click('#create_stream_button');
});
casper.then(function () {
    casper.click('#create_stream_button');
    casper.fill('form#stream_creation_form', {stream_name: '  '});
    casper.click('form#stream_creation_form button.btn.btn-primary');
});
casper.waitForText('A stream needs to have a name', function () {
    casper.test.assertTextExists('A stream needs to have a name', "Can't create a stream with an empty name");
    casper.click('form#stream_creation_form button.btn.btn-default');
    casper.fill('form#add_new_subscription', {stream_name: '  '});
    casper.click('#create_stream_button');
    casper.fill('form#stream_creation_form', {stream_name: 'Waseemio'});
    casper.click('form#stream_creation_form button.btn.btn-primary');
});
casper.waitForText('A stream with this name already exists', function () {
    casper.test.assertTextExists('A stream with this name already exists', "Can't create a stream with a duplicate name");
    casper.test.info('Streams should be filtered when typing in the create box');
    casper.click('form#stream_creation_form button.btn.btn-default');
});
casper.waitForText('Filter streams', function () {
    casper.test.assertSelectorHasText('.stream-row[data-stream-name="Verona"] .stream-name', 'Verona', 'Verona stream exists before filtering');
    casper.test.assertSelectorDoesntHaveText('.stream-row.notdisplayed .stream-name', 'Verona', 'Verona stream shown before filtering');
});
casper.then(function () {
    casper.fill('form#add_new_subscription', {stream_name: 'was'});
    casper.evaluate(function () {
      $('#add_new_subscription input[type="text"]').expectOne()
        .trigger($.Event('input'));
    });
});
casper.waitForSelectorTextChange('form#add_new_subscription', function () {
    casper.test.assertSelectorHasText('.stream-row.notdisplayed .stream-name', 'Verona', 'Verona stream not shown after filtering');
    casper.test.assertSelectorHasText('.stream-row .stream-name', 'Waseemio', 'Waseemio stream exists after filtering');
    casper.test.assertSelectorDoesntHaveText('.stream-row.notdisplayed .stream-name', 'Waseemio', 'Waseemio stream shown after filtering');
});

common.then_log_out();

casper.run(function () {
    casper.test.done();
});
