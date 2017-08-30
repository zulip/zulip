set_global('page_params', {realm_emoji: {
  burrito: {display_url: '/static/generated/emoji/images/emoji/burrito.png',
            source_url: '/static/generated/emoji/images/emoji/burrito.png'},
}});

add_dependencies({
    Handlebars: 'handlebars',
    templates: 'js/templates',
    emoji_codes: 'generated/emoji/emoji_codes.js',
    emoji: 'js/emoji',
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
    lng: 'en',
});

var jsdom = require("jsdom");
var window = jsdom.jsdom().defaultView;
global.$ = require('jquery')(window);
var _ = global._;

// When writing these tests, the following command might be helpful:
// ./tools/get-handlebar-vars static/templates/*.handlebars

function render(template_name, args) {
    return global.render_template(template_name, args);
}

(function test_finding_partials() {
    var fns = global.find_included_partials('settings_tab');
    assert.deepEqual(fns, [
        'account-settings',
        'display-settings',
        'notification-settings',
        'bot-settings',
        'alert-word-settings',
        'attachments-settings',
        'muted-topics-settings',
        'ui-settings',
    ]);
}());

(function test_handlebars_bug() {
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
    html += render('actions_popover_content', args);
    html += "</div>";
    var link = $(html).find("a.respond_button");
    assert.equal(link.text().trim(), 'Quote and reply');
    global.write_handlebars_output("actions_popover_content", html);
}());

(function admin_realm_domains_list() {
    var html = "<table>";
    var args = {
        realm_domain: {
            domain: 'zulip.org',
            allow_subdomains: true,
        },
    };
    html += render("admin-realm-domains-list", args);
    html += "</table>";

    var button = $(html).find('.button');
    var domain = $(html).find('.domain');
    var row = button.closest('tr');
    var subdomains_checkbox = row.find('.allow-subdomains');

    assert.equal(button.text().trim(), "Remove");
    assert(button.hasClass("delete_realm_domain"));
    assert.equal(domain.text(), "zulip.org");

    assert.equal(subdomains_checkbox.prop('checked'), true);

    global.write_handlebars_output("admin-realm-domains-list", html);
}());

(function admin_realm_dropdown_stream_list() {
    var html = "<ul>";
    var args = {
        stream: {
            name: "Italy",
            subscriber_count: 9,
            stream_id: 18,
        },
    };
    html += render("admin-realm-dropdown-stream-list", args);
    html += "</ul>";

    var link = $(html).find("a");
    var list_item = $(html).find("li");

    assert.equal(link.text().trim(), "Italy");
    assert(list_item.hasClass("stream_name"));
    assert.equal(list_item.attr("data-stream-id"), "18");

    global.write_handlebars_output("admin-realm-dropdown-stream-list", html);
}());

(function admin_default_streams_list() {
    var html = '<table>';
    var streams = ['devel', 'trac', 'zulip'];

    // When the logged in user is admin
    _.each(streams, function (stream) {
        var args = {stream: {name: stream, invite_only: false},
                    can_modify: true,
                    };
        html += render('admin_default_streams_list', args);
    });
    html += "</table>";
    var span = $(html).find(".default_stream_name:first");
    assert.equal(span.text(), "devel");

    // When the logged in user is not admin
    html = '<table>';
    _.each(streams, function (stream) {
        var args = {stream: {name: stream, invite_only: false},
                    can_modify: false,
                    };
        html += render('admin_default_streams_list', args);
    });
    html += "</table>";
    span = $(html).find(".default_stream_name:first");
    assert.equal(span.text(), "devel");
    global.write_handlebars_output("admin_default_streams_list", html);
}());

(function admin_emoji_list() {
    var args = {
        emoji: {
            name: "MouseFace",
            display_url: "http://emojipedia-us.s3.amazonaws.com/cache/46/7f/467fe69069c408e07517621f263ea9b5.png",
            source_url: "http://emojipedia-us.s3.amazonaws.com/cache/46/7f/467fe69069c408e07517621f263ea9b5.png",
        },
    };

    var html = '';
    html += '<tbody id="admin_emoji_table">';
    html += render('admin_emoji_list', args);
    html += '</tbody>';

    global.write_handlebars_output('admin_emoji_list', html);

    var emoji_name = $(html).find('tr.emoji_row:first span.emoji_name');
    var emoji_url = $(html).find('tr.emoji_row:first span.emoji_image img');

    assert.equal(emoji_name.text(), 'MouseFace');
    assert.equal(emoji_url.attr('src'), 'http://emojipedia-us.s3.amazonaws.com/cache/46/7f/467fe69069c408e07517621f263ea9b5.png');
}());

