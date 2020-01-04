set_global('Handlebars', global.make_handlebars());
zrequire('templates');

set_global('i18n', global.stub_i18n);
set_global('page_params', {});
zrequire('settings_notifications');
zrequire('stream_edit');

const { JSDOM } = require("jsdom");
const { window } = new JSDOM();
global.$ = require('jquery')(window);

// When writing these tests, the following command might be helpful:
// ./tools/get-handlebar-vars static/templates/*.hbs

function render(template_name, args) {
    return require('../../static/templates/' + template_name + '.hbs')(args);
}

run_test('handlebars_bug', () => {
    // There was a bug in 1.0.9 where identically structured
    // blocks get confused, so when foo is false, it still
    // renders the foo-is-true block.
    let s = '';
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
    const template = global.Handlebars.compile(s);
    const output = template({});

    assert.equal(output, 'd'); // the buggy version would return 'b'
});

run_test('actions_popover_content', () => {
    const args = {
        should_display_quote_and_reply: true,
        can_edit_message: true,
        can_mute_topic: true,
        narrowed: true,
    };

    let html = '<div style="height: 250px">';
    html += render('actions_popover_content', args);
    html += "</div>";
    const link = $(html).find("a.respond_button");
    assert.equal(link.text().trim(), 'translated: Quote and reply');

    const deletedArgs = {
        should_display_edit_and_view_source: false,
        should_display_quote_and_reply: false,
        narrowed: true,
    };

    let deletedHtml = '<div style="height: 250px">';
    deletedHtml += render('actions_popover_content', deletedArgs);
    deletedHtml += "</div>";
    const viewSourceLink = $(deletedHtml).find("a.popover_edit_message");
    assert.equal(viewSourceLink.length, 0);
    const quoteLink = $(deletedHtml).find("a.respond_button");
    assert.equal(quoteLink.length, 0);
});

run_test('admin_realm_domains_list', () => {
    let html = "<table>";
    const args = {
        realm_domain: {
            domain: 'zulip.org',
            allow_subdomains: true,
        },
    };
    html += render("settings/admin_realm_domains_list", args);
    html += "</table>";

    const button = $(html).find('.button');
    const domain = $(html).find('.domain');
    const row = button.closest('tr');
    const subdomains_checkbox = row.find('.allow-subdomains');

    assert.equal(button.text().trim(), "translated: Remove");
    assert(button.hasClass("delete_realm_domain"));
    assert.equal(domain.text(), "zulip.org");

    assert.equal(subdomains_checkbox.prop('checked'), true);
});

run_test('admin_realm_dropdown_stream_list', () => {
    let html = "<ul>";
    const args = {
        stream: {
            name: "Italy",
            subscriber_count: 9,
            stream_id: 18,
        },
    };
    html += render("settings/admin_realm_dropdown_stream_list", args);
    html += "</ul>";

    const link = $(html).find("a");
    const list_item = $(html).find("li");

    assert.equal(link.text().trim(), "Italy");
    assert(list_item.hasClass("stream_name"));
    assert.equal(list_item.attr("data-stream-id"), "18");
});

run_test('admin_default_streams_list', () => {
    let html = '<table>';
    const streams = ['devel', 'trac', 'zulip'];

    // When the logged in user is admin
    _.each(streams, function (stream) {
        const args = {
            stream: {name: stream, invite_only: false},
            can_modify: true,
        };
        html += render('admin_default_streams_list', args);
    });
    html += "</table>";
    let span = $(html).find(".default_stream_name").first();
    assert.equal(span.text(), "devel");

    // When the logged in user is not admin
    html = '<table>';
    _.each(streams, function (stream) {
        const args = {
            stream: {name: stream, invite_only: false},
            can_modify: false,
        };
        html += render('admin_default_streams_list', args);
    });
    html += "</table>";
    span = $(html).find(".default_stream_name").first();
    assert.equal(span.text(), "devel");
});

run_test('admin_emoji_list', () => {
    const args = {
        emoji: {
            name: "MouseFace",
            display_name: "MouseFace",
            source_url: "http://emojipedia-us.s3.amazonaws.com/cache/46/7f/467fe69069c408e07517621f263ea9b5.png",
        },
    };

    let html = '';
    html += '<tbody id="admin_emoji_table">';
    html += render('admin_emoji_list', args);
    html += '</tbody>';

    const emoji_name = $(html).find('tr.emoji_row').first().find('span.emoji_name');
    const emoji_url = $(html).find('tr.emoji_row').first().find('span.emoji_image img');

    assert.equal(emoji_name.text(), 'MouseFace');
    assert.equal(emoji_url.attr('src'), 'http://emojipedia-us.s3.amazonaws.com/cache/46/7f/467fe69069c408e07517621f263ea9b5.png');
});

run_test('admin_profile_field_list', () => {

    // When the logged in user is admin
    let args = {
        profile_field: {
            name: "teams",
            type: "Long text",
        },
        can_modify: true,
    };

    let html = '';
    html += '<tbody id="admin_profile_fields_table">';
    html += render('admin_profile_field_list', args);
    html += '</tbody>';

    let field_name = $(html).find('tr.profile-field-row').first().find('span.profile_field_name');
    let field_type = $(html).find('tr.profile-field-row').first().find('span.profile_field_type');
    let td = $(html).find('tr.profile-field-row').first().find('td');

    assert.equal(field_name.text(), 'teams');
    assert.equal(field_type.text(), 'Long text');
    assert.equal(td.length, 4);

    // When the logged in user is not admin
    args = {
        profile_field: {
            name: "teams",
            type: "Long text",
        },
        can_modify: false,
    };

    html = '';
    html += '<tbody id="admin_profile_fields_table">';
    html += render('admin_profile_field_list', args);
    html += '</tbody>';

    field_name = $(html).find('tr.profile-field-row').first().find('span.profile_field_name');
    field_type = $(html).find('tr.profile-field-row').first().find('span.profile_field_type');
    td = $(html).find('tr.profile-field-row').first().find('td');

    assert.equal(field_name.text(), 'teams');
    assert.equal(field_type.text(), 'Long text');
    assert.equal(td.length, 3);
});

