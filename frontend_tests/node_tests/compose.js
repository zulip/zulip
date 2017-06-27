set_global('$', global.make_zjquery());

set_global('page_params', {
    use_websockets: false,
});

set_global('document', {
    location: {
    },
});

var i18n = global.i18n;
var noop = function () {};

add_dependencies({
    common: 'js/common',
    compose_state: 'js/compose_state',
    people: 'js/people',
    stream_data: 'js/stream_data',
    util: 'js/util',
});

var compose = require('js/compose.js');

var me = {
    email: 'me@example.com',
    user_id: 30,
    full_name: 'Me Myself',
};

var alice = {
    email: 'alice@example.com',
    user_id: 31,
    full_name: 'Alice',
};

var bob = {
    email: 'bob@example.com',
    user_id: 32,
    full_name: 'Bob',
};

people.add(me);
people.initialize_current_user(me.user_id);

people.add(alice);
people.add(bob);


(function test_validate() {
    $("#compose-send-button").removeAttr('disabled');
    $("#compose-send-button").focus();
    $("#sending-indicator").hide();
    $("#new_message_content").select(noop);
    assert(!compose.validate());
    assert(!$("#sending-indicator").visible());
    assert(!$("#compose-send-button").is_focused());
    assert.equal($("#compose-send-button").attr('disabled'), undefined);
    assert.equal($('#error-msg').html(), 'You have nothing to send!');

    $("#new_message_content").val('foobarfoobar');
    var zephyr_checked = false;
    $("#zephyr-mirror-error").is = function () {
        if (!zephyr_checked) {
            zephyr_checked = true;
            return true;
        }
        return false;
    };
    assert(!compose.validate());
    assert(zephyr_checked);
    assert.equal($('#error-msg').html(), 'You need to be running Zephyr mirroring in order to send messages!');

    compose_state.set_message_type('private');
    compose_state.recipient('');
    $("#private_message_recipient").select(noop);
    assert(!compose.validate());
    assert.equal($('#error-msg').html(), 'Please specify at least one recipient');

    compose_state.recipient('foo@zulip.com');
    global.page_params.realm_is_zephyr_mirror_realm = true;
    assert(compose.validate());

    global.page_params.realm_is_zephyr_mirror_realm = false;
    assert(!compose.validate());
    assert.equal($('#error-msg').html(), i18n.t('The recipient foo@zulip.com is not valid', {}));

    compose_state.recipient('foo@zulip.com,alice@zulip.com');
    assert(!compose.validate());
    assert.equal($('#error-msg').html(), i18n.t('The recipients foo@zulip.com,alice@zulip.com are not valid', {}));

    people.add_in_realm(bob);
    compose_state.recipient('bob@example.com');
    assert(compose.validate());

    compose_state.set_message_type('stream');
    compose_state.stream_name('');
    $("#stream").select(noop);
    assert(!compose.validate());
    assert.equal($('#error-msg').html(), 'Please specify a stream');

    compose_state.stream_name('Denmark');
    global.page_params.realm_mandatory_topics = true;
    compose_state.subject('');
    $("#subject").select(noop);
    assert(!compose.validate());
    assert.equal($('#error-msg').html(), 'Please specify a topic');
}());

(function test_set_focused_recipient() {
    var sub = {
        stream_id: 101,
        name: 'social',
        subscribed: true,
    };
    stream_data.add_sub('social', sub);

    var page = {
        '#stream': 'social',
        '#subject': 'lunch',
        '#new_message_content': 'burrito',
        '#private_message_recipient': 'alice@example.com,    bob@example.com',
    };

    global.$ = function (selector) {
        return {
            val: function () {
                return page[selector];
            },
        };
    };

    global.compose_state.get_message_type = function () {
        return 'stream';
    };

    global.$.trim = function (s) {
        return s;
    };


    var message = compose.create_message_object();
    assert.equal(message.to, 'social');
    assert.equal(message.subject, 'lunch');
    assert.equal(message.content, 'burrito');

    global.compose_state.get_message_type = function () {
        return 'private';
    };
    message = compose.create_message_object();
    assert.deepEqual(message.to, ['alice@example.com', 'bob@example.com']);
    assert.equal(message.to_user_ids, '31,32');
    assert.equal(message.content, 'burrito');

}());