(function admin_filter_list() {

    // When the logged in user is admin
    var args = {
        filter: {
            pattern: "#(?P<id>[0-9]+)",
            url_format_string: "https://trac.example.com/ticket/%(id)s",
        },
        can_modify: true,
    };

    var html = '';
    html += '<tbody id="admin_filters_table">';
    html += render('admin_filter_list', args);
    html += '</tbody>';

    var filter_pattern = $(html).find('tr.filter_row:first span.filter_pattern');
    var filter_format = $(html).find('tr.filter_row:first span.filter_url_format_string');

    assert.equal(filter_pattern.text(), '#(?P<id>[0-9]+)');
    assert.equal(filter_format.text(), 'https://trac.example.com/ticket/%(id)s');

    // When the logged in user is not admin
    args = {
        filter: {
            pattern: "#(?P<id>[0-9]+)",
            url_format_string: "https://trac.example.com/ticket/%(id)s",
        },
        can_modify: false,
    };

    html = '';
    html += '<tbody id="admin_filters_table">';
    html += render('admin_filter_list', args);
    html += '</tbody>';

    global.write_test_output('admin_filter_list', html);

    filter_pattern = $(html).find('tr.filter_row:first span.filter_pattern');
    filter_format = $(html).find('tr.filter_row:first span.filter_url_format_string');

    assert.equal(filter_pattern.text(), '#(?P<id>[0-9]+)');
    assert.equal(filter_format.text(), 'https://trac.example.com/ticket/%(id)s');
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
    global.write_handlebars_output("admin_streams_list", html);
}());

(function admin_tab() {
    var args = {
        realm_name: 'Zulip',
    };
    var html = render('admin_tab', args);
    var admin_features = ["admin_users_table", "admin_bots_table",
                          "admin_streams_table", "admin_deactivated_users_table"];
    _.each(admin_features, function (admin_feature) {
        assert.notEqual($(html).find("#" + admin_feature).length, 0);
    });
    assert.equal($(html).find("input.admin-realm-name").val(), 'Zulip');
    global.write_handlebars_output("admin_tab", html);
}());

(function admin_user_list() {
    var html = '<table>';
    var users = ['alice', 'bob', 'carl'];

    // When the logged in user is admin
    _.each(users, function (user) {
        var args = {
            user: {
                is_active: true,
                is_active_human: true,
                email: user + '@zulip.com',
                full_name: user,
            },
            can_modify: true,
        };
        html += render('admin_user_list', args);
    });
    html += "</table>";

    var buttons = $(html).find('.button');

    assert.equal($(buttons[0]).text().trim(), "Deactivate");
    assert($(buttons[0]).hasClass("deactivate"));

    assert.equal($(buttons[1]).text().trim(), "Make admin");
    assert($(buttons[1]).hasClass("make-admin"));

    assert.equal($(buttons[2]).attr('title').trim(), "Edit user");
    assert($(buttons[2]).hasClass("open-user-form"));

    // When the logged in user is not admin
    html = '<table>';
    _.each(users, function (user) {
        var args = {
            user: {
                is_active: true,
                is_active_human: true,
                email: user + '@zulip.com',
                full_name: user,
            },
            can_modify: false,
        };
        html += render('admin_user_list', args);
    });
    html += "</table>";

    buttons = $(html).find('.button');
    assert.equal($(buttons).length, 6);

    global.write_handlebars_output("admin_user_list", html);
}());

