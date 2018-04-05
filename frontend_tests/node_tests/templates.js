zrequire('Handlebars', 'handlebars');
zrequire('templates');

set_global('i18n', global.stub_i18n);

var jsdom = require("jsdom");
var window = jsdom.jsdom().defaultView;
global.$ = require('jquery')(window);

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
        should_display_quote_and_reply: true,
        can_edit_message: true,
        can_mute_topic: true,
        narrowed: true,
    };

    var html = '<div style="height: 250px">';
    html += render('actions_popover_content', args);
    html += "</div>";
    var link = $(html).find("a.respond_button");
    assert.equal(link.text().trim(), 'translated: Quote and reply');
    global.write_handlebars_output("actions_popover_content", html);

    var deletedArgs = {
        message: {
            is_stream: true,
            id: "100",
            stream: "devel",
            subject: "testing",
            sender_full_name: "King Lear",
        },
        should_display_edit_and_view_source: false,
        should_display_quote_and_reply: false,
        narrowed: true,
    };

    var deletedHtml = '<div style="height: 250px">';
    deletedHtml += render('actions_popover_content', deletedArgs);
    deletedHtml += "</div>";
    var viewSourceLink = $(deletedHtml).find("a.popover_edit_message");
    assert.equal(viewSourceLink.length, 0);
    var quoteLink = $(deletedHtml).find("a.respond_button");
    assert.equal(quoteLink.length, 0);
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

    assert.equal(button.text().trim(), "translated: Remove");
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

