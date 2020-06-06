var common = require('../casper_lib/common.js');

common.start_and_log_in();

common.manage_organization();

function submit_notifications_stream_settings() {
    casper.then(function () {
        casper.waitUntilVisible('#org-submit-notifications[data-status="unsaved"]', function () {
            casper.test.assertSelectorHasText('#org-submit-notifications', 'Save');
        });
    });
    casper.then(function () {
        casper.click('#org-submit-notifications');
    });
}

// Test changing notifications stream
casper.then(function () {
    casper.test.info('Changing notifications stream to Verona by filtering with "verona"');
    casper.click("#realm_notifications_stream_id_widget button.dropdown-toggle");
    casper.waitUntilVisible('#realm_notifications_stream_id_widget ul.dropdown-menu', function () {
        casper.sendKeys('#realm_notifications_stream_id_widget  .dropdown-search > input[type=text]', 'verona');
        casper.click("#realm_notifications_stream_id_widget .dropdown-list-body > li:nth-of-type(1)");
    });
});

submit_notifications_stream_settings();

casper.then(function () {
    casper.waitUntilVisible('#org-submit-notifications[data-status="saved"]', function () {
        casper.test.assertSelectorHasText('#org-submit-notifications', 'Saved');
    });
    casper.waitWhileVisible('#org-submit-notifications');
});

casper.then(function () {
    casper.click("#realm_notifications_stream_id_widget  .dropdown_list_reset_button");
});

submit_notifications_stream_settings();

casper.then(function () {
    casper.waitUntilVisible('#org-submit-notifications[data-status="saved"]', function () {
        casper.test.assertSelectorHasText('#org-submit-notifications', 'Saved');
    });
    casper.waitWhileVisible('#org-submit-notifications');
});

// Test changing signup notifications stream
casper.then(function () {
    casper.test.info('Changing signup notifications stream to Verona by filtering with "verona"');
    casper.click("#id_realm_signup_notifications_stream_id > button.dropdown-toggle");
    casper.waitUntilVisible('#realm_signup_notifications_stream_id_widget  ul.dropdown-menu', function () {
        casper.sendKeys('#realm_signup_notifications_stream_id_widget  .dropdown-search > input[type=text]', 'verona');
        casper.click("#realm_signup_notifications_stream_id_widget  .dropdown-list-body li.list_item");
    });
});

submit_notifications_stream_settings();

casper.then(function () {
    casper.waitUntilVisible('#org-submit-notifications[data-status="saved"]', function () {
        casper.test.assertSelectorHasText('#org-submit-notifications', 'Saved');
    });
    casper.waitWhileVisible('#org-submit-notifications');
});

casper.then(function () {
    casper.click("#realm_signup_notifications_stream_id_widget  .dropdown_list_reset_button");
});

submit_notifications_stream_settings();

casper.then(function () {
    casper.waitUntilVisible('#org-submit-notifications[data-status="saved"]', function () {
        casper.test.assertSelectorHasText('#org-submit-notifications', 'Saved');
    });
    casper.waitWhileVisible('#org-submit-notifications');
});

// Test permissions setting
casper.then(function () {
    casper.click("li[data-section='organization-permissions']");
});

function submit_permissions_change() {
    casper.test.assertSelectorHasText('#org-submit-other-permissions', "Save");
    casper.click('#org-submit-other-permissions');
}

// Test setting create streams policy to 'admins only'.
casper.then(function () {
    casper.test.info("Test setting create streams policy to 'admins only'.");
    casper.waitUntilVisible("#id_realm_create_stream_policy", function () {
        // by_admins_only
        casper.evaluate(function () {
            $("#id_realm_create_stream_policy").val(2).change();
        });
        submit_permissions_change();
    });
});

casper.then(function () {
    // Test that save worked.
    casper.waitUntilVisible('#org-submit-other-permissions[data-status="saved"]', function () {
        casper.test.assertSelectorHasText('#org-submit-other-permissions', 'Saved');
    });
    casper.waitWhileVisible('#org-submit-notifications');
});

// Test setting create streams policy to 'members and admins'.
casper.then(function () {
    casper.test.info("Test setting create streams policy to 'members and admins'.");
    casper.waitUntilVisible("#id_realm_create_stream_policy", function () {
        // by_members
        casper.evaluate(function () {
            $("#id_realm_create_stream_policy").val(1).change();
        });
        submit_permissions_change();
    });
});

casper.then(function () {
    // Test that save worked.
    casper.waitUntilVisible('#org-submit-other-permissions[data-status="saved"]', function () {
        casper.test.assertSelectorHasText('#org-submit-other-permissions', 'Saved');
    });
    casper.waitWhileVisible('#org-submit-notifications');
});

// Test setting create streams policy to 'full members'.
casper.then(function () {
    casper.test.info("Test setting create streams policy to 'waiting period.");
    casper.waitUntilVisible("#id_realm_create_stream_policy", function () {
        // by_full_members
        casper.evaluate(function () {
            $("#id_realm_create_stream_policy").val(3).change();
        });
        submit_permissions_change();
    });
});