(function alert_word_settings_item() {
    var html = '<ul id="alert-words">';
    var words = ['lunch', 'support'];
    var args;
    _.each(words, function (word) {
        args = {
            word: word,
        };
        html += render('alert_word_settings_item', args);
    });
    args = {
        word: '',
        editing: true,
    };
    html += render('alert_word_settings_item', args);
    html += "</ul>";
    global.write_handlebars_output("alert_word_settings_item", html);

    var li = $(html).find("li.alert-word-item:first");
    var value = li.find('.value');
    var button = li.find('button');
    assert.equal(li.attr('data-word'),'lunch');
    assert.equal(value.length, 1);
    assert.equal(value.text(), 'lunch');
    assert.equal(button.attr('title'), 'Delete alert word');
    assert.equal(button.attr('data-word'),'lunch');

    var title = $(html).find('.new-alert-word-section-title');
    var textbox = $(html).find('#create_alert_word_name');
    button = $(html).find('#create_alert_word_button');
    assert.equal(title.length, 1);
    assert.equal(title.text().trim(), 'Add a new alert word');
    assert.equal(textbox.length, 1);
    assert.equal(textbox.attr('maxlength'), 100);
    assert.equal(textbox.attr('placeholder'), 'Alert word');
    assert.equal(textbox.attr('class'), 'required');
    assert.equal(button.length, 1);
    assert.equal(button.text().trim(), 'Add alert word');

}());

(function announce_stream_docs() {
    var html = render('announce_stream_docs');
    global.write_handlebars_output("announce_stream_docs", html);
}());

(function attachment_settings_item() {
    var html = '<ul id="attachments">';
    var attachments = [
        {messages: [], id: 42, name: "foo.txt"},
        {messages: [], id: 43, name: "bar.txt"},
    ];
    _.each(attachments, function (attachment) {
        var args = {attachment: attachment};
        html += render('attachment-item', args);
    });
    html += "</ul>";
    global.write_handlebars_output("attachment-item", html);
    var li = $(html).find("li.attachment-item:first");
    assert.equal(li.attr('data-attachment'), 42);
}());

(function bankruptcy_modal() {
    var args = {
        unread_count: 99,
    };
    var html = render('bankruptcy_modal', args);
    global.write_handlebars_output("bankruptcy_modal", html);
    var count = $(html).find("p b");
    assert.equal(count.text(), 99);
}());

(function admin_auth_methods_list() {
    var args = {
        method: {
            method: "Email",
            enabled: false,
        },
    };

    var html = '';
    html += '<tbody id="admin_auth_methods_table">';
    html += render('admin_auth_methods_list', args);
    html += '</tbody>';

    global.write_test_output('admin_auth_methods_list.handlebars', html);

    var method = $(html).find('tr.method_row:first span.method');
    assert.equal(method.text(), 'Email');
    assert.equal(method.is("checked"), false);
}());

(function bookend() {
    // Do subscribed/unsubscribed cases here.
    var args = {
        bookend_content: "subscribed to stream",
        trailing: true,
        subscribed: true,
    };
    var html;
    var all_html = '';

    html = render('bookend', args);
    assert.equal($(html).text().trim(), "subscribed to stream\n    \n        \n            Unsubscribe");

    all_html += html;

    args = {
        bookend_content: "Not subscribed to stream",
        trailing: true,
        subscribed: false,
    };

    html = render('bookend', args);
    assert.equal($(html).text().trim(), 'Not subscribed to stream\n    \n        \n            Subscribe');

    all_html += '<hr />';
    all_html += html;

    global.write_handlebars_output("bookend", all_html);
}());

(function bot_avatar_row() {
    var html = '';
    html += '<div id="settings">';
    html += '<div id="bot-settings" class="settings-section">';
    html += '<div class="bot-settings-form">';
    html += '<ol id="active_bots_list" style="display: block">';
    var args = {
        email: "hamlet@zulip.com",
        api_key: "123456ABCD",
        name: "Hamlet",
        avatar_url: "/hamlet/avatar/url",
    };
    html += render('bot_avatar_row', args);
    html += '</ol>';
    html += '</div>';
    html += '</div>';
    html += '</div>';

    global.write_handlebars_output("bot_avatar_row", html);
    var img = $(html).find("img");
    assert.equal(img.attr('src'), '/hamlet/avatar/url');
}());

(function bot_owner_select() {
    var args = {
        users_list: [
            {
                email: "hamlet@zulip.com",
                api_key: "123456ABCD",
                full_name: "Hamlet",
                avatar_url: "/hamlet/avatar/url",
            },
        ],
    };
    var html = render('bot_owner_select', args);
    global.write_handlebars_output("bot_owner_select", html);
    var option = $(html).find("option:last");
    assert.equal(option.val(), "hamlet@zulip.com");
    assert.equal(option.text(), "Hamlet");
}());


