add_dependencies({
    Handlebars: 'handlebars',
    templates: 'js/templates',
    i18n: 'i18next'
});

var i18n = global.i18n;
i18n.init({
    nsSeparator: false,
    keySeparator: false,
    interpolation: {
        prefix: "__",
        suffix: "__"
    },
    lng: 'en'
});

global.$ = require('jQuery');
var _ = global._;

// When writing these tests, the following command might be helpful:
// ./tools/get-handlebar-vars static/templates/*.handlebars

function render(template_name, args) {
    global.use_template(template_name);
    return global.templates.render(template_name, args);
}

(function test_handlebars_bug () {
    // There was a bug in 1.0.9 where identically structured
    // blocks get confused, so when foo is false, it still
    // renders the foo-is-true block.
    var s = '';
    s += '{{#if foo}}';
    s += '{{#if bar}}';
    s += 'a';
    s += '{{else}}';
    s += 'b';
    s += '{{/if}}';
    s += '{{else}}';
    s += '{{#if bar}}';
    s += 'c';
    s += '{{else}}';
    s += 'd';
    s += '{{/if}}';
    s += '{{/if}}';
    var template = global.Handlebars.compile(s);
    var output = template({});

    assert.equal(output, 'd'); // the buggy version would return 'b'
}());

(function actions_popover_content() {
    var args = {
        "message": {
            is_stream: true,
            id: "99",
            stream: "devel",
            subject: "testing",
            sender_full_name: "King Lear"
        },
        "can_edit_message": true,
        "can_mute_topic": true,
        "narrowed": true
    };

    var html = '<div style="height: 250px">';
    html += render('actions_popover_content', args);
    html += "</div>";
    var link = $(html).find("a.respond_button");
    assert.equal(link.text().trim(), 'Reply');
    global.write_test_output("actions_popover_content.handlebars", html);
}());

(function admin_tab() {
    var args = {
        realm_name: 'Zulip'
    };
    var html = render('admin_tab', args);
    var admin_features = ["admin_users_table", "admin_bots_table",
                          "admin_streams_table", "admin_deactivated_users_table"];
    _.each(admin_features, function (admin_feature) {
        assert.notEqual($(html).find("#" + admin_feature).length, 0);
    });
    assert.equal($(html).find("input.admin-realm-name").val(), 'Zulip');
    global.write_test_output("admin_tab.handlebars", html);
}());

(function admin_streams_list() {
    var html = '<table>';
    var streams = ['devel', 'trac', 'zulip'];
    _.each(streams, function (stream) {
        var args = {stream: {name: stream, invite_only: false}};
        html += render('admin_streams_list', args);
    });
    html += "</table>";
    var span = $(html).find(".stream_name:first");
    assert.equal(span.text(), "devel");
    global.write_test_output("admin_streams_list.handlebars", html);
}());

(function admin_user_list() {
    var html = '<table>';
    var users = ['alice', 'bob', 'carl'];
    _.each(users, function (user) {
        var args = {
            "user": {
                "is_active": true,
                "is_active_human": true,
                "email": user + '@zulip.com',
                "full_name": user
            }
        };
        html += render('admin_user_list', args);
    });
    html += "</table>";

    var button = $(html).find("button:first");
    assert.equal(button.text().trim(), "Deactivate");
    assert(button.hasClass("deactivate"));

    button = $(html).find("button:last");
    assert.equal(button.text().trim(), "Make admin");
    assert(button.hasClass("make-admin"));

    global.write_test_output("admin_user_list.handlebars", html);
}());

(function alert_word_settings_item() {
    var html = '<ul id="word-alerts">';
    var words = ['lunch', 'support'];
    _.each(words, function (word) {
        var args = {
            word: word
        };
        html += render('alert_word_settings_item', args);
    });
    html += "</ul>";
    global.write_test_output("alert_word_settings_item.handlebars", html);
    var li = $(html).find("li.alert-word-item:first");
    assert.equal(li.attr('data-word'),'lunch');
}());

(function announce_stream_docs() {
    var html = render('announce_stream_docs');
    global.write_test_output("announce_stream_docs.handlebars", html);
}());

(function bankruptcy_modal() {
    var args = {
        unread_count: 99
    };
    var html = render('bankruptcy_modal', args);
    global.write_test_output("bankruptcy_modal.handlebars", html);
    var count = $(html).find("p b");
    assert.equal(count.text(), 99);
}());