casper.then(function () {
    // Test that save worked.
    casper.waitUntilVisible('#org-submit-other-permissions[data-status="saved"]', function () {
        casper.test.assertSelectorHasText('#org-submit-other-permissions', 'Saved');
    });
    casper.waitWhileVisible('#org-submit-notifications');
});

// Test setting invite to streams policy to 'admins only'.
casper.then(function () {
    casper.test.info("Test setting invite to streams policy to 'admins only'.");
    casper.waitUntilVisible("#id_realm_invite_to_stream_policy", function () {
        // by_admins_only
        casper.evaluate(function () {
            $("#id_realm_invite_to_stream_policy").val(2).change();
        });
        submit_permissions_change();
    });
});

casper.then(function () {
    // Test that save worked.
    casper.waitUntilVisible('#org-submit-other-permissions[data-status="saved"]', function () {
        casper.test.assertSelectorHasText('#org-submit-other-permissions', 'Saved');
    });
    casper.waitWhileVisible('#org-submit-notifications');
});

// Test setting invite to streams policy to 'members and admins'.
casper.then(function () {
    casper.test.info("Test setting invite to streams policy to 'members and admins'.");
    casper.waitUntilVisible("#id_realm_invite_to_stream_policy", function () {
        // by_members
        casper.evaluate(function () {
            $("#id_realm_invite_to_stream_policy").val(1).change();
        });
        submit_permissions_change();
    });
});

casper.then(function () {
    // Test that save worked.
    casper.waitUntilVisible('#org-submit-other-permissions[data-status="saved"]', function () {
        casper.test.assertSelectorHasText('#org-submit-other-permissions', 'Saved');
    });
    casper.waitWhileVisible('#org-submit-notifications');
});

// Test setting invite to streams policy to 'full members'.
casper.then(function () {
    casper.test.info("Test setting invite to streams policy to 'waiting period'.");
    casper.waitUntilVisible("#id_realm_invite_to_stream_policy", function () {
        // by_full_members
        casper.evaluate(function () {
            $("#id_realm_invite_to_stream_policy").val(3).change();
        });
        submit_permissions_change();
    });
});

casper.then(function () {
    // Test that save worked.
    casper.waitUntilVisible('#org-submit-other-permissions[data-status="saved"]', function () {
        casper.test.assertSelectorHasText('#org-submit-other-permissions', 'Saved');
    });
    casper.waitWhileVisible('#org-submit-notifications');
});

// Test setting new user threshold to three days.
casper.then(function () {
    casper.test.info("Test setting new user threshold to three days.");
    casper.waitUntilVisible("#id_realm_waiting_period_setting", function () {
        casper.evaluate(function () {
            $("#id_realm_waiting_period_setting").val("three_days").change();
        });
        submit_permissions_change();
    });
});

casper.then(function () {
    // Test that save worked.
    casper.waitUntilVisible('#org-submit-other-permissions[data-status="saved"]', function () {
        casper.test.assertSelectorHasText('#org-submit-other-permissions', 'Saved');
        casper.test.assertNotVisible('#id_realm_waiting_period_threshold');
    });
    casper.waitWhileVisible('#org-submit-notifications');
});

// Test setting new user threshold to N days.
casper.then(function () {
    casper.test.info("Test setting new user threshold to N days.");
    casper.waitUntilVisible("#id_realm_waiting_period_setting", function () {
        casper.evaluate(function () {
            $("#id_realm_waiting_period_setting").val("custom_days").change();
        });
        submit_permissions_change();
    });
});

casper.then(function () {
    // Test that save worked.
    casper.waitUntilVisible('#org-submit-other-permissions[data-status="saved"]', function () {
        casper.test.assertSelectorHasText('#org-submit-other-permissions', 'Saved');
        casper.test.assertVisible('#id_realm_waiting_period_threshold');
    });
    casper.waitWhileVisible('#org-submit-notifications');
});

casper.then(function () {
    // Test custom realm emoji
    casper.click("li[data-section='emoji-settings']");
    casper.waitUntilVisible('.admin-emoji-form', function () {
        casper.fill('form.admin-emoji-form', {
            name: 'new mouse face',
            emoji_file_input: 'static/images/logo/zulip-icon-128x128.png',
        }, true);
    });
});

casper.then(function () {
    casper.waitUntilVisible('div#admin-emoji-status', function () {
        casper.test.assertSelectorHasText('div#admin-emoji-status', 'Custom emoji added!');
    });
});

casper.then(function () {
    casper.waitUntilVisible('tr#emoji_new_mouse_face', function () {
        casper.test.assertSelectorHasText('tr#emoji_new_mouse_face .emoji_name', 'new mouse face');
        casper.test.assertExists('tr#emoji_new_mouse_face img');
        casper.click('tr#emoji_new_mouse_face button.delete');
    });
});