(function compose_invite_users() {
    var args = {
        email: 'hamlet@zulip.com',
        name: 'Hamlet',
    };
    var html = render('compose-invite-users', args);
    global.write_handlebars_output("compose-invite-users", html);
    var button = $(html).find("button:first");
    assert.equal(button.text(), "Subscribe");
}());

(function compose_all_everyone() {
    var args = {
        count: '101',
        name: 'all',
    };
    var html = render('compose_all_everyone', args);
    global.write_handlebars_output("compose_all_everyone", html);
    var button = $(html).find("button:first");
    assert.equal(button.text(), "Yes, send");
    var error_msg = $(html).find('span.compose-all-everyone-msg').text().trim();
    assert.equal(error_msg, "Are you sure you want to mention all 101 people in this stream?");
}());

(function compose_notification() {
    var args = {
        note: "You sent a message to a muted topic.",
        link_text: "Narrow to here",
        link_msg_id: "99",
        link_class: "compose_notification_narrow_by_subject",
    };
    var html = '<div  id="out-of-view-notification" class="notification-alert">';
    html += render('compose_notification', args);
    html += '</div>';
    global.write_handlebars_output("compose_notification", html);
    var a = $(html).find("a.compose_notification_narrow_by_subject");
    assert.equal(a.text(), "Narrow to here");
}());

(function draft_table_body() {
    var args = {
        drafts: [
            {
                draft_id: '1',
                is_stream: true,
                stream: 'all',
                stream_color: '#FF0000',  // rgb(255, 0, 0)
                topic: 'tests',
                content: 'Public draft',
            },
            {
                draft_id: '2',
                is_stream: false,
                recipients: 'Jordan, Michael',
                content: 'Private draft',
            },
        ],
    };

    var html = '';
    html += '<div id="drafts_table">';
    html += render('draft_table_body', args);
    html += '</div>';

    global.write_handlebars_output("draft_table_body", html);

    var row_1 = $(html).find(".draft-row[data-draft-id='1']");
    assert.equal(row_1.find(".stream_label").text().trim(), "all");
    assert.equal(row_1.find(".stream_label").css("background"), "rgb(255, 0, 0)");
    assert.equal(row_1.find(".stream_topic").text().trim(), "tests");
    assert(!row_1.find(".message_row").hasClass("private-message"));
    assert.equal(row_1.find(".messagebox").css("box-shadow"),
                 "inset 2px 0px 0px 0px #FF0000, -1px 0px 0px 0px #FF0000");
    assert.equal(row_1.find(".message_content").text().trim(), "Public draft");

    var row_2 = $(html).find(".draft-row[data-draft-id='2']");
    assert.equal(row_2.find(".stream_label").text().trim(), "You and Jordan, Michael");
    assert(row_2.find(".message_row").hasClass("private-message"));
    assert.equal(row_2.find(".message_content").text().trim(), "Private draft");
}());


(function email_address_hint() {
    var html = render('email_address_hint');
    global.write_handlebars_output("email_address_hint", html);
    var li = $(html).find("li:first");
    assert.equal(li.text(), 'The email will be forwarded to this stream');
}());

(function emoji_popover() {
    var args = {
        class: "emoji-info-popover",
        categories: [
            { name: "Test category 1", icon: "test-icon-1" },
            { name: "Test category 2", icon: "test-icon-2" },
        ],
    };
    var html = render('emoji_popover', args);
    var categories = $(html).find(".emoji-popover-tab-item");
    assert.equal(categories.length, 2);
    var category_1 = $(html).find(".emoji-popover-tab-item[data-tab-name = 'Test category 1']");
    assert(category_1.hasClass("active"));
    global.write_handlebars_output("emoji_popover", html);
}());

(function emoji_popover_content() {
    var args = {
        search: 'Search',
        message_id: 1,
        emoji_categories: [
            {
                name: 'Test',
                emojis: [
                    {
                        has_reacted: false,
                        is_realm_emoji: false,
                        name: '100',
                        css_class: '100',
                    },
                ],
            },
        ],
    };

    var html = '<div style="height: 250px">';
    html += render('emoji_popover_content', args);
    html += "</div>";
    // test to make sure the first emoji is present in the popover
    var emoji_key = $(html).find(".emoji-100").attr('title');
    assert.equal(emoji_key, '100');
    global.write_handlebars_output("emoji_popover_content", html);
}());

