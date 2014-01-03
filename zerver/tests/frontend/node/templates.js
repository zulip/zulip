var assert = require('assert');

add_dependencies({
    Handlebars: 'handlebars',
    _: 'third/underscore/underscore',
    templates: 'js/templates'
});

global.$ = require('jquery');
var _ = global._;

// When writing these tests, the following command might be helpful:
// ./tools/get-handlebar-vars static/templates/*.handlebars

function render(template_name, args) {
    global.use_template(template_name);
    return global.templates.render(template_name, args);
}

(function actions_popover_content() {
    var args = {
        "stream_subject_uri": "/stream/subject/uri",
        "message": {
            is_stream: true,
            id: "99",
            stream: "devel",
            subject: "testing",
            sender_full_name: "King Lear"
        },
        "can_edit_message": true,
        "conversation_time_uri": "/conversation/time/uri",
        "can_mute_topic": true,
        "narrowed": true,
        "near_time_uri": "/near/time/uri"
    };

    var html = '<div style="height: 250px">';
    html += render('actions_popover_content', args);
    html += "</div>";
    var link = $(html).find("a.popover_narrow_by_subject_button");
    assert.equal(link.attr('href'), '/stream/subject/uri');
    global.write_test_output("actions_popover_content.handlebars", html);
}());

(function admin_streams_list() {
    var html = '<table>';
    var streams = ['devel', 'trac', 'zulip'];
    _.each(streams, function (stream) {
        var args = {stream: {name: stream}};
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
                "email": user + '@zulip.com',
                "full_name": user
            }
        };
        html += render('admin_user_list', args);
    });
    html += "</table>";
    var button = $(html).find("button:first");
    assert.equal(button.text().trim(), "Deactivate");
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

(function message() {
    var messages = [
        {
            include_recipient: true,
            display_recipient: 'devel',
            subject: 'testing',
            is_stream: true,
            content: 'This is message one.',
            last_edit_timestr: '11:00',
            starred: true
        },
        {
            content: 'This is message two.',
            is_stream: true,
            unread: true
        }
    ];
    var args = {
        messages: messages,
        include_layout_row: true
    };
    var html = render('message', args);
    html = '<div class="message_table focused_table" id="zfilt">' + html + '</div>';

    global.write_test_output("message.handlebars", html);

    var first_message = $(html).find("div.messagebox:first");

    var first_message_text = first_message.find(".message_content").text().trim();
    assert.equal(first_message_text, "This is message one.");

    var starred_title = first_message.find(".star span").attr("title");
    assert.equal(starred_title, "Unstar this message");
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

(function notification_docs() {
    var html = render('notification_docs');
    global.write_test_output("notification_docs.handlebars", html);

    var title = $(html).find("li:first");
    assert.equal(title.text().trim(), 'a private message');
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

    span = $(html).find(".rename-stream .sub_settings_title");
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
    assert.equal(button.text().trim(), 'Save');

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

(function trailing_bookend() {
    var args = {
        trailing_bookend: "subscribed to stream"
    };
    var html = '';
    html += '<table>';
    html += render('trailing_bookend', args);
    html += '</table>';

    global.write_test_output("trailing_bookend.handlebars", html);

    var td = $(html).find("td:first");
    assert.equal(td.text().trim(), 'subscribed to stream');
}());

(function tutorial() {
    var tutorials = [
        'tutorial_home',
        'tutorial_message',
        'tutorial_private',
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

