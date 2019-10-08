zrequire('people');

var return_false = function () { return false; };
var return_true = function () { return true; };
set_global('reload_state', {
    is_in_progress: return_false,
});

set_global('blueslip', global.make_zblueslip({
    debug: true, // testing for debug is disabled by default.
}));

var me = {
    email: 'me@example.com',
    user_id: 30,
    full_name: 'Me Myself',
    timezone: 'US/Pacific',
};

people.init();
people.add(me);
people.initialize_current_user(me.user_id);

run_test('report_late_add', () => {
    blueslip.set_test_data('error', 'Added user late: user_id=55 email=foo@example.com');
    people.report_late_add(55, 'foo@example.com');
    assert.equal(blueslip.get_test_logs('error').length, 1);
    blueslip.clear_test_data();

    reload_state.is_in_progress = return_true;
    people.report_late_add(55, 'foo@example.com');
    assert.equal(blueslip.get_test_logs('log').length, 1);
    assert.equal(blueslip.get_test_logs('log')[0].message, 'Added user late: user_id=55 email=foo@example.com');
    assert.equal(blueslip.get_test_logs('error').length, 0);
    blueslip.clear_test_data();
});

run_test('blueslip', () => {
    var unknown_email = "alicebobfred@example.com";

    blueslip.set_test_data('debug', 'User email operand unknown: ' + unknown_email);
    people.id_matches_email_operand(42, unknown_email);
    assert.equal(blueslip.get_test_logs('debug').length, 1);
    blueslip.clear_test_data();

    blueslip.set_test_data('error', 'Unknown email for get_user_id: ' + unknown_email);
    people.get_user_id(unknown_email);
    assert.equal(blueslip.get_test_logs('error').length, 1);
    blueslip.clear_test_data();

    blueslip.set_test_data('warn', 'No user_id provided for person@example.com');
    var person = {
        email: 'person@example.com',
        user_id: undefined,
        full_name: 'Person Person',
    };
    people.add(person);
    assert.equal(blueslip.get_test_logs('warn').length, 1);
    blueslip.clear_test_data();

    blueslip.set_test_data('error', 'No user_id found for person@example.com');
    var user_id = people.get_user_id('person@example.com');
    assert.equal(user_id, undefined);
    assert.equal(blueslip.get_test_logs('error').length, 1);
    blueslip.clear_test_data();

    blueslip.set_test_data('warn', 'Unknown user ids: 1,2');
    people.user_ids_string_to_emails_string('1,2');
    assert.equal(blueslip.get_test_logs('warn').length, 1);
    blueslip.clear_test_data();

    blueslip.set_test_data('warn', 'Unknown emails: ' + unknown_email);
    people.email_list_to_user_ids_string(unknown_email);
    assert.equal(blueslip.get_test_logs('warn').length, 1);
    blueslip.clear_test_data();

    var message = {
        type: 'private',
        display_recipient: [],
        sender_id: me.user_id,
    };
    blueslip.set_test_data('error', 'Empty recipient list in message');
    people.pm_with_user_ids(message);
    people.group_pm_with_user_ids(message);
    people.all_user_ids_in_pm(message);
    assert.equal(people.pm_perma_link(message), undefined);
    assert.equal(blueslip.get_test_logs('error').length, 4);
    blueslip.clear_test_data();

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
    blueslip.set_test_data('error', 'Unknown user id in message: 42');
    var reply_to = people.pm_reply_to(message);
    assert(reply_to.indexOf('?') > -1);
    assert.equal(blueslip.get_test_logs('error').length, 1);
    blueslip.clear_test_data();

    people.pm_with_user_ids = function () { return [42]; };
    people.get_person_from_user_id = function () { return; };
    blueslip.set_test_data('error', 'Unknown people in message');
    var uri = people.pm_with_url({});
    assert.equal(uri.indexOf('unk'), uri.length - 3);
    assert.equal(blueslip.get_test_logs('error').length, 1);
    blueslip.clear_test_data();
});