(function emoji_popover_search_results() {
    var args = {
        message_id: 1,
        search_results: [
            {
                has_reacted: false,
                is_realm_emoji: false,
                name: 'test-1',
                css_class: 'test-1',
            },
            {
                has_reacted: true,
                is_realm_emoji: false,
                name: 'test-2',
                css_class: 'test-2',
            },
        ],
    };
    var html = "<div>";
    html += render("emoji_popover_search_results", args);
    html += "</div>";
    global.write_handlebars_output("emoji_popover_search_results", html);
    var used_emoji = $(html).find(".emoji-test-2").parent();
    assert(used_emoji.hasClass("reaction"));
    assert(used_emoji.hasClass("reacted"));
}());

(function group_pms() {
    var args = {
        group_pms: [
            {
                fraction_present: 0.1,
                emails: "alice@zulip.com,bob@zulip.com",
                short_name: "Alice and Bob",
                name: "Alice and Bob",
            },
        ],
    };
    var html = render('group_pms', args);
    global.write_handlebars_output("group_pms", html);

    var a = $(html).find("a:first");
    assert.equal(a.text(), 'Alice and Bob');
}());

(function hotspot_overlay() {
    var args = {
        title: 'Start a new conversation',
        name: 'intro_compose',
        description: 'Click the "New topic" button to start a new conversation.',
    };

    var html = render('hotspot_overlay', args);
    global.write_handlebars_output("hotspot_overlay", html);

    assert.equal($(html).attr('id'), 'hotspot_intro_compose_overlay');
    assert.equal($(html).find('.hotspot-title').text(), 'Start a new conversation');
    assert.equal(
        $(html).find('.hotspot-description').text(),
        'Click the "New topic" button to start a new conversation.'
    );
}());

(function invite_subscription() {
    var args = {
        streams: [
            {
                name: "devel",
            },
            {
                name: "social",
            },
        ],
    };
    var html = render('invite_subscription', args);
    global.write_handlebars_output("invite_subscription", html);

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
            starred: true,
            starred_status: "Unstar",
        },
    };

    var html = render('single_message', message);
    html = '<div class="message_table focused_table" id="zfilt">' + html + '</div>';

    global.write_handlebars_output("message", html);

    var first_message = $(html).find("div.messagebox:first");

    var first_message_text = first_message.find(".message_content").text().trim();
    assert.equal(first_message_text, "This is message one.");

    var starred_title = first_message.find(".star").attr("title");
    assert.equal(starred_title, "Unstar this message (*)");
}());

(function message_edit_form() {
    var args = {
        topic: "lunch",
        content: "Let's go to lunch!",
        is_stream: true,
    };
    var html = render('message_edit_form', args);
    global.write_handlebars_output("message_edit_form", html);

    var textarea = $(html).find("textarea.message_edit_content");
    assert.equal(textarea.text(), "Let's go to lunch!");
}());

(function message_group() {
    var messages = [
        {
            msg: {
                id: 1,
                match_content: 'This is message one.',
                starred: true,
                is_stream: true,
                content: 'This is message one.',
            },
            include_recipient: true,
            display_recipient: 'devel',
            last_edit_timestr: '11:00',
        },
        {
            msg: {
                content: 'This is message two.',
                match_content: 'This is message <span class="highlight">two</span>.',
                is_stream: true,
                unread: true,
                id: 2,
            },
        },
    ];

    var groups = [
        {
            display_recipient: "support",
            is_stream: true,
            message_ids: [1, 2],
            message_containers: messages,
            show_date: '"<span class="timerender82">Jan&nbsp;07</span>"',
            show_date_separator: true,
            subject: 'two messages',
            match_subject: '<span class="highlight">two</span> messages',
        },
    ];

    render('loader');
    var html = render('message_group', {message_groups: groups, use_match_properties: true});

    var first_message_text = $(html).next('.recipient_row').find('div.messagebox:first .message_content').text().trim();
    assert.equal(first_message_text, "This is message one.");

    var last_message_html = $(html).next('.recipient_row').find('div.messagebox:last .message_content').html().trim();
    assert.equal(last_message_html, 'This is message <span class="highlight">two</span>.');

    var highlighted_subject_word = $(html).find('a.narrows_by_subject .highlight').text();
    assert.equal(highlighted_subject_word, 'two');

    global.write_handlebars_output("message_group", html);
}());

