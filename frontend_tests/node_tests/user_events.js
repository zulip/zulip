add_dependencies({
    people: 'js/people.js',
});

var people = global.people;

var user_events = require("js/user_events.js");

set_global('activity', {
    redraw: function () {},
});
set_global('settings_users', {
    update_user_data: function () {},
});
set_global('admin', {
    show_or_hide_menu_item: function () {},
});
set_global('page_params', {
    is_admin: true,
});

set_global('pm_list', {
    update_private_messages: function () {},
});

set_global('message_live_update', {
});

var me = {
    email: 'me@example.com',
    user_id: 30,
    full_name: 'Me Myself',
    is_admin: true,
};

function initialize() {
    people.init();
    people.add(me);
    people.initialize_current_user(me.user_id);
}

initialize();

(function test_updates() {
    var person;

    var isaac = {
        email: 'isaac@example.com',
        user_id: 32,
        full_name: 'Isaac Newton',
    };
    people.add(isaac);

    user_events.update_person({user_id: isaac.user_id, is_admin: true});
    person = people.get_by_email(isaac.email);
    assert.equal(person.full_name, 'Isaac Newton');
    assert.equal(person.is_admin, true);

    var user_id;
    var full_name;
    global.message_live_update.update_user_full_name = function (user_id_arg, full_name_arg) {
        user_id = user_id_arg;
        full_name = full_name_arg;
    };

    user_events.update_person({user_id: isaac.user_id, full_name: 'Sir Isaac'});
    person = people.get_by_email(isaac.email);
    assert.equal(person.full_name, 'Sir Isaac');
    assert.equal(person.is_admin, true);
    assert.equal(user_id, isaac.user_id);
    assert.equal(full_name, 'Sir Isaac');

    user_events.update_person({user_id: me.user_id, is_admin: false});
    assert(!global.page_params.is_admin);

    user_events.update_person({user_id: me.user_id, full_name: 'Me V2'});
    assert.equal(people.my_full_name(), 'Me V2');
    assert.equal(user_id, me.user_id);
    assert.equal(full_name, 'Me V2');

}());
