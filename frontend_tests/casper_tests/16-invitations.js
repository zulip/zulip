var common = require('../casper_lib/common.js').common;

common.start_and_log_in();

casper.then(function () {
    var menu_selector = '#settings-dropdown';

    casper.test.info('Invite page');

    casper.waitUntilVisible(menu_selector, function () {
        casper.click(menu_selector);
        casper.then(function () {
            casper.click('a[href^="#invite"]');
            casper.test.assertUrlMatch(
                /^http:\/\/[^/]+\/#invite/,
                'URL suggests we are on invite users page');
            casper.waitUntilVisible('#invite-user.new-style.overlay', function () {
                casper.test.assertExists('#invite-user.new-style.overlay', 'Invite users page is active');
            });
        });
    });
});

casper.waitUntilVisible('#invite_user_form', function () {
    casper.fill('form#invite_user_form', {invitee_emails: 'foo@zulip.com'});
    casper.click('input[name="invite_as_admin"] ~ span');
    casper.click('#edit_streams_button');
    casper.test.assertVisible("#add_invite_stream_input", "Stream input visible");
    common.select_item_via_typeahead('#add_invite_stream_input', 'D', 'Denmark');
});

casper.then(function () {
    casper.waitUntilVisible("div .pill", function () {
        casper.click('#submit-invitation');
    });
});

casper.waitUntilVisible("#invite_status.alert.alert-success", function () {
    casper.test.assertExists('#invite_status.alert.alert-success', 'User invited');
});


casper.then(function () {
    var menu_selector = '#settings-dropdown';

    casper.test.info('Invitations page');

    casper.waitUntilVisible(menu_selector, function () {
        casper.click(menu_selector);
        casper.then(function () {
            casper.click('a[href^="#organization"]');
            casper.test.assertUrlMatch(
                /^http:\/\/[^/]+\/#organization/,
                'URL suggests we are on organisation settings page');
            casper.waitUntilVisible('#settings_page.new-style', function () {
                casper.test.assertExists('#settings_page.new-style', 'Settings page is active');
                casper.click('.admin[data-section="invites-list-admin"]');
            });
        });
    });
});

casper.waitUntilVisible("#admin_invites_table", function () {
    casper.test.assertExists('#admin_invites_table', 'Invitations page is active');
    casper.test.assertEval(function () {
        var table_cells = $("#admin_invites_table tr.invite_row td:nth-child(1)");
        for (var i = 0; i < table_cells.length; i += 1) {
            var td = table_cells[i];
            var email = td.children[0].textContent;
            if (email === "foo@zulip.com") {
                var title = td.children[1].title;
                return title === "Invited as administrator";
            }
        }
    }, 'User invited as admin');
});

common.then_log_out();

casper.run(function () {
    casper.test.done();
});