(function bot_avatar_row() {
    var html = '';
    html += '<div id="settings">';
    html += '<div id="bot-settings" class="settings-section">';
    html += '<div class="bot-settings-form">';
    html += '<ol id="bots_list" style="display: block">';
    var args = {
        "email": "hamlet@zulip.com",
        "api_key": "123456ABCD",
        "name": "Hamlet",
        "avatar_url": "/hamlet/avatar/url"
    };
    html += render('bot_avatar_row', args);
    html += '</ol>';
    html += '</div>';
    html += '</div>';
    html += '</div>';

    global.write_test_output("bot_avatar_row.handlebars", html);
    var img = $(html).find("img");
    assert.equal(img.attr('src'), '/hamlet/avatar/url');
}());

(function compose_invite_users() {
    var args = {
        email: 'hamlet@zulip.com',
        name: 'Hamlet'
    };
    var html = render('compose-invite-users', args);
    global.write_test_output("compose-invite-users.handlebars", html);
    var button = $(html).find("button:first");
    assert.equal(button.text(), "Subscribe");
}());

(function compose_all_everyone() {
    var args = {
        count: '101',
        name: 'all'
    };
    var html = render('compose_all_everyone', args);
    global.write_test_output("compose_all_everyone.handlebars", html);
    var button = $(html).find("button:first");
    assert.equal(button.text(), "YES");
    var error_msg = $(html).find('span.compose-all-everyone-msg').text().trim();
    assert.equal(error_msg, "Are you sure you want to message all 101 people in this stream?");
}());

(function compose_notification() {
    var args = {
        "note": "You sent a message to a muted topic.",
        "link_text": "Narrow to here",
        "link_msg_id": "99",
        "link_class": "compose_notification_narrow_by_subject"
    };
    var html = '<div  id="out-of-view-notification" class="notification-alert">';
    html += render('compose_notification', args);
    html += '</div>';
    global.write_test_output("compose_notification.handlebars", html);
    var a = $(html).find("a.compose_notification_narrow_by_subject");
    assert.equal(a.text(), "Narrow to here");
}());

(function email_address_hint() {
    var html = render('email_address_hint');
    global.write_test_output("email_address_hint.handlebars", html);
    var li = $(html).find("li:first");
    assert.equal(li.text(), 'The email will be forwarded to this stream');
}());

(function group_pms() {
    var args = {
        "group_pms": [
            {
                "fraction_present": 0.1,
                "emails": "alice@zulip.com,bob@zulip.com",
                "short_name": "Alice and Bob",
                "name": "Alice and Bob"
            }
        ]
    };
    var html = render('group_pms', args);
    global.write_test_output("group_pms.handlebars", html);

    var a = $(html).find("a:first");
    assert.equal(a.text(), 'Alice and Bob');
}());

(function invite_subscription() {
    var args = {
        streams: [
            {
                name: "devel"
            },
            {
                name: "social"
            }
        ]
    };
    var html = render('invite_subscription', args);
    global.write_test_output("invite_subscription.handlebars", html);

    var input = $(html).find("label:first");
    assert.equal(input.text().trim(), "devel");
}());

(function single_message() {
    var message =  {
        msg: {
            include_recipient: true,
            display_recipient: 'devel',
            subject: 'testing',
            is_stream: true,
            content: 'This is message one.',
            last_edit_timestr: '11:00',
            starred: true
        }
    };

    var html = render('single_message', message);
    html = '<div class="message_table focused_table" id="zfilt">' + html + '</div>';

    global.write_test_output("message.handlebars", html);

    var first_message = $(html).find("div.messagebox:first");

    var first_message_text = first_message.find(".message_content").text().trim();
    assert.equal(first_message_text, "This is message one.");

    var starred_title = first_message.find(".star span").attr("title");
    assert.equal(starred_title, "Unstar this message");
}());

