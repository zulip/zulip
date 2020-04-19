set_global('Handlebars', global.make_handlebars());
zrequire('templates');

// We download our translations in `page_params` (which
// are for the user's chosen language), so we simulate
// that here for the tests.
set_global('page_params', {
    translation_data: {
        "Quote and reply": "French translation",
        "Notification triggers": "Some French text",
    },
});

// All of our other tests stub out i18n activity;
// here we do a quick sanity check on the engine itself.
// We use `i18n.js` to initialize `i18next` and
// to set `i18n` to `i18next` on the global namespace
// for `templates.js`.
zrequire('i18n');

run_test('t_tag', () => {
    const args = {
        message: {
            is_stream: true,
            id: "99",
            stream: "devel",
            subject: "testing",
            sender_full_name: "King Lear",
        },
        should_display_quote_and_reply: true,
        can_edit_message: true,
        can_mute_topic: true,
        narrowed: true,
    };

    const html = require('../../static/templates/actions_popover_content.hbs')(args);
    assert(html.indexOf("French translation") > 0);
});

run_test('tr_tag', () => {
    const args = {
        page_params: {
            full_name: "John Doe",
            password_auth_enabled: false,
            avatar_url: "http://example.com",
            left_side_userlist: false,
            twenty_four_hour_time: false,
            enable_stream_desktop_notifications: false,
            enable_stream_push_notifications: false,
            enable_stream_audible_notifications: false,
            enable_desktop_notifications: false,
            enable_sounds: false,
            enable_offline_email_notifications: false,
            enable_offline_push_notifications: false,
            enable_online_push_notifications: false,
            enable_digest_emails: false,
        },
    };

    const html = require('../../static/templates/settings_tab.hbs')(args);
    assert(html.indexOf('Some French text') > 0);
});



/* =================== PLURALIZATION =================== */

// Plurals for three language codes are tested here
// with the i18next library: 'en', 'fr', and 'ar'

// Test for 'en' language code plural translations
run_test('en_pluralization_test', () => {
    // i18n 'en' setup: stubbing resource file's translation data and changing language
    i18n.addResourceBundle('en', 'translation', {
        key: 'hello world',
        interpolate: 'value is __val__',
        child: '__count__ child',
        child_plural: '__count__ children',
        'Users can now edit topics for all their messages, and the content of messages which are less than __count__ minutes old.': 'Users can now edit topics for all their messages, and the content of messages which are less than __count__ minute old.',
        'Users can now edit topics for all their messages, and the content of messages which are less than __count__ minutes old._plural': 'Users can now edit topics for all their messages, and the content of messages which are less than __count__ minutes old.',
    });
    i18n.changeLanguage('en');
    assert.equal(i18n.language, 'en');

    // testing translations
    assert.equal(i18n.t('key'), 'hello world'); // basic test
    assert.equal(i18n.t('interpolate', {val: 10}), 'value is 10'); // basic test
    assert.equal(i18n.t('child', {count: 0}), '0 children');
    assert.equal(i18n.t('child', {count: 1}), '1 child');
    assert.equal(i18n.t('child', {count: 2}), '2 children');
    assert.equal(i18n.t('child', {count: 100}), '100 children');

    // testing the proposed key in https://github.com/zulip/zulip/issues/1286
    assert.equal(i18n.t('Users can now edit topics for all their messages, and the content of messages which are less than __count__ minutes old.', {count: 0}), 'Users can now edit topics for all their messages, and the content of messages which are less than 0 minutes old.'); // plural 'minutes' used for count of 0
    assert.equal(i18n.t('Users can now edit topics for all their messages, and the content of messages which are less than __count__ minutes old.', {count: 1}), 'Users can now edit topics for all their messages, and the content of messages which are less than 1 minute old.'); // singular 'minute' used for count of 1
    assert.equal(i18n.t('Users can now edit topics for all their messages, and the content of messages which are less than __count__ minutes old.', {count: 2}), 'Users can now edit topics for all their messages, and the content of messages which are less than 2 minutes old.');
    assert.equal(i18n.t('Users can now edit topics for all their messages, and the content of messages which are less than __count__ minutes old.', {count: 100}), 'Users can now edit topics for all their messages, and the content of messages which are less than 100 minutes old.');
});


// Test for 'fr' language code plural translations
run_test('fr_pluralization_test', () => {
    // i18n 'fr' setup: stubbing resource file's translation data and changing language
    i18n.addResourceBundle('fr', 'translation', {
        enfant: '__count__ enfant',
        enfant_plural: '__count__ enfants',
    });
    i18n.changeLanguage('fr');
    assert.equal(i18n.language, 'fr');

    // testing translations
    assert.equal(i18n.t('enfant', {count: 0}), '0 enfant'); // 'fr' uses singular key for a count of 0, unlike 'en'
    assert.equal(i18n.t('enfant', {count: 1}), '1 enfant');
    assert.equal(i18n.t('enfant', {count: 2}), '2 enfants');
    assert.equal(i18n.t('enfant', {count: 10}), '10 enfants');
});


// Test for 'ar' language code plural translations
run_test('ar_pluralization_test', () => {
    // i18n 'en' setup: stubbing resource file's translation data and changing language
    i18n.addResourceBundle('ar', 'translation', {
        key_0: 'zero',
        key_1: 'singular',
        key_2: 'two',
        key_3: 'few',
        key_4: 'many',
        key_5: 'other',
    });
    i18n.changeLanguage('ar');
    assert.equal(i18n.language, 'ar');

    // testing translations
    assert.equal(i18n.t('key', {count: 0}), 'zero');
    assert.equal(i18n.t('key', {count: 1}), 'singular');
    assert.equal(i18n.t('key', {count: 2}), 'two');
    assert.equal(i18n.t('key', {count: 3}), 'few');
    assert.equal(i18n.t('key', {count: 4}), 'few');
    assert.equal(i18n.t('key', {count: 5}), 'few');
    assert.equal(i18n.t('key', {count: 11}), 'many');
    assert.equal(i18n.t('key', {count: 99}), 'many');
    assert.equal(i18n.t('key', {count: 100}), 'other');
});
