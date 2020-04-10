var common = require('../casper_lib/common.js');

common.start_and_log_in();

common.manage_organization();

// Test custom profile fields
casper.test.info("Testing custom profile fields");
casper.thenClick("li[data-section='profile-field-settings']");
casper.then(function () {
    casper.waitUntilVisible('.admin-profile-field-form', function () {
        casper.fill('form.admin-profile-field-form', {
            name: 'Teams',
            field_type: '1',
        });
        casper.click("form.admin-profile-field-form button[type='submit']");
    });
});

casper.then(function () {
    casper.waitUntilVisible('#admin-add-profile-field-status img', function () {
        casper.test.assertSelectorHasText('div#admin-add-profile-field-status', 'Saved');
        common.wait_for_text('.profile-field-row span.profile_field_name', 'Teams', function () {
            casper.test.assertSelectorHasText('.profile-field-row span.profile_field_name', 'Teams');
            casper.test.assertSelectorHasText('.profile-field-row span.profile_field_type', 'Short text');
            casper.click('.profile-field-row button.open-edit-form');
        });
    });
});

casper.then(function () {
    casper.waitUntilVisible('tr.profile-field-form form', function () {
        casper.fill('tr.profile-field-form form.name-setting', {
            name: 'team',
        });
        casper.click('tr.profile-field-form button.submit');
    });
});

casper.then(function () {
    casper.waitUntilVisible('#admin-profile-field-status img', function () {
        casper.test.assertSelectorHasText('div#admin-profile-field-status', 'Saved');
    });
    casper.waitForSelectorTextChange('.profile-field-row span.profile_field_name', function () {
        casper.test.assertSelectorHasText('.profile-field-row span.profile_field_name', 'team');
        casper.test.assertSelectorHasText('.profile-field-row span.profile_field_type', 'Short text');
        casper.click('.profile-field-row button.delete');
    });
});

casper.then(function () {
    casper.waitUntilVisible('#admin-profile-field-status img', function () {
        casper.test.assertSelectorHasText('div#admin-profile-field-status', 'Saved');
    });
});


common.then_log_out();

casper.run(function () {
    casper.test.done();
});