(function message_group() {
    var messages = [
        {
            msg: {
                id: 1,
                match_content: 'This is message one.',
                starred: true,
                is_stream: true,
                content: 'This is message one.'
            },
            include_recipient: true,
            display_recipient: 'devel',
            last_edit_timestr: '11:00'
        },
        {
            msg: {
                content: 'This is message two.',
                match_content: 'This is message <span class="highlight">two</span>.',
                is_stream: true,
                unread: true,
                id: 2
            }
        }
    ];

    var groups = [
        {
            display_recipient: "support",
            is_stream: true,
            message_ids: [1, 2],
            message_containers: messages,
            show_date: '"<span id="timerender82">Jan&nbsp;07</span>"',
            subject: 'two messages',
            match_subject: '<span class="highlight">two</span> messages'
        }
    ];

    global.use_template('single_message'); // partial
    global.use_template('recipient_row'); // partial
    global.use_template('bookend'); // partial

    var html = render('message_group', {message_groups: groups, use_match_properties: true});

    var first_message_text = $(html).next('.recipient_row').find('div.messagebox:first .message_content').text().trim();
    assert.equal(first_message_text, "This is message one.");

    var last_message_html = $(html).next('.recipient_row').find('div.messagebox:last .message_content').html().trim();
    assert.equal(last_message_html, 'This is message <span class="highlight">two</span>.');

    var highlighted_subject_word = $(html).find('a.narrows_by_subject .highlight').text();
    assert.equal(highlighted_subject_word, 'two');

    global.write_test_output("message_group.handlebars", html);
}());

(function message_edit_form() {
    var args = {
        "topic": "lunch",
        "content": "Let's go to lunch!",
        "is_stream": true
    };
    var html = render('message_edit_form', args);
    global.write_test_output("message_edit_form.handlebars", html);

    var textarea = $(html).find("textarea.message_edit_content");
    assert.equal(textarea.text(), "Let's go to lunch!");
}());

(function message_info_popover_content() {
    var args = {
        message: {
            full_date_str: 'Monday',
            full_time_str: '12:00',
            sender_full_name: 'Alice Smith',
            sender_email: 'alice@zulip.com'
        },
        sent_by_uri: '/sent_by/uri',
        pm_with_uri: '/pm_with/uri'
    };

    var html = render('message_info_popover_content', args);
    global.write_test_output("message_info_popover_content.handlebars", html);

    var a = $(html).find("a.respond_personal_button");
    assert.equal(a.text().trim(), 'Send Alice Smith a private message');
}());


(function message_info_popover_title() {
    var args = {
        message: {
            is_stream: true,
            stream: 'devel'
        }
    };

    var html = render('message_info_popover_title', args);
    global.write_test_output("message_info_popover_title.handlebars", html);

    assert($(html).text().trim(), "Message to stream devel");
}());

(function new_stream_users() {
    var args = {
        users: [
            {
                email: 'lear@zulip.com',
                full_name: 'King Lear'
            },
            {
                email: 'othello@zulip.com',
                full_name: 'Othello the Moor'
            }
        ]
    };

    var html = render('new_stream_users', args);
    global.write_test_output("new_stream_users.handlebars", html);

    var label = $(html).find("label:first");
    assert.equal(label.text().trim(), 'King Lear (lear@zulip.com)');
}());

(function notification() {
    var args = {
        "content": "Hello",
        "gravatar_url": "/gravatar/url",
        "title": "You have a notification"
    };

    var html = render('notification', args);
    global.write_test_output("notification.handlebars", html);

    var title = $(html).find(".title");
    assert.equal(title.text().trim(), 'You have a notification');
}());

(function sidebar_subject_list() {
    var args = {
        want_show_more_topics_links: true,
        subjects: [
            {
                is_muted: false,
                topic_name: 'lunch',
                url: '/lunch/url',
                unread: 5
            },
            {
                is_muted: true,
                topic_name: 'dinner',
                url: '/dinner/url',
                is_zero: true
            }
        ]
    };

    var html = '';
    html += '<ul class="filters">';
    html += '<li>';
    html += '<ul class="expanded_subjects">';
    html += render('sidebar_subject_list', args);
    html += '</ul>';
    html += '</li>';
    html += '</ul>';

    global.write_test_output("sidebar_subject_list.handlebars", html);

    var li = $(html).find("li.expanded_subject:first");
    assert.equal(li.attr('data-name'), 'lunch');
}());

(function stream_member_list_entry() {
    var everyone_items = ["subscriber-name", "subscriber-email"];
    var admin_items = ["remove-subscriber-button"];

    // First, as non-admin.
    var html = render('stream_member_list_entry',
                      {name: "King Hamlet", email: "hamlet@zulip.com"});
    _.each(everyone_items, function (item) {
        assert.equal($(html).find("." + item).length, 1);
    });
    _.each(admin_items, function (item) {
        assert.equal($(html).find("." + item).length, 0);
    });

    // Now, as admin.
    html = render('stream_member_list_entry',
                  {name: "King Hamlet", email: "hamlet@zulip.com",
                   displaying_for_admin: true});
    _.each(everyone_items, function (item) {
        assert.equal($(html).find("." + item).length, 1);
    });
    _.each(admin_items, function (item) {
        assert.equal($(html).find("." + item).length, 1);
    });

    global.write_test_output("stream_member_list_entry.handlebars", html);
}());