casper.then(function () {
    casper.waitWhileVisible('tr#emoji_new_mouse_face', function () {
        casper.test.assertDoesntExist('tr#emoji_new_mouse_face');
    });
});

var stream_name = "Scotland";
function get_suggestions(str) {
    casper.then(function () {
        casper.evaluate(function (str) {
            $('.create_default_stream')
                .focus()
                .val(str)
                .trigger($.Event('keyup', { which: 0 }));
        }, str);
    });
}

function select_from_suggestions(item) {
    casper.then(function () {
        casper.evaluate(function (item) {
            var tah = $('.create_default_stream').data().typeahead;
            tah.mouseenter({
                currentTarget: $('.typeahead:visible li:contains("' + item + '")')[0],
            });
            tah.select();
        }, {item: item});
        casper.click(".default-stream-form #do_submit_stream");
    });
}

// Test default stream creation and addition
casper.then(function () {
    casper.click("li[data-section='default-streams-list']");
    casper.waitUntilVisible(".create_default_stream", function () {
        // It matches with all the stream names which has 'O' as a substring (Rome, Scotland, Verona
        // etc). 'O' is used to make sure that it works even if there are multiple suggestions.
        // Uppercase 'O' is used instead of the lowercase version to make sure that the suggestions
        // are case insensitive.
        get_suggestions("O");
        select_from_suggestions(stream_name);
    });
});

casper.then(function () {
    var stream_id = common.get_stream_id(stream_name);
    var row = ".default_stream_row[data-stream-id='" + stream_id + "']";
    casper.waitUntilVisible(row, function () {
        casper.test.assertSelectorHasText(row + ' .default_stream_name', stream_name);
        casper.click(row + ' button.remove-default-stream');
        casper.waitWhileVisible(row, function () {
            casper.test.assertDoesntExist(row);
        });
    });
});

// TODO: Test stream deletion

// Test uploading realm icon image
casper.then(function () {
    casper.click("li[data-section='organization-profile']");
    var selector = 'img#realm-icon-block[src^="https://secure.gravatar.com/avatar/"]';
    casper.waitUntilVisible(selector, function () {
        casper.test.assertEqual(casper.visible('#realm_icon_delete_button'), false);
        // Hack: Rather than submitting the form, we just fill the
        // form and then trigger a click event by clicking the button.
        casper.fill('form.admin-realm-form', {
            realm_icon_file_input: 'static/images/logo/zulip-icon-128x128.png',
        }, false);
        casper.click("#realm_icon_upload_button");
        casper.waitWhileVisible("#icon-spinner-background", function () {
            casper.test.assertExists('img#realm-icon-block[src^="/user_avatars/2/realm/icon.png?version=2"]');
            casper.test.assertEqual(casper.visible('#realm_icon_delete_button'), true);
        });
    });
});

// Test deleting realm icon image
casper.then(function () {
    casper.click("li[data-section='organization-profile']");
    casper.click("#realm_icon_delete_button");
    casper.test.assertEqual(casper.visible('#realm_icon_delete_button'), true);
    casper.waitWhileVisible('#realm_icon_delete_button', function () {
        casper.test.assertExists('img#realm-icon-block[src^="https://secure.gravatar.com/avatar/"]');
        casper.test.assertEqual(casper.visible('#realm_icon_delete_button'), false);
    });
});


casper.then(function () {
    casper.click("li[data-section='organization-settings']");
    casper.waitUntilVisible('#id_realm_default_language', function () {
        casper.test.info("Changing realm default language");
        casper.evaluate(function () {
            $('#id_realm_default_language').val('de').change();
        });
        casper.test.assertSelectorHasText('#org-submit-user-defaults', "Save");
        casper.click('#org-submit-user-defaults');
    });
});

casper.then(function () {
    casper.waitUntilVisible('#org-submit-user-defaults[data-status="saved"]', function () {
        casper.test.assertSelectorHasText('#org-submit-user-defaults',
                                          'Saved');
    });
});

// Test authentication methods setting
casper.then(function () {
    casper.click("li[data-section='auth-methods']");
    casper.waitUntilVisible(".method_row[data-method='Google'] input[type='checkbox'] + span", function () {
        casper.click(".method_row[data-method='Google'] input[type='checkbox'] + span");
        casper.test.assertSelectorHasText('#org-submit-auth_settings', "Save");
        casper.click('#org-submit-auth_settings');
    });
});

casper.then(function () {
    // Leave the page and return
    casper.click('#settings-dropdown');
    casper.click('a[href^="#streams"]');
    casper.click('#settings-dropdown');
    casper.click('a[href^="#organization"]');
    casper.click("li[data-section='auth-methods']");

    casper.waitUntilVisible(".method_row[data-method='Google'] input[type='checkbox'] + span", function () {
        // Test Setting was saved
        casper.test.assertEval(function () {
            return !document.querySelector(".method_row[data-method='Google'] input[type='checkbox']").checked;
        });
    });
});

common.then_log_out();

casper.run(function () {
    casper.test.done();
});