run_test('admin_filter_list', () => {

    // When the logged in user is admin
    let args = {
        filter: {
            pattern: "#(?P<id>[0-9]+)",
            url_format_string: "https://trac.example.com/ticket/%(id)s",
        },
        can_modify: true,
    };

    let html = '';
    html += '<tbody id="admin_filters_table">';
    html += render('admin_filter_list', args);
    html += '</tbody>';

    let filter_pattern = $(html).find('tr.filter_row').first().find('span.filter_pattern');
    let filter_format = $(html).find('tr.filter_row').first().find('span.filter_url_format_string');

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

    filter_pattern = $(html).find('tr.filter_row').first().find('span.filter_pattern');
    filter_format = $(html).find('tr.filter_row').first().find('span.filter_url_format_string');

    assert.equal(filter_pattern.text(), '#(?P<id>[0-9]+)');
    assert.equal(filter_format.text(), 'https://trac.example.com/ticket/%(id)s');
});

run_test('admin_invites_list', () => {
    let html = '<table>';
    const invites = ['alice', 'bob', 'carl'];
    let invite_id = 0;
    _.each(invites, function (invite) {
        const args = {
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
    const buttons = $(html).find('.button');

    assert.equal($(buttons[0]).text().trim(), "translated: Revoke");
    assert($(buttons[0]).hasClass("revoke"));
    assert.equal($(buttons[0]).attr("data-invite-id"), 0);

    assert.equal($(buttons[3]).text().trim(), "translated: Resend");
    assert($(buttons[3]).hasClass("resend"));
    assert.equal($(buttons[3]).attr("data-invite-id"), 1);

    const span = $(html).find(".email").first();
    assert.equal(span.text(), "alice@zulip.com");
});

run_test('admin_tab', () => {
    const args = {
        realm_name: 'Zulip',
    };
    const html = render('admin_tab', args);
    const admin_features = ["admin_users_table", "admin_bots_table",
                            "admin_deactivated_users_table", "admin_invites_table"];
    _.each(admin_features, function (admin_feature) {
        assert.notEqual($(html).find("#" + admin_feature).length, 0);
    });
    assert.equal($(html).find("input.admin-realm-name").val(), 'Zulip');
});

run_test('admin_user_group_list', () => {
    const args = {
        user_group: {
            id: "9",
            name: "uranohoshi",
            description: "Students at Uranohoshi Academy",
        },
    };

    let html = '';
    html += '<div id="user-groups">';
    html += render('admin_user_group_list', args);
    html += '</div>';

    const group_id = $(html).find('.user-group').first().prop('id');
    const group_pills_id = $(html).find('.user-group').first().find('.pill-container').attr('data-group-pills');
    const group_name_display = $(html).find('.user-group').first().find('.name').text().trim().replace(/\s+/g, ' ');
    const group_description = $(html).find('.user-group').first().find('.description').text().trim().replace(/\s+/g, ' ');

    assert.equal(group_id, '9');
    assert.equal(group_pills_id, '9');
    assert.equal(group_name_display, 'uranohoshi');
    assert.equal(group_description, 'Students at Uranohoshi Academy');
});

run_test('admin_user_list', () => {
    let html = '<table>';
    const users = ['alice', 'bob', 'carl'];

    // When the logged in user is admin
    _.each(users, function (user) {
        const args = {
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

    let buttons = $(html).find('.button');

    assert.equal($(buttons[0]).text().trim(), "translated: Deactivate");
    assert($(buttons[0]).hasClass("deactivate"));

    assert.equal($(buttons[1]).attr('title').trim(), "translated: Edit user");
    assert($(buttons[1]).hasClass("open-user-form"));

    // When the logged in user is not admin
    html = '<table>';
    _.each(users, function (user) {
        const args = {
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
    // No buttons should be availabe to non-admins
    assert.equal($(buttons).length, 0);
});

run_test('alert_word_settings_item', () => {
    let html = '<ul id="alert-words">';
    const words = ['lunch', 'support'];
    let args;
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

    const li = $(html).find("li.alert-word-item").first();
    const value = li.find('.value');
    let button = li.find('button');
    assert.equal(li.attr('data-word'), 'lunch');
    assert.equal(value.length, 1);
    assert.equal(value.text(), 'lunch');
    assert.equal(button.attr('title'), 'translated: Delete alert word');
    assert.equal(button.attr('data-word'), 'lunch');

    const title = $(html).find('.new-alert-word-section-title');
    const textbox = $(html).find('#create_alert_word_name');
    button = $(html).find('#create_alert_word_button');
    assert.equal(title.length, 1);
    assert.equal(title.text().trim(), 'translated: Add a new alert word');
    assert.equal(textbox.length, 1);
    assert.equal(textbox.attr('maxlength'), 100);
    assert.equal(textbox.attr('placeholder'), 'translated: Alert word');
    assert.equal(textbox.attr('class'), 'required');
    assert.equal(button.length, 1);
    assert.equal(button.text().trim(), 'translated: Add alert word');

});

run_test('all_messages_sidebar_actions', () => {
    render('all_messages_sidebar_actions');
});

run_test('announce_stream_docs', () => {
    render('announce_stream_docs');
});

run_test('bankruptcy_modal', () => {
    const args = {
        unread_count: 99,
    };
    const html = render('bankruptcy_modal', args);
    const count = $(html).find("p b");
    assert.equal(count.text(), 99);
});

run_test('settings/admin_auth_methods_list', () => {
    const args = {
        method: "Email",
        enabled: false,
    };

    let html = '';
    html += '<tbody>';
    html += render('settings/admin_auth_methods_list', args);
    html += '</tbody>';

    const method = $(html).find('tr.method_row').first().find('span.method');
    assert.equal(method.text(), 'Email');
    assert.equal(method.is(":checked"), false);
});

run_test('bookend', () => {
    // Do subscribed/unsubscribed cases here.
    let args = {
        bookend_content: "subscribed to stream",
        trailing: true,
        subscribed: true,
    };
    let html;

    html = render('bookend', args);
    assert.equal($(html).text().trim(), "subscribed to stream\n    \n        \n            translated: Unsubscribe");

    args = {
        bookend_content: "Not subscribed to stream",
        trailing: true,
        subscribed: false,
    };

    html = render('bookend', args);
    assert.equal($(html).text().trim(), 'Not subscribed to stream\n    \n        \n            translated: Subscribe');

});

run_test('bot_avatar_row', () => {
    let html = '';
    const args = {
        email: "hamlet@zulip.com",
        api_key: "123456ABCD",
        name: "Hamlet",
        avatar_url: "/hamlet/avatar/url",
    };
    html += render('bot_avatar_row', args);

    const img = $(html).find("img");
    assert.equal(img.attr('src'), '/hamlet/avatar/url');
});

run_test('bot_owner_select', () => {
    const args = {
        users_list: [
            {
                email: "hamlet@zulip.com",
                api_key: "123456ABCD",
                full_name: "Hamlet",
                avatar_url: "/hamlet/avatar/url",
            },
        ],
    };
    const html = render('bot_owner_select', args);
    const option = $(html).find("option").last();
    assert.equal(option.val(), "hamlet@zulip.com");
    assert.equal(option.text(), "Hamlet");
});


run_test('compose_invite_users', () => {
    const args = {
        email: 'hamlet@zulip.com',
        name: 'Hamlet',
        can_subscribe_other_users: true,
    };
    let html = render('compose_invite_users', args);
    let button = $(html).find("button").first();
    assert.equal(button.text(), "translated: Subscribe");

    args.can_subscribe_other_users = false;
    html = render('compose_invite_users', args);
    button = $(html).find("button").first();
    assert.equal(button.length, 0);
});

run_test('compose_all_everyone', () => {
    const args = {
        count: '101',
        name: 'all',
    };
    const html = render('compose_all_everyone', args);
    const button = $(html).find("button").first();
    assert.equal(button.text(), "translated: Yes, send");
    const error_msg = $(html).find('span.compose-all-everyone-msg').text().trim();
    assert.equal(error_msg, "translated: Are you sure you want to mention all 101 people in this stream?");
});

run_test('compose_announce', () => {
    const args = {
        count: '101',
    };
    const html = render('compose_announce', args);
    const button = $(html).find("button").first();
    assert.equal(button.text(), "translated: Yes, send");
    const error_msg = $(html).find('span.compose-announce-msg').text().trim();
    assert.equal(error_msg, "translated: This stream is reserved for announcements.  Are you sure you want to message all 101 people in this stream?");
});

run_test('compose_not_subscribed', () => {
    let html = render('compose_not_subscribed', {should_display_sub_button: true});
    let button = $(html).find("button").first();
    assert.equal(button.text(), "translated: Subscribe");
    html = render('compose_not_subscribed', {should_display_sub_button: false});
    button = $(html).find("button").first();
    assert.equal(button.length, 0);
});

run_test('compose_notification', () => {
    const args = {
        note: "You sent a message to a muted topic.",
        link_text: "Narrow to here",
        link_msg_id: "99",
        link_class: "compose_notification_narrow_by_topic",
    };
    let html = '<div  id="out-of-view-notification" class="notification-alert">';
    html += render('compose_notification', args);
    html += '</div>';
    const a = $(html).find("a.compose_notification_narrow_by_topic");
    assert.equal(a.text(), "Narrow to here");
});

run_test('compose_private_stream_alert', () => {
    const args = {
        stream_name: 'Denmark',
    };
    const html = render('compose_private_stream_alert', args);
    assert($(html).hasClass('compose_private_stream_alert'));

    const actual_text = $(html).text();
    const expected_text = 'translated: Warning: Denmark is a private stream.';
    assert(actual_text.indexOf(expected_text) >= 1);
});

run_test('custom_user_profile_field', () => {
    const field = {name: "GitHub user name", id: 2, hint: "Or link to profile"};
    const args = {field: field, field_value: {value: "@GitHub", rendered_value: "<p>@GitHub</p>"}, field_type: "text"};
    const html = render('settings/custom_user_profile_field', args);
    assert.equal($(html).attr('data-field-id'), 2);
    assert.equal($(html).find('.custom_user_field_value').val(), "@GitHub");
    assert.equal($(html).find('.field_hint').text(), "Or link to profile");
    assert.equal($(html).find('label').text(), "GitHub user name");
});

run_test('deactivate_stream_modal', () => {
    const args = {
        stream_name: "Public stream",
        stream_id: 1,
    };
    const html = render('settings/deactivation_stream_modal', args);

    const modal_header = $(html).find("#deactivation_stream_modal_label");
    assert.equal(modal_header.text(), "translated: Delete stream " + args.stream_name);

    const button = $(html).find("#do_deactivate_stream_button");
    assert.equal(button.text(), "translated: Yes, delete this stream");
    assert.equal(button.data('stream-id'), args.stream_id);
});

run_test('settings/dev_env_email_access', () => {
    render('settings/dev_env_email_access');
});

run_test('draft_table_body', () => {
    const args = {
        drafts: [
            {
                draft_id: '1',
                is_stream: true,
                stream: 'all',
                stream_color: '#FF0000',  // hsl(0, 100%, 50%)
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

    let html = '';
    html += '<div id="drafts_table">';
    html += render('draft_table_body', args);
    html += '</div>';

    const row_1 = $(html).find(".draft-row[data-draft-id='1']");
    assert.equal(row_1.find(".stream_label").text().trim(), "all");
    assert.equal(row_1.find(".stream_label").css("background"), "rgb(255, 0, 0)");
    assert.equal(row_1.find(".stream_topic").text().trim(), "tests");
    assert(!row_1.find(".message_row").hasClass("private-message"));
    assert.equal(row_1.find(".message_content").text().trim(), "Public draft");

    const row_2 = $(html).find(".draft-row[data-draft-id='2']");
    assert.equal(row_2.find(".stream_label").text().trim(), "translated: You and Jordan, Michael");
    assert(row_2.find(".message_row").hasClass("private-message"));
    assert.equal(row_2.find(".message_content").text().trim(), "Private draft");
});

run_test('emoji_popover', () => {
    const args = {
        class: "emoji-info-popover",
    };
    let html = "<div>";
    html += render('emoji_popover', args);
    html += "</div>";
    const popover = $(html).find(".popover");
    assert(popover.hasClass("emoji-info-popover"));
});

run_test('emoji_popover_content', () => {
    const args = {
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
                        emoji_code: '100',
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

    let html = '<div style="height: 250px">';
    html += render('emoji_popover_content', args);
    html += "</div>";
    // test to make sure the first emoji is present in the popover
    const first_emoji = $(html).find(".emoji-100");
    assert.equal(first_emoji.length, 1);

    const categories = $(html).find(".emoji-popover-tab-item");
    assert.equal(categories.length, 2);

    const category_1 = $(html).find(".emoji-popover-tab-item[data-tab-name = 'Test']");
    assert(category_1.hasClass("active"));
});

run_test('emoji_popover_search_results', () => {
    const args = {
        message_id: 1,
        search_results: [
            {
                has_reacted: false,
                is_realm_emoji: false,
                name: 'test-1',
                emoji_code: 'test-1',
            },
            {
                has_reacted: true,
                is_realm_emoji: false,
                name: 'test-2',
                emoji_code: 'test-2',
            },
        ],
    };
    let html = "<div>";
    html += render("emoji_popover_search_results", args);
    html += "</div>";
    const used_emoji = $(html).find(".emoji-test-2").parent();
    assert(used_emoji.hasClass("reaction"));
    assert(used_emoji.hasClass("reacted"));
});

run_test('emoji_showcase', () => {
    const args = {
        emoji_dict: {
            name: "thumbs_up",
            is_realm_emoji: false,
            emoji_code: "1f44d",
            has_reacted: false,
        },
    };
    const html = render("emoji_showcase", args);
    const emoji_div = $(html).find(".emoji");
    const canonical_name = $(html).find(".emoji-canonical-name");

    assert.equal(emoji_div.length, 1);
    assert(emoji_div.hasClass("emoji-1f44d"));
    assert.equal(canonical_name.text(), "thumbs_up");
    assert.equal(canonical_name.attr("title"), "thumbs_up");
});

run_test('group_pms', () => {
    const args = {
        group_pms: [
            {
                fraction_present: 0.1,
                emails: "alice@zulip.com,bob@zulip.com",
                short_name: "Alice and Bob",
                name: "Alice and Bob",
            },
        ],
    };
    const html = render('group_pms', args);

    const a = $(html).find("a").first();
    assert.equal(a.text(), 'Alice and Bob');
});

run_test('hotspot_overlay', () => {
    const args = {
        title: 'Start a new conversation',
        name: 'intro_compose',
        description: 'Click the "New topic" button to start a new conversation.',
    };

    const html = render('hotspot_overlay', args);

    assert.equal($(html).attr('id'), 'hotspot_intro_compose_overlay');
    assert.equal($(html).find('.hotspot-title').text(), 'Start a new conversation');
    assert.equal(
        $(html).find('.hotspot-description').text(),
        'Click the "New topic" button to start a new conversation.'
    );
});

run_test('input_pill', () => {
    const args = {
        id: 22,
        display_value: 'King Hamlet',
    };

    const html = render('input_pill', args);

    assert($(html).hasClass('pill'));
});

run_test('intro_reply_hotspot', () => {
    const html = render('intro_reply_hotspot', {});

    assert($(html).hasClass('hotspot-message'));
});

run_test('invite_subscription', () => {
    const args = {
        streams: [
            {
                name: "devel",
            },
            {
                name: "social",
            },
        ],
    };
    const html = render('invite_subscription', args);

    const input = $(html).find("label").first();
    assert.equal(input.text().trim(), "#devel");
});

run_test('single_message', () => {
    const message =  {
        msg: {
            include_recipient: true,
            display_recipient: 'devel',
            is_stream: true,
            content: 'This is message one.',
            last_edit_timestr: '11:00',
            starred: true,
            starred_status: "Unstar",
        },
    };

    let html = render('single_message', message);
    html = '<div class="message_table focused_table" id="zfilt">' + html + '</div>';

    const first_message = $(html).find("div.messagebox").first();

    const first_message_text = first_message.find(".message_content").text().trim();
    assert.equal(first_message_text, "This is message one.");

    const starred_title = first_message.find(".star").attr("title");
    assert.equal(starred_title, "translated: Unstar this message (*)");
});

run_test('message_edit_form', () => {
    const args = {
        topic: "lunch",
        content: "Let's go to lunch!",
        is_stream: true,
    };
    const html = render('message_edit_form', args);

    const textarea = $(html).find("textarea.message_edit_content");
    assert.equal(textarea.text(), "Let's go to lunch!");
});

run_test('message_group', () => {
    const messages = [
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
                match_content: 'This is message <span class="highlight">two</span>.\n<pre>code\nblock</pre>',
                is_stream: true,
                unread: true,
                id: 2,
            },
        },
    ];

    const groups = [
        {
            display_recipient: "support",
            is_stream: true,
            message_ids: [1, 2],
            message_containers: messages,
            group_date_divider_html: '"<span class="timerender82">Jan&nbsp;07</span>"',
            show_group_date_divider: true,
            match_topic: '<span class="highlight">two</span> messages',
        },
    ];

    render('loader');
    const html = render('message_group', {message_groups: groups, use_match_properties: true});

    const first_message_text = $(html).next('.recipient_row').find('div.messagebox').first().find('.message_content').text().trim();
    assert.equal(first_message_text, "This is message one.");

    const last_message_html = $(html).next('.recipient_row').find('div.messagebox').last().find('.message_content').html().trim();
    assert.equal(last_message_html, 'This is message <span class="highlight">two</span>.\n<pre>code\nblock</pre>');

    const highlighted_topic_word = $(html).find('a.narrows_by_topic .highlight').text();
    assert.equal(highlighted_topic_word, 'two');
});

run_test('message_edit_history', () => {
    const message = {
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
    const html = "<div>" + render('message_edit_history', {
        edited_messages: message.edit_history,
    }) + "</div>";
    const edited_message = $(html).find("div.messagebox-content");
    assert.equal(edited_message.text().trim(),
                 "1468132659\n        Let\'s go to lunchdinner!\n        Edited by Alice");
});

run_test('message_and_topic_edit_history', () => {
    const message = {
        content: "Let's go to lunch!",
        edit_history: [
            {
                body_to_render: "<p>Let's go to " +
                                    "<span class='highlight_text_deleted'>lunch</span>" +
                                    "<span class='highlight_text_inserted'>dinner</span>" +
                                "!</p>",
                new_topic: 'Lunch',
                prev_topic: 'Dinner',
                topic_edited: true,
                timestamp: 1468132659,
                edited_by: 'Alice',
                posted_or_edited: "Edited by",
            },
        ],
    };
    const html = "<div>" + render('message_edit_history', {
        edited_messages: message.edit_history,
    }) + "</div>";
    const edited_message = $(html).find("div.messagebox-content");
    assert.equal(edited_message.text().trim(),
                 "1468132659\n        Topic: Lunch Dinner\n        Let\'s go to lunchdinner!\n        Edited by Alice");
});

run_test('topic_edit_history', () => {
    const message = {
        content: "Let's go to lunch!",
        edit_history: [
            {
                prev_topic: 'Dinner',
                new_topic: 'Lunch',
                topic_edited: true,
                timestamp: 1468132659,
                edited_by: 'Alice',
                posted_or_edited: "Topic edited by",
            },
        ],
    };
    const html = "<div>" + render('message_edit_history', {
        edited_messages: message.edit_history,
    }) + "</div>";
    const edited_message = $(html).find("div.messagebox-content");
    assert.equal(edited_message.text().trim(),
                 "1468132659\n        Topic: Lunch Dinner\n        Topic edited by Alice");
});

run_test('message_reaction', () => {
    const args = {
        class: 'message_reaction',
        emoji_name: 'smile',
        emoji_code: '1f604',
        local_id: 'unicode_emoji,smile,1f604',
        message_id: '1',
    };

    let html = '';
    html += '<div>';
    html += render('message_reaction', args);
    html += '</div>';

    const reaction = $(html).find(".message_reaction");
    assert.equal(reaction.data("reaction-id"), "unicode_emoji,smile,1f604");
    assert(reaction.find(".emoji").hasClass("emoji-1f604"));
});

run_test('more_topics', () => {
    const html = render('more_topics');

    assert($(html).hasClass('show-more-topics'));
});

run_test('new_stream_users', () => {
    const args = {
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

    const html = render('new_stream_users', args);

    const label = $(html).find("label").first();
    assert.equal(label.text().trim(), 'King Lear (lear@zulip.com)');
});

run_test('non_editable_user_group', () => {
    const args = {
        user_group: {
            id: "9",
            name: "uranohoshi",
            description: "Students at Uranohoshi Academy",
        },
    };

    let html = '';
    html += '<div id="user-groups">';
    html += render('non_editable_user_group', args);
    html += '</div>';

    const group_id = $(html).find('.user-group').first().prop('id');
    const group_pills_id = $(html).find('.user-group').first().find('.pill-container').attr('data-group-pills');
    const group_name_display = $(html).find('.user-group').first().find('.name').text().trim().replace(/\s+/g, ' ');
    const group_description = $(html).find('.user-group').first().find('.description').text().trim().replace(/\s+/g, ' ');

    assert.equal(group_id, '9');
    assert.equal(group_pills_id, '9');
    assert.equal(group_name_display, 'uranohoshi');
    assert.equal(group_description, 'Students at Uranohoshi Academy');
});

run_test('notification', () => {
    const args = {
        content: "Hello",
        gravatar_url: "/gravatar/url",
        title: "You have a notification",
    };

    const html = render('notification', args);

    const title = $(html).find(".title");
    assert.equal(title.text().trim(), 'You have a notification');
});

run_test('reminder_popover_content', () => {
    const args = {
        message: {
            is_stream: true,
            id: "420",
            stream: "devel",
            sender_full_name: "Iago",
        },
        can_edit_message: true,
        can_mute_topic: true,
        narrowed: true,
    };

    let html = '<div style="height: 250px">';
    html += render('remind_me_popover_content', args);
    html += "</div>";
    const link = $(html).find("a.remind.custom");
    assert.equal(link.text().trim(), 'translated: Select date and time');
});

run_test('revoke_invite_modal', () => {
    const args = {
        is_multiuse: false,
        email: "iago@zulip.com",
    };

    let html = "<div>";
    html += render('settings/revoke_invite_modal', args);
    html += "</div>";
    assert.equal($(html).find("p strong").text(), "iago@zulip.com");
});

run_test('settings_tab', () => {
    const page_param_checkbox_options = {
        enable_stream_desktop_notifications: true,
        enable_stream_push_notifications: true,
        enable_stream_audible_notifications: true,
        enable_desktop_notifications: true,
        enable_sounds: true,
        enable_offline_email_notifications: true,
        enable_offline_push_notifications: true,
        enable_online_push_notifications: true,
        enable_digest_emails: true,
        realm_digest_emails_enabled: true,
        realm_name_in_notifications: true,
        realm_push_notifications_enabled: true,
        wildcard_mentions_notify: true,
    };
    const page_params = $.extend(page_param_checkbox_options, {
        full_name: "Alyssa P. Hacker", password_auth_enabled: true,
        avatar_url: "https://google.com",
    });

    const checkbox_ids = [
        "enable_stream_desktop_notifications",
        "enable_stream_push_notifications",
        "enable_stream_audible_notifications",
        "enable_desktop_notifications",
        "enable_sounds",
        "enable_offline_push_notifications",
        "enable_online_push_notifications",
        "enable_digest_emails",
        "realm_name_in_notifications",
        "wildcard_mentions_notify",
    ];

    // Render with all booleans set to true.
    let html = render('settings_tab', {
        page_params: page_params,
        notification_settings: settings_notifications.all_notifications.settings,
    });

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
    const parent_elem = $('#pm_content_in_desktop_notifications_label').wrap("<div></div>");

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

});

run_test('stream_member_list_entry', () => {
    const everyone_items = ["subscriber-name", "subscriber-email"];
    const admin_items = ["remove-subscriber-button"];

    // First, as non-admin.
    let html = render('stream_member_list_entry',
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
});

run_test('stream_sidebar_actions', () => {
    const args = {
        stream: {
            color: 'red',
            name: 'devel',
            is_muted: false,
            id: 55,
        },
    };

    const html = render('stream_sidebar_actions', args);

    const li = $(html).find("li").first();
    assert.equal(li.text().trim(), 'translated: Stream settings');
});

run_test('stream_sidebar_row', () => {
    const args = {
        name: "devel",
        color: "red",
        dark_background: "maroon",
        uri: "/devel/uri",
        id: 999,
    };

    let html = '<ul id="stream_filters">';
    html += render('stream_sidebar_row', args);
    html += '</ul>';

    const swatch = $(html).find(".stream-privacy");
    assert.equal(swatch.attr('id'), 'stream_sidebar_privacy_swatch_999');

    // test to ensure that the hashtag element from stream_privacy exists.
    assert.equal($(html).find(".stream-privacy").children("*").attr("class"), "hashtag");
});

run_test('subscription_invites_warning_modal', () => {
    const html = render('subscription_invites_warning_modal');

    const button = $(html).find(".close-invites-warning-modal").last();
    assert.equal(button.text(), 'translated: Go back');
});

run_test('subscription_settings', () => {
    const sub = {
        name: 'devel',
        subscribed: true,
        notifications: true,
        is_admin: true,
        render_subscribers: true,
        color: 'purple',
        invite_only: true,
        can_change_stream_permissions: true,
        email_address: 'xxxxxxxxxxxxxxx@zulip.com',
        stream_id: 888,
        is_muted: false,
    };

    let html = '';
    page_params.realm_push_notifications_enabled = false;
    const check_realm_setting = {
        push_notifications: !page_params.realm_push_notifications_enabled,
    };

    html += render('subscription_settings', {
        sub: sub,
        settings: stream_edit.stream_settings(sub),
        realm_settings: check_realm_setting,
    });

    const div = $(html).find(".subscription-type");
    assert(div.text().indexOf('private stream') > 0);

    const anchor = $(html).find(".change-stream-privacy").first();
    assert.equal(anchor.text(), "[translated: Change]");
});


run_test('subscription_stream_privacy_modal', () => {
    const args = {
        stream_id: 999,
        is_private: true,
        is_admin: true,
    };
    const html = render('subscription_stream_privacy_modal', args);

    const other_options = $(html).find("input[name=privacy]");
    assert.equal(other_options[0].value, 'public');
    assert.equal(other_options[1].value, 'invite-only-public-history');
    assert.equal(other_options[2].value, 'invite-only');

    const is_announcement_only = $(html).find("input[name=is-announcement-only]");
    assert.equal(is_announcement_only.prop('checked'), false);

    const button = $(html).find("#change-stream-privacy-button");
    assert(button.hasClass("btn-danger"));
    assert.equal(button.text().trim(), "translated: Save changes");
});


run_test('subscription_table_body', () => {
    // We are mostly deprecating template tests,
    // but we try to make sure rendering does not
    // crash.
    render('subscription_table_body', {});
});


run_test('subscriptions', () => {
    const args = {
        subscriptions: [
            {
                name: 'devel',
                subscribed: true,
                notifications: true,
                is_admin: true,
                render_subscribers: true,
                color: 'purple',
                invite_only: true,
                email_address: 'xxxxxxxxxxxxxxx@zulip.com',
                stream_id: 888,
                is_muted: false,
            },
            {
                name: 'social',
                color: 'green',
                stream_id: 999,
            },
        ],
    };

    let html = '';
    html += '<div>';
    html += render('subscriptions', args);
    html += '</div>';

    const span = $(html).find(".stream-name").first();
    assert.equal(span.text(), 'devel');
});


run_test('tab_bar', () => {
    const args = {
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

    const html = render('tab_bar', args);

    const a = $(html).find("li").first();
    assert.equal(a.text().trim(), 'Home');
});

run_test('topic_edit_form', () => {
    const html = render('topic_edit_form');

    const button = $(html).find("button").first();
    assert.equal(button.find("i").attr("class"), 'fa fa-check');
});

run_test('topic_list_item', () => {
    const args = {
        is_muted: false,
        topic_name: 'lunch',
        url: '/lunch/url',
        unread: 5,
    };

    const html = render('topic_list_item', args);

    assert.equal($(html).attr('data-topic-name'), 'lunch');
});


run_test('topic_sidebar_actions', () => {
    let args = {
        stream_name: 'social',
        topic_name: 'lunch',
        can_mute_topic: true,
        is_admin: false,
    };
    let html = render('topic_sidebar_actions', args);

    const a = $(html).find("a.narrow_to_topic");
    assert.equal(a.text().trim(), 'translated: Narrow to topic lunch');

    let delete_topic_option = $(html).find("a.sidebar-popover-delete-topic-messages");
    assert.equal(delete_topic_option.length, 0);

    args = {
        is_admin: true,
    };
    html = render('topic_sidebar_actions', args);

    delete_topic_option = $(html).find("a.sidebar-popover-delete-topic-messages");
    assert.equal(delete_topic_option.length, 1);
});

run_test('delete_topic_modal', () => {
    const args = {
        topic_name: 'lunch',
    };
    const html = render('delete_topic_modal', args);

    const modal_body = $(html).find('.modal-body');
    assert(modal_body.text().indexOf('delete all messages in lunch?') > 0);
});

run_test('typeahead_list_item', () => {
    const args = {
        primary: 'primary-text',
        secondary: 'secondary-text',
        img_src: 'https://zulip.org',
        is_emoji: true,
        has_image: true,
        has_secondary: true,
    };

    const html = '<div>' + render('typeahead_list_item', args) + '</div>';

    assert.equal($(html).find('.emoji').attr('src'), 'https://zulip.org');
    assert.equal($(html).find('strong').text().trim(), 'primary-text');
    assert.equal($(html).find('small').text().trim(), 'secondary-text');
});

run_test('typing_notifications', () => {
    const args = {
        users: [{
            full_name: 'Hamlet',
            email: 'hamlet@zulip.com',
        }],
    };

    let html = '';
    html += '<ul>';
    html += render('typing_notifications', args);
    html += '</ul>';

    const li = $(html).find('li').first();
    assert.equal(li.text(), 'Hamlet is typing...');

});

run_test('upload_space_stats', () => {
    let args = {
        show_upgrade_message: true,
        percent_used: 50,
        upload_quota: "1 GB",
    };
    let html = render('settings/upload_space_stats', args);
    assert.equal($(html).text().trim(), "translated: Organization using 50% of 1 GB.\n    translated: Upgrade for more space.");

    args = {
        show_upgrade_message: false,
        percent_used: 10,
        upload_quota: "5 GB",
    };
    html = render('settings/upload_space_stats', args);
    assert.equal($(html).text().trim(), "translated: Organization using 10% of 5 GB.");
});

run_test('user_group_info_popover', () => {
    const html = render('user_group_info_popover');

    $(html).hasClass('popover message-info-popover group-info-popover');
});

run_test('user_group_info_popover_content', () => {
    const args = {
        group_name: 'groupName',
        group_description: 'groupDescription',
        members: [
            {
                full_name: 'Active Alice',
                user_last_seen_time_status: 'time',
                is_bot: false,
            },
            {
                full_name: 'Bot Bob',
                user_last_seen_time_status: 'time',
                is_bot: true,
            },
            {
                full_name: 'Inactive Imogen',
                user_last_seen_time_status: 'time',
                is_bot: false,
            },
        ],
    };

    const html = render('user_group_info_popover_content', args);

    const allUsers = $(html).find("li");
    assert.equal($(allUsers[0]).text().trim(), 'Active Alice');
    assert.equal($(allUsers[1]).text().trim(), 'Bot Bob');
    assert.equal($(allUsers[2]).text().trim(), 'Inactive Imogen');

    assert.equal($(html).find('.group-name').text().trim(), 'groupName');
    assert.equal($(html).find('.group-description').text().trim(), 'groupDescription');
});

run_test('no_arrow_popover', () => {
    const html = render('no_arrow_popover', {class: 'message-info-popover'});

    $(html).hasClass('popover message-info-popover');
});

run_test('user_info_popover_content', () => {
    const args = {
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

    const html = render('user_info_popover_content', args);

    const a = $(html).find("a.narrow_to_private_messages");
    assert.equal(a.text().trim(), 'translated: View private messages');
});

run_test('user_info_popover_title', () => {
    let html = render('user_info_popover_title', {user_avatar: 'avatar/hamlet@zulip.com'});

    html = '<div>' + html + '</div>';
    assert.equal($(html).find('.popover-avatar').css('background-image'), "url(avatar/hamlet@zulip.com)");
});

run_test('uploaded_files_list_popover', () => {
    const args = {
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

    const html = render('uploaded_files_list', args);
    assert.equal($(html).find('.ind-message').attr("href"), "/#narrow/id/1");
    assert.equal($(html).find('#download_attachment').attr("href"),
                 "/user_uploads/2/65/6wITdgsd63hdskjuFqEeEy7_r/file_name.txt");

});

run_test('user_presence_rows', () => {
    const args = {
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

    let html = '';
    html += '<ul class="filters">';
    html += render('user_presence_rows', args);
    html += '</ul>';

    const a = $(html).find("a").first();
    assert.equal(a.text().trim(), 'King Lear');
});

run_test('buddy_list_tooltip_content', () => {
    const args = {
        first_line: 'Iago',
        second_line: 'out to lunch',
        third_line: 'Active now',
    };

    const html = render('buddy_list_tooltip_content', args);
    const tooltip_content = $(html).find(".tooltip_inner_content");
    assert.equal(tooltip_content.text().trim(), 'Iagoout to lunchActive now');
});

run_test('user_profile_modal', () => {
    let args = {
        full_name: "Iago",
        email: "iago@zulip.com",
        profile_data: {
            author: "Shakespeare",
            book: "Othello",
        },
        show_email: true,
    };

    let html = render('user_profile_modal', args);
    let div = $(html).find("#email .value");
    assert.equal(div.text().trim(), 'iago@zulip.com');

    args = {
        full_name: "Hamlet",
        email: "hamlet@zulip.com",
        profile_data: {
            author: "Hamlet",
            book: "Othello",
        },
        show_email: false,
    };

    html = render('user_profile_modal', args);
    div = $(html).find("#email .value");
    assert.equal(div.text().trim(), '');
});

run_test('muted_topic_ui_row', () => {
    const args = {
        stream: 'Verona',
        stream_id: 99,
        topic: 'pizza',
    };

    let html = '<table id="muted-topics-table">';
    html += '<tbody>';
    html += render('muted_topic_ui_row', args);
    html += '</tbody>';
    html += '</table>';

    assert.equal($(html).find("tr").attr("data-stream-id"), 99);
    assert.equal($(html).find("tr").attr("data-topic"), "pizza");
});

run_test('embedded_bot_config_item', () => {
    const args = {
        botname: 'giphy',
        key: 'api_key',
        value: '12345678',
    };
    const html = render('embedded_bot_config_item', args);
    assert.equal($(html).attr('name'), args.botname);
    assert.equal($(html).attr('id'), args.botname + '_' + args.key);
    assert.equal($(html).find('label').text(), args.key);
    assert.equal($(html).find('input').attr('placeholder'), args.value);
});

run_test('edit_bot', () => {
    render('edit_bot');
});

run_test('edit_outgoing_webhook_service', () => {
    const args = {
        service: {base_url: "http://www.foo.bar",
                  interface: "1"},
    };
    const html = render('settings/edit_outgoing_webhook_service', args);
    assert.equal($(html).find('#edit_service_base_url').val(), args.service.base_url);
    assert.equal($(html).find('#edit_service_interface').val(), args.service.interface);
});

run_test('edit_embedded_bot_service', () => {
    const args = {
        service: {service_name: "giphy",
                  config_data: {key: "abcd1234"}},
    };
    const html = render('settings/edit_embedded_bot_service', args);
    assert.equal($(html).find('#embedded_bot_key_edit').attr('name'), 'key');
    assert.equal($(html).find('#embedded_bot_key_edit').val(), 'abcd1234');
});

run_test('archive_message_group', () => {
    // The messages list below doesn't represent the actual HTML which would be
    // feed to these handlebar templates but since the actual one is a lot bigger
    // to be included in a test case and really comes pre rendered from the backend
    // we just kinda test out the template part which is rendered on frontend with
    // some self made html for messages to insert into the handlebars.
    const messages = [
        '<p>This is message one.</p>',
        '<p>This is message two.</p>',
    ];

    const groups = [
        {
            display_recipient: "support",
            message_containers: messages,
            group_date_divider_html: '"<span class="timerender82">Jan&nbsp;07</span>"',
            show_group_date_divider: true,
        },
    ];

    const html = render('archive_message_group', {message_groups: groups});

    const first_message_text = $(html).next('.recipient_row').find('p').first().text().trim();
    assert.equal(first_message_text, "This is message one.");

    const last_message_text = $(html).next('.recipient_row').find('p').last().text().trim();
    assert.equal(last_message_text, 'This is message two.');

});

run_test('recipient_row', () => {
    // Assert HTML escaping in topic links.
    const data = {
        is_stream: true,
        topic_links: [
            'https://google.com',
            'https://<script>alert("Hello")</script>',
        ],
    };
    const html = render('recipient_row', data);
    assert(html.indexOf('<script>alert("Hello")</script>') === -1);
    assert(html.indexOf('&lt;script&gt;alert(&quot;Hello&quot;)&lt;/script&gt;') !== -1);
});

run_test('invitation_failed_error', () => {
    let err_list = [];
    err_list.push("hamlet@zulip.com: Account has been deactivated.");
    let data = {
        error_message: "We weren't able to invite anyone.",
        error_list: err_list,
        is_invitee_deactivated: true,
        is_admin: true,
    };

    let html = '<div>';
    html += render('invitation_failed_error', data);
    html += '</div>';
    let p = $(html).find('p#invitation_error_message');
    assert.equal(p.text().trim(), "We weren't able to invite anyone.");
    let li = $(html).find("li").first();
    assert.equal(li.text().trim(), "hamlet@zulip.com: Account has been deactivated.");
    let p_admin = $(html).find("p#invitation_admin_message");
    assert.equal(p_admin.text().trim(), 'translated: You can reactivate deactivated users from organization settings.');

    err_list = [];
    err_list.push("hamlet@zulip.com: Account has been deactivated.");
    data = {
        error_message: "We weren't able to invite anyone.",
        error_list: err_list,
        is_invitee_deactivated: true,
        is_admin: false,
    };

    html = '<div>';
    html += render('invitation_failed_error', data);
    html += '</div>';
    p = $(html).find("p#invitation_error_message");
    assert.equal(p.text().trim(), "We weren't able to invite anyone.");
    li = $(html).find("li").first();
    assert.equal(li.text().trim(), "hamlet@zulip.com: Account has been deactivated.");
    const msg = $(html).find("p#invitation_non_admin_message");
    assert.equal(msg.text().trim(), 'translated: Organization administrators can reactivate deactivated users.');
    p_admin = $(html).find("p#invitation_admin_message");
    assert.equal(p_admin.length, 0);

    err_list = [];
    err_list.push("othello@zulip.com: Already has an account.");
    data = {
        error_message: "We weren't able to invite anyone.",
        error_list: err_list,
        is_invitee_deactivated: false,
        is_admin: false,
    };

    html = '<div>';
    html += render('invitation_failed_error', data);
    html += '</div>';
    p = $(html).find("p#invitation_error_message");
    assert.equal(p.text().trim(), "We weren't able to invite anyone.");
    li = $(html).find("li").first();
    assert.equal(li.text().trim(), "othello@zulip.com: Already has an account.");
    p_admin = $(html).find("p#invitation_admin_message");
    assert.equal(p_admin.length, 0);

});