(function message_edit_history() {
    var message = {
        content: "Let's go to lunch!",
        edit_history: [
            {
                body_to_render: "<p>Let's go to " +
                                    "<span class='highlight_text_deleted'>lunch</span>" +
                                    "<span class='highlight_text_inserted'>dinner</span>" +
                                "!</p>",
                timestamp: 1468132659,
                edited_by: 'Alice',
                posted_or_edited: "Edited by",
            },
        ],
    };
    var html = render('message_edit_history', {
            edited_messages: message.edit_history,
        });
    global.write_test_output("message_edit_history.handlebars", html);
    var edited_message = $(html).find("div.messagebox-content");
    assert.equal(edited_message.text().trim(),
                "1468132659\n                Let's go to lunchdinner!\n                Edited by Alice");
}());

(function message_reaction() {
    var args = {
        emoji_name: 'smile',
        message_id: '1',
    };

    var html = '';
    html += '<div>';
    html += render('message_reaction', args);
    html += '</div>';

    global.write_handlebars_output("message_reaction", html);
    assert($(html).find(".message_reaction").has(".emoji .emoji-smile"));
}());

(function new_stream_users() {
    var args = {
        users: [
            {
                email: 'lear@zulip.com',
                full_name: 'King Lear',
            },
            {
                email: 'othello@zulip.com',
                full_name: 'Othello the Moor',
            },
        ],
    };

    var html = render('new_stream_users', args);
    global.write_handlebars_output("new_stream_users", html);

    var label = $(html).find("label:first");
    assert.equal(label.text().trim(), 'King Lear (lear@zulip.com)');
}());

(function notification() {
    var args = {
        content: "Hello",
        gravatar_url: "/gravatar/url",
        title: "You have a notification",
    };

    var html = render('notification', args);
    global.write_handlebars_output("notification", html);

    var title = $(html).find(".title");
    assert.equal(title.text().trim(), 'You have a notification');
}());

(function propagate_notification_change() {
    var html = render('propagate_notification_change');
    global.write_handlebars_output("propagate_notification_change", html);

    var button_area = $(html).find(".propagate-notifications-controls");
    assert.equal(button_area.find(".yes_propagate_notifications").text().trim(), 'Yes');
    assert.equal(button_area.find(".no_propagate_notifications").text().trim(), 'No');
}());

(function settings_tab() {
    var page_param_checkbox_options = {
        enable_stream_desktop_notifications: true,
        enable_stream_push_notifications: true,
        enable_stream_sounds: true, enable_desktop_notifications: true,
        enable_sounds: true, enable_offline_email_notifications: true,
        enable_offline_push_notifications: true, enable_online_push_notifications: true,
        enable_digest_emails: true,
        autoscroll_forever: true, default_desktop_notifications: true,
    };
    var page_params = $.extend(page_param_checkbox_options, {
        full_name: "Alyssa P. Hacker", password_auth_enabled: true,
        avatar_url: "https://google.com",
    });

    var checkbox_ids = ["enable_stream_desktop_notifications",
                        "enable_stream_push_notifications",
                        "enable_stream_sounds", "enable_desktop_notifications",
                        "enable_sounds", "enable_offline_push_notifications",
                        "enable_online_push_notifications",
                        "enable_digest_emails", "autoscroll_forever",
                        "default_desktop_notifications"];

    // Render with all booleans set to true.
    var html = render('settings_tab', {page_params: page_params});
    global.write_handlebars_output("settings_tab", html);

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

    // Check if enable_desktop_notifications setting disables subsetting too.
    var parent_elem = $('#pm_content_in_desktop_notifications_label').wrap("<div></div>");

    $('#enable_desktop_notifications').prop('checked', false).triggerHandler('change');
    $('#enable_desktop_notifications').change(function () {
        assert(parent_elem.hasClass('control-label-disabled'));
        assert.equal($('#pm_content_in_desktop_notifications').attr('disabled'), 'disabled');
    });

    $('#enable_desktop_notifications').prop('checked', true).triggerHandler('change');
    $('#enable_desktop_notifications').change(function () {
        assert(!parent_elem.hasClass('control-label-disabled'));
        assert.equal($('#pm_content_in_desktop_notifications').attr('disabled'), undefined);
    });

}());