(function stream_sidebar_actions() {
    var args = {
        stream: {
            color: 'red',
            name: 'devel',
            in_home_view: true,
            id: 55
        }
    };

    var html = render('stream_sidebar_actions', args);
    global.write_test_output("stream_sidebar_actions.handlebars", html);

    var li = $(html).find("li:first");
    assert.equal(li.text().trim(), 'Narrow to stream devel');
}());

(function stream_sidebar_row() {
    var args = {
        name: "devel",
        color: "red",
        dark_background: "maroon",
        uri: "/devel/uri",
        id: 999
    };

    var html = '<ul id="stream_filters">';
    html += render('stream_sidebar_row', args);
    html += '</ul>';

    global.write_test_output("stream_sidebar_row.handlebars", html);

    var swatch = $(html).find(".streamlist_swatch");
    assert.equal(swatch.attr('id'), 'stream_sidebar_swatch_999');
}());


(function subscription_table_body() {
    var args = {
        subscriptions: [
            {
                name: 'devel',
                subscribed: true,
                notifications: true,
                is_admin: true,
                render_subscribers: true,
                color: 'purple',
                invite_only: true,
                can_make_public: true,
                can_make_private: true, /* not logical, but that's ok */
                email_address: 'xxxxxxxxxxxxxxx@zulip.com',
                id: 888,
                in_home_view: true
            },
            {
                name: 'social',
                color: 'green',
                id: 999
            }
        ]
    };

    global.use_template('subscription'); // partial
    global.use_template('subscription_type'); // partial
    global.use_template('subscription_setting_icon'); // partial
    global.use_template('change_stream_privacy'); // partial
    var html = '';
    html += '<div id="subscriptions_table">';
    html += render('subscription_table_body', args);
    html += '</div>';

    global.write_test_output("subscription_table_body.handlebars", html);

    var span = $(html).find(".subscription_name:first");
    assert.equal(span.text(), 'devel');

    span = $(html).find(".admin-settings .sub_settings_title");
    assert.equal(span.text(), 'Administrator settings');

    var div = $(html).find(".subscription-type");
    assert(div.text().indexOf('invite-only stream') > 0);
}());


(function tab_bar() {
    var args = {
        tabs: [
            {
                cls: 'root',
                title: 'Home',
                hash: '#',
                data: 'home'
            },
            {
                cls: 'stream',
                title: 'Devel',
                hash: '/stream/uri',
                data: 'devel'
            }
        ]
    };

    var html = render('tab_bar', args);

    global.write_test_output("tab_bar.handlebars", html);

    var a = $(html).find("li:first");
    assert.equal(a.text().trim(), 'Home');
}());

(function topic_edit_form() {
    var html = render('topic_edit_form');

    global.write_test_output("topic_edit_form.handlebars", html);

    var button = $(html).find("button:first");
    assert.equal(button.find("i").attr("class"), 'icon-vector-ok');
}());

(function topic_sidebar_actions() {
    var args = {
        stream_name: 'social',
        topic_name: 'lunch',
        can_mute_topic: true
    };
    var html = render('topic_sidebar_actions', args);

    global.write_test_output("topic_sidebar_actions.handlebars", html);

    var a = $(html).find("a.narrow_to_topic");
    assert.equal(a.text().trim(), 'Narrow to topic lunch');

}());

(function subscribed_trailing_bookend() {
    var args = {
        bookend_content: "subscribed to stream",
        trailing: true,
        subscribed: true
    };
    var html = '';
    html += render('bookend', args);

    global.write_test_output("bookend.handlebars", html);
    assert.equal($(html).text().trim(), "subscribed to stream\n    \n        \n            \n            Unsubscribe");
}());

(function unsubscribed_trailing_bookend() {
    var args = {
        bookend_content: "Not subscribed to stream",
        trailing: true,
        subscribed: false
    };
    var html = '';
    html += render('bookend', args);

    global.write_test_output("bookend.handlebars", html);
    assert.equal($(html).text().trim(), 'Not subscribed to stream\n    \n        \n            \n            Subscribe');
}());

(function tutorial() {
    var tutorials = [
        'tutorial_home',
        'tutorial_message',
        'tutorial_reply',
        'tutorial_stream',
        'tutorial_subject',
        'tutorial_title'
    ];
    var html = '';
    _.each(tutorials, function (tutorial) {
        var args = {
            placement: 'left',
            title: 'Title'
        };
        html = render(tutorial, args);
        global.write_test_output(tutorial + '.handlebars', html);
    });
}());

