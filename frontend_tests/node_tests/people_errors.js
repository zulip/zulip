zrequire('people');

set_global('blueslip', {});

var me = {
    email: 'me@example.com',
    user_id: 30,
    full_name: 'Me Myself',
    timezone: 'US/Pacific',
};

people.init();
people.add(me);
people.initialize_current_user(me.user_id);

(function test_report_late_add() {
    var message;
    global.blueslip.error = function (msg) {
        message = msg;
    };

    people.report_late_add(55, 'foo@example.com');
    assert.equal(message, 'Added user late: user_id=55 email=foo@example.com');
}());

(function test_blueslip() {
    var unknown_email = "alicebobfred@example.com";

    global.blueslip.debug = function (msg) {
        assert.equal(msg, 'User email operand unknown: ' + unknown_email);
    };

    var warning;
    global.blueslip.warn = function (w) {
        warning = w;
    };

    people.id_matches_email_operand(42, unknown_email);

    global.blueslip.error = function (msg) {
        assert.equal(msg, 'Unknown email for get_user_id: ' + unknown_email);
    };
    people.get_user_id(unknown_email);

    var person = {
        email: 'person@example.com',
        user_id: undefined,
        full_name: 'Person Person',
    };
    people.add(person);
    assert.equal(warning, 'No user_id provided for person@example.com');

    global.blueslip.error = function (msg) {
        assert.equal(msg, 'No user_id found for person@example.com');
    };
    var user_id = people.get_user_id('person@example.com');
    assert.equal(user_id, undefined);

    global.blueslip.error = function (msg) {
        assert.equal(msg, 'Unknown user ids: 1,2');
    };
    people.user_ids_string_to_emails_string('1,2');

    global.blueslip.warn = function (msg) {
        assert.equal(msg, 'Unknown emails: ' + unknown_email);
    };
    people.email_list_to_user_ids_string(unknown_email);

    var message = {
        type: 'private',
        display_recipient: [],
        sender_id: me.user_id,
    };
    global.blueslip.error = function (msg) {
        assert.equal(msg, 'Empty recipient list in message');
    };
    people.pm_with_user_ids(message);
    people.group_pm_with_user_ids(message);

    var charles = {
        email: 'charles@example.com',
        user_id: 451,
        full_name: 'Charles Dickens',
        avatar_url: 'charles.com/foo.png',
    };
    var maria = {
        email: 'athens@example.com',
        user_id: 452,
        full_name: 'Maria Athens',
    };
    people.add(charles);
    people.add(maria);

    message = {
        type: 'private',
        display_recipient: [
            {id: maria.user_id},
            {id: 42},
            {user_id: charles.user_id},
        ],
        sender_id: charles.user_id,
    };
    global.blueslip.error = function (msg) {
        assert.equal(msg, 'Unknown user id in message: 42');
    };
    var reply_to = people.pm_reply_to(message);
    assert(reply_to.indexOf('?') > -1);

    people.pm_with_user_ids = function () { return [42]; };
    people.get_person_from_user_id = function () { return; };
    global.blueslip.error = function (msg) {
        assert.equal(msg, 'Unknown people in message');
    };
    var uri = people.pm_with_url({});
    assert.equal(uri.indexOf('unk'), uri.length - 3);
}());

