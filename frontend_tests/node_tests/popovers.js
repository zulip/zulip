set_global('$', global.make_zjquery());
set_global('i18n', global.stub_i18n);

zrequire('hash_util');
zrequire('narrow');
zrequire('narrow_state');
zrequire('people');
zrequire('presence');
zrequire('buddy_data');
zrequire('user_status');

var noop =  function () {};
$.fn.popover = noop; // this will get wrapped by our code

zrequire('popovers');
popovers.hide_user_profile = noop;

set_global('current_msg_list', {});
set_global('page_params', {
    custom_profile_fields: [],
});
set_global('rows', {});
set_global('templates', {});


set_global('message_viewport', {
    height: () => 500,
});

set_global('emoji_picker', {
    hide_emoji_popover: noop,
});

set_global('stream_popover', {
    hide_stream_popover: noop,
    hide_topic_popover: noop,
    hide_all_messages_popover: noop,
    restore_stream_list_size: noop,
});

set_global('ClipboardJS', function (sel) {
    assert.equal(sel, '.copy_link');
});

var alice = {
    email: 'alice@example.com',
    full_name: 'Alice Smith',
    user_id: 42,
    is_guest: false,
};

var me = {
    email: 'me@example.com',
    user_id: 30,
    full_name: 'Me Myself',
    timezone: 'US/Pacific',
};

function initialize_people() {
    people.init();
    people.add_in_realm(me);
    people.add_in_realm(alice);
    people.initialize_current_user(me.user_id);
}

initialize_people();

function make_image_stubber() {
    var images = [];

    function stub_image() {
        var image = {};
        image.to_$ = () => {
            return {
                on: (name, f) => {
                    assert.equal(name, "load");
                    image.load_f = f;
                },
            };
        };
        images.push(image);
        return image;
    }

    set_global('Image', function () {
        return stub_image();
    });

    return {
        get: (i) => images[i],
    };
}

run_test('sender_hover', () => {
    popovers.register_click_handlers();

    var handler = $('#main_div').get_on_handler('click', '.sender_info_hover');
    var e = {
        stopPropagation: noop,
    };

    var message = {
        id: 999,
        sender_id: alice.user_id,
    };

    user_status.set_status_text({
        user_id: alice.user_id,
        status_text: 'on the beach',
    });

    var target = $.create('click target');

    target.offset = () => {
        return {
            top: 10,
        };
    };

    rows.id = () => message.id;

    current_msg_list.get = (msg_id) => {
        assert.equal(msg_id, message.id);
        return message;
    };

    current_msg_list.select_id = (msg_id) => {
        assert.equal(msg_id, message.id);
    };

    target.closest = (sel) => {
        assert.equal(sel, '.message_row');
        return {};
    };

    templates.render = function (fn, opts) {
        switch (fn) {
        case 'no_arrow_popover':
            assert.deepEqual(opts, {
                class: 'message-info-popover',
            });
            return 'popover-html';

        case 'user_info_popover_title':
            assert.deepEqual(opts, {
                user_avatar: 'avatar/alice@example.com',
                user_is_guest: false,
            });
            return 'title-html';

        case 'user_info_popover_content':
            assert.deepEqual(opts, {
                can_set_away: false,
                can_revoke_away: false,
                user_full_name: 'Alice Smith',
                user_email: 'alice@example.com',
                user_id: 42,
                user_time: undefined,
                user_type: i18n.t('Member'),
                user_circle_class: 'user_circle_empty',
                user_last_seen_time_status: 'translated: More than 2 weeks ago',
                pm_with_uri: '#narrow/pm-with/42-alice',
                sent_by_uri: '#narrow/sender/42-alice',
                private_message_class: 'respond_personal_button',
                show_user_profile: false,
                is_me: false,
                is_active: true,
                is_bot: undefined,
                is_sender_popover: true,
                status_text: 'on the beach',
            });
            return 'content-html';

        default:
            throw Error('unrecognized template: ' + fn);
        }
    };

    $('.user_popover_email').each = noop;

    var image_stubber = make_image_stubber();

    handler.call(target, e);

    var avatar_img = image_stubber.get(0);
    assert.equal(avatar_img.src, 'avatar/42/medium');

    // todo: load image
});
