var common = require('../casper_lib/common.js').common;

common.start_and_log_in();

casper.then(function () {
    var menu_selector = '#settings-dropdown';

    casper.test.info('Subscriptions page');

    casper.waitUntilVisible(menu_selector, function () {
        casper.click(menu_selector);
        casper.then(function () {
            casper.click('a[href^="#subscriptions"]');
            casper.test.assertUrlMatch(
                /^http:\/\/[^\/]+\/#subscriptions/,
                'URL suggests we are on subscriptions page');
            casper.test.assertExists('#subscriptions.tab-pane.active', 'Subscriptions page is active');
        });
    });
});

casper.waitForSelector('.sub_unsub_button.checked', function () {
    casper.test.assertExists('.sub_unsub_button.checked', 'Initial subscriptions loaded');
    casper.click('form#add_new_subscription input.btn');
});
casper.waitForSelector('#create_stream_button', function () {
     casper.test.assertTextExists('Create stream', 'Modal for specifying new stream users');
     casper.fill('form#stream_creation_form', {stream_name: 'Waseemio', stream_description: 'Oimeesaw'});
     casper.click('form#stream_creation_form button.btn.btn-primary');
});
casper.then(function () {
    casper.test.assertExists('#user-checkboxes [data-name="cordelia@zulip.com"]', 'Original user list contains Cordelia');
    casper.test.assertExists('#user-checkboxes [data-name="hamlet@zulip.com"]', 'Original user list contains King Hamlet');
});
casper.then(function () {
    casper.test.info("Filtering user list with keyword 'cor'");
    casper.fill('form#stream_creation_form', {user_list_filter: 'cor'});
});
casper.then(function () {
    casper.test.assertEquals(casper.visible('#user-checkboxes [data-name="cordelia@zulip.com"]'),
                             true,
                             "Cordelia is visible");
    casper.test.assertEquals(casper.visible('#user-checkboxes [data-name="hamlet@zulip.com"]'),
                             false,
                             "King Hamlet is not visible");
});
casper.then(function () {
    casper.test.info("Clearing user filter search box");
    casper.fill('form#stream_creation_form', {user_list_filter: ''});
});
casper.then(function () {
    casper.test.assertEquals(casper.visible('#user-checkboxes [data-name="cordelia@zulip.com"]'),
                             true,
                             "Cordelia is visible again");
    casper.test.assertEquals(casper.visible('#user-checkboxes [data-name="hamlet@zulip.com"]'),
                             true,
                             "King Hamlet is visible again");
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
    casper.fill('form#add_new_subscription', {stream_name: 'WASeemio'});
    casper.click('form#add_new_subscription input.btn');
});
casper.waitForText('Already subscribed', function () {
    casper.test.assertTextExists('Already subscribed', "Can't subscribe twice to a stream");
    casper.fill('form#add_new_subscription', {stream_name: '  '});
    casper.click('form#add_new_subscription input.btn');
    casper.fill('form#stream_creation_form', {stream_name: '  '});
    casper.click('form#stream_creation_form button.btn.btn-primary');
});
casper.waitForText('A stream needs to have a name', function () {
    casper.test.assertTextExists('A stream needs to have a name', "Can't create a stream with an empty name");
    casper.click('form#stream_creation_form button.btn.btn-default');
    casper.fill('form#add_new_subscription', {stream_name: '  '});
    casper.click('form#add_new_subscription input.btn');
    casper.fill('form#stream_creation_form', {stream_name: 'Waseemio'});
    casper.click('form#stream_creation_form button.btn.btn-primary');
});
casper.waitForText('A stream with this name already exists', function () {
    casper.test.assertTextExists('A stream with this name already exists', "Can't create a stream with a duplicate name");
    casper.test.info('Streams should be filtered when typing in the create box');
    casper.click('form#stream_creation_form button.btn.btn-default');
});
casper.waitForText('Filter by stream name', function () {
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