(function sidebar_private_message_list() {
    var args = {
        want_show_more_messages_links: true,
        messages: [
            {
                recipients: "alice,bob",
            },
        ],
    };

    var html = '';
    html += render('sidebar_private_message_list', args);

    var conversations = $(html).find('a').text().trim().split('\n');
    assert.equal(conversations[0], 'alice,bob');
    assert.equal(conversations[1].trim(), '(more conversations)');

    global.write_handlebars_output("sidebar_private_message_list", html);
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

    global.write_handlebars_output("stream_member_list_entry", html);
}());

(function stream_sidebar_actions() {
    var args = {
        stream: {
            color: 'red',
            name: 'devel',
            in_home_view: true,
            id: 55,
        },
    };

    var html = render('stream_sidebar_actions', args);
    global.write_handlebars_output("stream_sidebar_actions", html);

    var li = $(html).find("li:first");
    assert.equal(li.text().trim(), 'Stream settings');
}());

(function stream_sidebar_row() {
    var args = {
        name: "devel",
        color: "red",
        dark_background: "maroon",
        uri: "/devel/uri",
        id: 999,
    };

    var html = '<ul id="stream_filters">';
    html += render('stream_sidebar_row', args);
    html += '</ul>';

    global.write_handlebars_output("stream_sidebar_row", html);

    var swatch = $(html).find(".stream-privacy");
    assert.equal(swatch.attr('id'), 'stream_sidebar_privacy_swatch_999');

    // test to ensure that the hashtag element from stream_privacy exists.
    assert.equal($(html).find(".stream-privacy").children("*").attr("class"), "hashtag");
}());

(function subscription_invites_warning_modal() {
    var html = render('subscription_invites_warning_modal');

    global.write_handlebars_output("subscription_invites_warning_modal", html);

    var button = $(html).find(".close-invites-warning-modal").last();
    assert.equal(button.text(), 'Go back');
}());

(function subscription_settings() {
    var sub = {
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
        stream_id: 888,
        in_home_view: true,
    };

    var html = '';
    html += render('subscription_settings', sub);

    global.write_handlebars_output("subscription_settings", html);

    var div = $(html).find(".subscription-type");
    assert(div.text().indexOf('invite-only stream') > 0);

    var anchor = $(html).find(".change-stream-privacy:first");
    assert.equal(anchor.data("is-private"), true);
    assert.equal(anchor.text(), "[Change]");
}());


(function subscription_stream_privacy_modal() {
    var args = {
        stream_id: 999,
        is_private: true,
    };
    var html = render('subscription_stream_privacy_modal', args);

    global.write_handlebars_output("subscription_stream_privacy_modal", html);

    var stream_desc = $(html).find(".modal-body b");
    assert.equal(stream_desc.text(), 'an invite-only stream');

    var button = $(html).find("#change-stream-privacy-button");
    assert(button.hasClass("btn-primary"));
    assert.equal(button.text().trim(), "Make stream public");
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
                stream_id: 888,
                in_home_view: true,
            },
            {
                name: 'social',
                color: 'green',
                stream_id: 999,
            },
        ],
    };

    var html = '';
    html += '<div id="subscriptions_table">';
    html += render('subscription_table_body', args);
    html += '</div>';

    global.write_handlebars_output("subscription_table_body", html);

    var span = $(html).find(".stream-name:first");
    assert.equal(span.text(), 'devel');
}());


(function tab_bar() {
    var args = {
        tabs: [
            {
                cls: 'root',
                title: 'Home',
                hash: '#',
                data: 'home',
            },
            {
                cls: 'stream',
                title: 'Devel',
                hash: '/stream/uri',
                data: 'devel',
            },
        ],
    };

    var html = render('tab_bar', args);

    global.write_handlebars_output("tab_bar", html);

    var a = $(html).find("li:first");
    assert.equal(a.text().trim(), 'Home');
}());

(function topic_edit_form() {
    var html = render('topic_edit_form');

    global.write_handlebars_output("topic_edit_form", html);

    var button = $(html).find("button:first");
    assert.equal(button.find("i").attr("class"), 'icon-vector-ok');
}());