(function admin_profile_field_list() {

    // When the logged in user is admin
    var args = {
        profile_field: {
            name: "teams",
            type: "Long Text",
        },
        can_modify: true,
    };

    var html = '';
    html += '<tbody id="admin_profile_fields_table">';
    html += render('admin_profile_field_list', args);
    html += '</tbody>';

    var field_name = $(html).find('tr.profile-field-row:first span.profile_field_name');
    var field_type = $(html).find('tr.profile-field-row:first span.profile_field_type');
    var td = $(html).find('tr.profile-field-row:first td');

    assert.equal(field_name.text(), 'teams');
    assert.equal(field_type.text(), 'Long Text');
    assert.equal(td.length, 3);

    // When the logged in user is not admin
    args = {
        profile_field: {
            name: "teams",
            type: "Long Text",
        },
        can_modify: false,
    };

    html = '';
    html += '<tbody id="admin_profile_fields_table">';
    html += render('admin_profile_field_list', args);
    html += '</tbody>';

    global.write_test_output('admin_profile_field_list', html);

    field_name = $(html).find('tr.profile-field-row:first span.profile_field_name');
    field_type = $(html).find('tr.profile-field-row:first span.profile_field_type');
    td = $(html).find('tr.profile-field-row:first td');

    assert.equal(field_name.text(), 'teams');
    assert.equal(field_type.text(), 'Long Text');
    assert.equal(td.length, 2);
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

(function admin_invites_list() {
    var html = '<table>';
    var invites = ['alice', 'bob', 'carl'];
    var invite_id = 0;
    _.each(invites, function (invite) {
        var args = {
            invite: {
                email: invite + '@zulip.com',
                ref: 'iago@zulip.com',
                invited: "2017-01-01 01:01:01",
                id: invite_id,
                invited_as_admin: true,
            },
        };
        html += render('admin_invites_list', args);
        invite_id += 1;
    });
    html += "</table>";
    var buttons = $(html).find('.button');

    assert.equal($(buttons[0]).text().trim(), "translated: Revoke");
    assert($(buttons[0]).hasClass("revoke"));
    assert.equal($(buttons[0]).attr("data-invite-id"), 0);

    assert.equal($(buttons[3]).text().trim(), "translated: Resend");
    assert($(buttons[3]).hasClass("resend"));
    assert.equal($(buttons[3]).attr("data-invite-id"), 1);

    var span = $(html).find(".email:first");
    assert.equal(span.text(), "alice@zulip.com");

    var icon = $(html).find(".icon-vector-bolt");
    assert.equal(icon.attr('title'), "translated: Invited as administrator");

    global.write_handlebars_output("admin_invites_list", html);
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
                          "admin_streams_table", "admin_deactivated_users_table",
                          "admin_invites_table"];
    _.each(admin_features, function (admin_feature) {
        assert.notEqual($(html).find("#" + admin_feature).length, 0);
    });
    assert.equal($(html).find("input.admin-realm-name").val(), 'Zulip');
    global.write_handlebars_output("admin_tab", html);
}());

(function admin_user_group_list() {
    var args = {
        user_group: {
            id: "9",
            name: "uranohoshi",
            description: "Students at Uranohoshi Academy",
        },
    };

    var html = '';
    html += '<div id="user-groups">';
    html += render('admin_user_group_list', args);
    html += '</div>';

    global.write_handlebars_output('admin_user_group_list', html);

    var group_id = $(html).find('.user-group:first').prop('id');
    var group_name_pills = $(html).find('.user-group:first .pill-container').attr('data-group-pills');
    var group_name_display = $(html).find('.user-group:first .name').text().trim().replace(/\s+/g, ' ');
    var group_description = $(html).find('.user-group:first .description').text().trim().replace(/\s+/g, ' ');

    assert.equal(group_id, '9');
    assert.equal(group_name_pills, 'uranohoshi');
    assert.equal(group_name_display, 'uranohoshi');
    assert.equal(group_description, 'Students at Uranohoshi Academy');
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

    assert.equal($(buttons[0]).text().trim(), "translated: Deactivate");
    assert($(buttons[0]).hasClass("deactivate"));

    assert.equal($(buttons[1]).text().trim(), "translated: Make admin");
    assert($(buttons[1]).hasClass("make-admin"));

    assert.equal($(buttons[2]).attr('title').trim(), "translated: Edit user");
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
    assert.equal(button.attr('title'), 'translated: Delete alert word');
    assert.equal(button.attr('data-word'),'lunch');

    var title = $(html).find('.new-alert-word-section-title');
    var textbox = $(html).find('#create_alert_word_name');
    button = $(html).find('#create_alert_word_button');
    assert.equal(title.length, 1);
    assert.equal(title.text().trim(), 'translated: Add a new alert word');
    assert.equal(textbox.length, 1);
    assert.equal(textbox.attr('maxlength'), 100);
    assert.equal(textbox.attr('placeholder'), 'translated: Alert word');
    assert.equal(textbox.attr('class'), 'required');
    assert.equal(button.length, 1);
    assert.equal(button.text().trim(), 'translated: Add alert word');

}());

(function all_messages_sidebar_actions() {
    var html = render('all_messages_sidebar_actions');
    global.write_handlebars_output("all_messages_sidebar_actions", html);
}());

(function announce_stream_docs() {
    var html = render('announce_stream_docs');
    global.write_handlebars_output("announce_stream_docs", html);
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
    assert.equal($(html).text().trim(), "subscribed to stream\n    \n        \n            translated: Unsubscribe");

    all_html += html;

    args = {
        bookend_content: "Not subscribed to stream",
        trailing: true,
        subscribed: false,
    };

    html = render('bookend', args);
    assert.equal($(html).text().trim(), 'Not subscribed to stream\n    \n        \n            translated: Subscribe');

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
    assert.equal(button.text(), "translated: Subscribe");
}());

(function compose_all_everyone() {
    var args = {
        count: '101',
        name: 'all',
    };
    var html = render('compose_all_everyone', args);
    global.write_handlebars_output("compose_all_everyone", html);
    var button = $(html).find("button:first");
    assert.equal(button.text(), "translated: Yes, send");
    var error_msg = $(html).find('span.compose-all-everyone-msg').text().trim();
    assert.equal(error_msg, "translated: Are you sure you want to mention all 101 people in this stream?");
}());

(function compose_announce() {
    var args = {
        count: '101',
    };
    var html = render('compose_announce', args);
    global.write_handlebars_output("compose_announce", html);
    var button = $(html).find("button:first");
    assert.equal(button.text(), "translated: Yes, send");
    var error_msg = $(html).find('span.compose-announce-msg').text().trim();
    assert.equal(error_msg, "translated:         This stream is reserved for announcements.\n        \n        Are you sure you want to message all 101 people in this stream?");
}());

(function compose_not_subscribed() {
    var html = render('compose_not_subscribed');
    global.write_handlebars_output("compose_not_subscribed", html);
    var button = $(html).find("button:first");
    assert.equal(button.text(), "translated: Subscribe");
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

(function compose_private_stream_alert() {
    var args = {
      stream_name: 'Denmark',
    };
    var html = render('compose_private_stream_alert', args);
    assert($(html).hasClass('compose_private_stream_alert'));

    var actual_text = $(html).text();
    var expected_text = 'translated: Warning: Denmark is a private stream.';
    assert(actual_text.indexOf(expected_text) >= 1);
    global.write_handlebars_output("compose_stream_alert", html);
}());

(function custom_user_profile_field() {
    var args = {field_name: "GitHub user name", field_id: 2, field_value: "@GitHub", field_type: "text"};
    var html = render('custom-user-profile-field', args);
    assert.equal($(html).find('input').attr('id'), 2);
    assert.equal($(html).find('input').val(), "@GitHub");
    global.write_handlebars_output("custom-user-profile-field", html);
}());

(function deactivate_stream_modal() {
    var args = {
        stream_name: "Public stream",
    };
    var html = render('deactivation-stream-modal', args);
    global.write_handlebars_output("deactivation-stream-modal", html);

    var modal_header = $(html).find("#deactivation_stream_modal_label");
    assert.equal(modal_header.text(), "translated: Delete stream " + args.stream_name);

    var button = $(html).find("#do_deactivate_stream_button");
    assert.equal(button.text(), "translated: Yes, delete this stream");
}());

(function dev_env_email_access() {
    var html = render('dev_env_email_access');
    global.write_handlebars_output("dev_env_email_access", html);
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
    assert.equal(row_2.find(".stream_label").text().trim(), "translated: You and Jordan, Michael");
    assert(row_2.find(".message_row").hasClass("private-message"));
    assert.equal(row_2.find(".message_content").text().trim(), "Private draft");
}());


(function email_address_hint() {
    var html = render('email_address_hint');
    global.write_handlebars_output("email_address_hint", html);
    var li = $(html).find("li:first");
    assert.equal(li.text(), 'translated: The email will be forwarded to this stream');
}());

(function emoji_popover() {
    var args = {
        class: "emoji-info-popover",
    };
    var html = "<div>";
    html += render('emoji_popover', args);
    html += "</div>";
    var popover = $(html).find(".popover");
    assert(popover.hasClass("emoji-info-popover"));
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
            {
                name: 'Test1',
                emojis: [
                    {
                        has_reacted: false,
                        is_realm_emoji: true,
                        name: 'zulip',
                        url: 'zulip',
                    },
                ],
            },
        ],
    };

    var html = '<div style="height: 250px">';
    html += render('emoji_popover_content', args);
    html += "</div>";
    // test to make sure the first emoji is present in the popover
    var first_emoji = $(html).find(".emoji-100");
    assert.equal(first_emoji.length, 1);

    var categories = $(html).find(".emoji-popover-tab-item");
    assert.equal(categories.length, 2);

    var category_1 = $(html).find(".emoji-popover-tab-item[data-tab-name = 'Test']");
    assert(category_1.hasClass("active"));

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

(function emoji_showcase() {
    var args = {
        emoji_dict: {
            name: "thumbs_up",
            is_realm_emoji: false,
            css_class: "1f44d",
            has_reacted: false,
        },
    };
    var html = render("emoji_showcase", args);
    var emoji_div = $(html).find(".emoji");
    var canonical_name = $(html).find(".emoji-canonical-name");

    assert.equal(emoji_div.length, 1);
    assert(emoji_div.hasClass("emoji-1f44d"));
    assert.equal(canonical_name.text(), "thumbs_up");
    assert.equal(canonical_name.attr("title"), "thumbs_up");
    global.write_handlebars_output("emoji_showcase", html);
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

(function input_pill() {
    var args = {
        id: 22,
        display_value: 'King Hamlet',
    };

    var html = render('input_pill', args);
    global.write_handlebars_output("input_pill", html);

    assert($(html).hasClass('pill'));
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
    assert.equal(starred_title, "translated: Unstar this message (*)");
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
        class: 'message_reaction',
        emoji_name: 'smile',
        emoji_code: '1f604',
        local_id: 'unicode_emoji,smile,1f604',
        message_id: '1',
    };

    var html = '';
    html += '<div>';
    html += render('message_reaction', args);
    html += '</div>';

    var reaction = $(html).find(".message_reaction");
    assert.equal(reaction.data("reaction-id"), "unicode_emoji,smile,1f604");
    assert(reaction.find(".emoji").hasClass("emoji-1f604"));
    global.write_handlebars_output("message_reaction", html);
}());

(function more_topics() {
    var html = render('more_topics');
    global.write_handlebars_output("more_topics", html);

    assert($(html).hasClass('show-more-topics'));
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

(function non_editable_user_group() {
    var args = {
        user_group: {
            id: "9",
            name: "uranohoshi",
            description: "Students at Uranohoshi Academy",
        },
    };

    var html = '';
    html += '<div id="user-groups">';
    html += render('non_editable_user_group', args);
    html += '</div>';

    global.write_handlebars_output('non_editable_user_group', html);

    var group_id = $(html).find('.user-group:first').prop('id');
    var group_name_pills = $(html).find('.user-group:first .pill-container').attr('data-group-pills');
    var group_name_display = $(html).find('.user-group:first .name').text().trim().replace(/\s+/g, ' ');
    var group_description = $(html).find('.user-group:first .description').text().trim().replace(/\s+/g, ' ');

    assert.equal(group_id, '9');
    assert.equal(group_name_pills, 'uranohoshi');
    assert.equal(group_name_display, 'uranohoshi');
    assert.equal(group_description, 'Students at Uranohoshi Academy');
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
    assert.equal(button_area.find(".yes_propagate_notifications").text().trim(), 'translated: Yes');
    assert.equal(button_area.find(".no_propagate_notifications").text().trim(), 'translated: No');
}());

(function reminder_popover_content() {
    var args = {
        message: {
            is_stream: true,
            id: "420",
            stream: "devel",
            subject: "testing",
            sender_full_name: "Iago",
        },
        can_edit_message: true,
        can_mute_topic: true,
        narrowed: true,
    };

    var html = '<div style="height: 250px">';
    html += render('remind_me_popover_content', args);
    html += "</div>";
    var link = $(html).find("a.remind.custom");
    assert.equal(link.text().trim(), 'translated: Select date and time');
    global.write_handlebars_output("remind_me_popover_content", html);
}());

(function settings_tab() {
    var page_param_checkbox_options = {
        enable_stream_desktop_notifications: true,
        enable_stream_push_notifications: true,
        enable_stream_sounds: true, enable_desktop_notifications: true,
        enable_sounds: true, enable_offline_email_notifications: true,
        enable_offline_push_notifications: true, enable_online_push_notifications: true,
        enable_digest_emails: true,
        default_desktop_notifications: true,
        realm_name_in_notifications: true,
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
                        "enable_digest_emails",
                        "default_desktop_notifications",
                        "realm_name_in_notifications"];

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
    assert.equal(conversations[1].trim(), '(translated: more conversations)');

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
    assert.equal(li.text().trim(), 'translated: Stream settings');
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
    assert.equal(button.text(), 'translated: Go back');
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
        can_change_subscription_type: true,
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
    assert.equal(anchor.text(), "[translated: Change]");
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
    assert.equal(button.text().trim(), "translated: Make stream public");
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
    assert.equal(a.text().trim(), 'translated: Narrow to topic lunch');

}());

(function typeahead_list_item() {
    var args = {
        primary: 'primary-text',
        secondary: 'secondary-text',
        img_src: 'https://zulip.org',
        is_emoji: true,
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

(function user_group_info_popover() {
    var html = render('user_group_info_popover');
    global.write_handlebars_output("user_group_info_popover", html);

    $(html).hasClass('popover message-info-popover group-info-popover');
}());

(function user_group_info_popover_content() {
    var args = {
        group_name: 'groupName',
        group_description: 'groupDescription',
        members: [
            {
                presence_status: 'active',
                full_name: 'Active Alice',
                user_last_seen_time_status: 'time',
                is_bot: false,
            },
            {
                presence_status: 'offline',
                full_name: 'Bot Bob',
                user_last_seen_time_status: 'time',
                is_bot: true,
            },
            {
                presence_status: 'offline',
                full_name: 'Inactive Imogen',
                user_last_seen_time_status: 'time',
                is_bot: false,
            },
        ],
    };

    var html = render('user_group_info_popover_content', args);
    global.write_handlebars_output("user_group_info_popover_content", html);

    var allUsers = $(html).find("li");
    assert.equal(allUsers[0].classList.contains("user_active"), true);
    assert.equal(allUsers[2].classList.contains("user_offline"), true);
    assert.equal($(allUsers[0]).text().trim(), 'Active Alice');
    assert.equal($(allUsers[1]).text().trim(), 'Bot Bob');
    assert.equal($(allUsers[2]).text().trim(), 'Inactive Imogen');

    assert.equal($(html).find('.group-name').text().trim(), 'groupName');
    assert.equal($(html).find('.group-description').text().trim(), 'groupDescription');
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

    var a = $(html).find("a.narrow_to_private_messages");
    assert.equal(a.text().trim(), 'translated: View private messages');
}());

(function user_info_popover_title() {
    var html = render('user_info_popover_title', {user_avatar: 'avatar/hamlet@zulip.com'});
    global.write_handlebars_output("user_info_popover_title", html);

    html = '<div>' + html + '</div>';
    assert.equal($(html).find('.popover-avatar').css('background-image'), "url(avatar/hamlet@zulip.com)");
}());

(function uploaded_files_list_popover() {
    var args = {
        attachment: {
            name: "file_name.txt",
            create_time: "Apr 12 04:18 AM",
            messages: [
                {
                    id: "1",
                },
                {
                    id: "2",
                },
            ],
            size: 1234,
            path_id: "2/65/6wITdgsd63hdskjuFqEeEy7_r/file_name.txt",
        },
    };

    var html = render('uploaded_files_list', args);
    assert.equal($(html).find('.ind-message').attr("href"), "/#narrow/id/1");
    assert.equal($(html).find('#download_attachment').attr("href"),
                 "/user_uploads/2/65/6wITdgsd63hdskjuFqEeEy7_r/file_name.txt");

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

(function embedded_bot_config_item() {
    var args = {
        botname: 'giphy',
        key: 'api_key',
        value: '12345678',
    };
    var html = render('embedded_bot_config_item', args);
    assert.equal($(html).attr('name'), args.botname);
    assert.equal($(html).attr('id'), args.botname+'_'+args.key);
    assert.equal($(html).find('label').text(), args.key);
    assert.equal($(html).find('input').attr('placeholder'), args.value);
}());

(function edit_bot() {
    render('edit_bot');
}());

(function edit_outgoing_webhook_service() {
    var args = {
        service: {base_url: "http://www.foo.bar",
                  interface: "1"},
    };
    var html = render('edit-outgoing-webhook-service', args);
    assert.equal($(html).find('#edit_service_base_url').attr('value'), args.service.base_url);
    assert.equal($(html).find('#edit_service_interface').attr('value'), args.service.interface);
}());

(function edit_embedded_bot_service() {
    var args = {
        service: {service_name: "giphy",
                  config_data: {key: "abcd1234"}},
    };
    var html = render('edit-embedded-bot-service', args);
    assert.equal($(html).find('#embedded_bot_key_edit').attr('name'), 'key');
    assert.equal($(html).find('#embedded_bot_key_edit').val(), 'abcd1234');
}());

// By the end of this test, we should have compiled all our templates.  Ideally,
// we will also have exercised them to some degree, but that's a little trickier
// to enforce.
global.make_sure_all_templates_have_been_compiled();