(function user_presence_rows() {
    global.use_template('user_presence_row'); // partial
    var args = {
        users: [
            {
                "my_fullname": true,
                "type_desc": "Active",
                "type": "active",
                "num_unread": 0,
                "email": "lear@zulip.com",
                "name": "King Lear"
            },
            {
                "type_desc": "Away",
                "type": "away",
                "num_unread": 5,
                "email": "othello@zulip.com",
                "name": "Othello"
            }
        ]
    };

    var html = '';
    html += '<ul class="filters">';
    html += render('user_presence_rows', args);
    html += '</ul>';

    global.write_test_output("user_presence_rows.handlebars", html);

    var a = $(html).find("a.my_fullname:first");
    assert.equal(a.text(), 'King Lear');
}());

(function user_sidebar_actions() {
    var args = {
        email: 'hamlet@zulip.com',
        name: 'Hamlet'
    };

    var html = render('user_sidebar_actions', args);

    global.write_test_output("user_sidebar_actions.handlebars", html);

    var a = $(html).find("a.narrow_to_private_messages");
    assert.equal(a.text().trim(), 'Narrow to private messages with Hamlet');
}());

(function notification_docs() {
    var html = render('propagate_notification_change');
    global.write_test_output("propagate_notification_change.handlebars", html);

    var button_area = $(html).find(".propagate-notifications-controls");
    assert.equal(button_area.find(".yes_propagate_notifications").text().trim(), 'Yes');
    assert.equal(button_area.find(".no_propagate_notifications").text().trim(), 'No');
}());

(function settings_tab() {
    var page_param_checkbox_options = {
        stream_desktop_notifications_enabled: true,
        stream_sounds_enabled: true, desktop_notifications_enabled: true,
        sounds_enabled: true, enable_offline_email_notifications: true,
        enable_offline_push_notifications: true, enable_digest_emails: true,
        autoscroll_forever: true, default_desktop_notifications: true
    };
    var page_params = $.extend(page_param_checkbox_options, {
        fullname: "Alyssa P. Hacker", password_auth_enabled: true,
        avatar_url: "https://google.com",
        domain: "zulip.com"
    });

    var checkbox_ids = ["enable_stream_desktop_notifications",
                        "enable_stream_sounds", "enable_desktop_notifications",
                        "enable_sounds", "enable_offline_push_notifications",
                        "enable_digest_emails", "autoscroll_forever",
                        "default_desktop_notifications"];

    // Render with all booleans set to true.
    var html = render('settings_tab', {page_params: page_params});
    global.write_test_output("settings_tab.handlebars", html);

    // All checkboxes should be checked.
    _.each(checkbox_ids, function (checkbox) {
        assert.equal($(html).find("#" + checkbox).is(":checked"), true);
    });

    // Re-render with checkbox booleans set to false.
    _.each(page_param_checkbox_options, function (value, option) {
        page_params[option] = false;
    });

    html = render('settings_tab', {page_params: page_params});

    // All checkboxes should be unchecked.
    _.each(checkbox_ids, function (checkbox) {
        assert.equal($(html).find("#" + checkbox).is(":checked"), false);
    });

}());

(function admin_emoji_list() {
    global.use_template('admin_emoji_list');
    var args = {
        emoji: {
            "name": "MouseFace",
            "display_url": "http://emojipedia-us.s3.amazonaws.com/cache/46/7f/467fe69069c408e07517621f263ea9b5.png",
            "source_url": "http://emojipedia-us.s3.amazonaws.com/cache/46/7f/467fe69069c408e07517621f263ea9b5.png"
        }
    };

    var html = '';
    html += '<tbody id="admin_emoji_table">';
    html += render('admin_emoji_list', args);
    html += '</tbody>';

    global.write_test_output('admin_emoji_list.handlebars', html);

    var emoji_name = $(html).find('tr.emoji_row:first span.emoji_name');
    var emoji_url = $(html).find('tr.emoji_row:first span.emoji_image img');

    assert.equal(emoji_name.text(), 'MouseFace');
    assert.equal(emoji_url.attr('src'), 'http://emojipedia-us.s3.amazonaws.com/cache/46/7f/467fe69069c408e07517621f263ea9b5.png');
}());

// By the end of this test, we should have compiled all our templates.  Ideally,
// we will also have exercised them to some degree, but that's a little trickier
// to enforce.
global.make_sure_all_templates_have_been_compiled();