(function topic_list_item() {
    var args = {
        is_muted: false,
        topic_name: 'lunch',
        url: '/lunch/url',
        unread: 5,
    };

    var html = render('topic_list_item', args);

    global.write_handlebars_output("topic_list_item", html);

    assert.equal($(html).attr('data-topic-name'), 'lunch');
}());


(function topic_sidebar_actions() {
    var args = {
        stream_name: 'social',
        topic_name: 'lunch',
        can_mute_topic: true,
    };
    var html = render('topic_sidebar_actions', args);

    global.write_handlebars_output("topic_sidebar_actions", html);

    var a = $(html).find("a.narrow_to_topic");
    assert.equal(a.text().trim(), 'Narrow to topic lunch');

}());

(function typeahead_list_item() {
    var args = {
        primary: 'primary-text',
        secondary: 'secondary-text',
        img_src: 'https://zulip.org',
        has_image: true,
        has_secondary: true,
    };

    var html = '<div>' + render('typeahead_list_item', args) + '</div>';
    global.write_handlebars_output('typeahead_list_item', html);

    assert.equal($(html).find('.emoji').attr('src'), 'https://zulip.org');
    assert.equal($(html).find('strong').text().trim(), 'primary-text');
    assert.equal($(html).find('small').text().trim(), 'secondary-text');
}());

(function typing_notifications() {
    var args = {
        users: [{
            full_name: 'Hamlet',
            email: 'hamlet@zulip.com',
        }],
    };

    var html = '';
    html += '<ul>';
    html += render('typing_notifications', args);
    html += '</ul>';

    global.write_handlebars_output('typing_notifications', html);
    var li = $(html).find('li:first');
    assert.equal(li.text(), 'Hamlet is typing...');

}());

(function user_info_popover() {
    var html = render('user_info_popover', {class: 'message-info-popover'});
    global.write_handlebars_output("user_info_popover", html);

    $(html).hasClass('popover message-info-popover');
}());

(function user_info_popover_content() {
    var args = {
        message: {
            full_date_str: 'Monday',
            full_time_str: '12:00',
            user_full_name: 'Alice Smith',
            user_email: 'alice@zulip.com',
        },
        sent_by_uri: '/sent_by/uri',
        pm_with_uri: '/pm_with/uri',
        private_message_class: 'compose_private_message',
    };

    var html = render('user_info_popover_content', args);
    global.write_handlebars_output("user_info_popover_content", html);

    var a = $(html).find("a.compose_private_message");
    assert.equal(a.text().trim(), 'Send private message (R)');
}());

(function user_info_popover_title() {
    var html = render('user_info_popover_title', {user_avatar: 'avatar/hamlet@zulip.com'});
    global.write_handlebars_output("user_info_popover_title", html);

    html = '<div>' + html + '</div>';
    assert($(html).find('.popover-avatar').css('background-image'), "url(avatar/hamlet@zulip.com)");
}());

(function user_presence_rows() {
    var args = {
        users: [
            {
                type_desc: "Active",
                type: "active",
                num_unread: 0,
                email: "lear@zulip.com",
                name: "King Lear",
            },
            {
                type_desc: "Away",
                type: "away",
                num_unread: 5,
                email: "othello@zulip.com",
                name: "Othello",
            },
        ],
    };

    var html = '';
    html += '<ul class="filters">';
    html += render('user_presence_rows', args);
    html += '</ul>';

    global.write_handlebars_output("user_presence_rows", html);

    var a = $(html).find("a:first");
    assert.equal(a.text(), 'King Lear');
}());

(function muted_topic_ui_row() {
    var args = {
        stream: 'Verona',
        topic: 'Verona2',
    };

    var html = '<table id="muted-topics-table">';
    html += '<tbody>';
    html += render('muted_topic_ui_row', args);
    html += '</tbody>';
    html += '</table>';

    assert.equal($(html).find("tr").data("stream"), "Verona");
    assert.equal($(html).find("tr").data("topic"), "Verona2");
}());

// By the end of this test, we should have compiled all our templates.  Ideally,
// we will also have exercised them to some degree, but that's a little trickier
// to enforce.
global.make_sure_all_templates_have_been_compiled();
