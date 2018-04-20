zrequire('people');
zrequire('presence');
zrequire('util');
zrequire('buddy_data');

// The buddy_data module is mostly tested indirectly through
// activity.js, but we should feel free to add direct tests
// here.


set_global('page_params', {});

(function make_people() {
    _.each(_.range(1000, 2000), (i) => {
        const person = {
            user_id: i,
            full_name: `Person ${i}`,
            email: `person${i}@example.com`,
        };
        people.add_in_realm(person);
    });
}());

(function activate_people() {
    const server_time = 9999;
    const info = {
        website: {
            status: "active",
            timestamp: server_time,
        },
    };

    // Make 400 of the users active
    _.each(_.range(1000, 1400), (user_id) => {
        presence.set_user_status(user_id, info, server_time);
    });

    // And then 300 not active
    _.each(_.range(1400, 1700), (user_id) => {
        presence.set_user_status(user_id, {}, server_time);
    });
}());

(function test_user_ids() {
    const user_ids = buddy_data.get_filtered_and_sorted_user_ids();

    // Even though we have 900 users, we only get the 400 active
    // users.  This is a consequence of buddy_data.maybe_shrink_list.
    assert.equal(user_ids.length, 400);
}());
