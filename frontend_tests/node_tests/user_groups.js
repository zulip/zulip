set_global('blueslip', {});
set_global('page_params', {});

zrequire('user_groups');

(function test_user_groups() {
    var students = {
        name: 'Students',
        id: 0,
    };
    global.page_params.realm_user_groups = [students];

    user_groups.initialize();
    assert.equal(user_groups.get_user_group_from_id(students.id), students);

    var admins = {
        name: 'Admins',
        id: 1,
    };
    var all = {
        name: 'Everyone',
        id: 2,
    };

    user_groups.add(admins);
    assert.equal(user_groups.get_user_group_from_id(admins.id), admins);

    var called = false;
    global.blueslip.error = function (msg) {
        assert.equal(msg, "Unknown group_id in get_user_group_from_id: " + all.id);
        called = true;
    };

    assert.equal(user_groups.get_user_group_from_id(all.id), undefined);
    assert(called);

    user_groups.remove(students);
    global.blueslip.error = function (msg) {
        assert.equal(msg, "Unknown group_id in get_user_group_from_id: " + students.id);
    };
    assert.equal(user_groups.get_user_group_from_id(students.id), undefined);
}());
