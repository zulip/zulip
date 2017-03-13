add_dependencies({
    Handlebars: 'handlebars',
    templates: 'js/templates',
    i18n: 'i18next',
});

var i18n = global.i18n;
i18n.init({
    nsSeparator: false,
    keySeparator: false,
    interpolation: {
        prefix: "__",
        suffix: "__",
    },
    lng: 'fr',
    resources: {
        fr: {
            translation: {
                "Quote and reply": "French",
                "You'll receive notifications when a message arrives and Zulip isn't in focus or the message is offscreen.": "Some French text with Zulip",
            },
        },
    },
});

var jsdom = require("jsdom");
var window = jsdom.jsdom().defaultView;
global.$ = require('jquery')(window);

(function test_t_tag() {
    var args = {
        message: {
            is_stream: true,
            id: "99",
            stream: "devel",
            subject: "testing",
            sender_full_name: "King Lear",
        },
        can_edit_message: true,
        can_mute_topic: true,
        narrowed: true,
    };

    var html = '<div style="height: 250px">';
    html += global.render_template('actions_popover_content', args);
    html += "</div>";
    var link = $(html).find("a.respond_button");
    assert.equal(link.text().trim(), 'French');
    global.write_test_output("actions_popover_content.handlebars", html);
}());

(function test_tr_tag() {
    var args = {
        page_params: {
            fullname: "John Doe",
            password_auth_enabled: false,
            avatar_url: "http://example.com",
            left_side_userlist: false,
            twenty_four_hour_time: false,
            stream_desktop_notifications_enabled: false,
            stream_sounds_enabled: false,
            desktop_notifications_enabled: false,
            sounds_enabled: false,
            enable_offline_email_notifications: false,
            enable_offline_push_notifications: false,
            enable_online_push_notifications: false,
            enable_digest_emails: false,
            autoscroll_forever: false,
            default_desktop_notifications: false,
        },
    };

    var html = global.render_template('settings_tab', args);
    var div = $(html).find("div.notification-reminder");
    assert.equal(div.text().trim(), 'Some French text with Zulip');
    global.write_test_output("test_tr_tag settings", html);
}());
