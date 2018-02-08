zrequire('muting_user');

(function test_edge_cases() {
    assert(!muting_user.is_user_muted(undefined));
}());

(function test_basic_functionality() {
    assert(!muting_user.is_user_muted(6));
    muting_user.add_muted_user([6, 'othello']);
    assert(muting_user.is_user_muted(6));

    // test idempotentcy
    muting_user.add_muted_user([6, 'othello']);
    assert(muting_user.is_user_muted(6));

    muting_user.remove_muted_user([6, 'othello']);
    assert(!muting_user.is_user_muted(6));

    // test idempotentcy
    muting_user.remove_muted_user([6, 'othello']);
    assert(!muting_user.is_user_muted(6));

    // test removing muted user who isn't muted
    muting_user.remove_muted_user([4, 'hamlet']);
    assert(!muting_user.is_user_muted(4));
}());

(function test_get_and_set_muted_users() {
    var cordelia = {id: 3, name: 'cordelia'};
    var zoe = {id: 2, name: 'zoe'};
    assert.deepEqual(muting_user.get_muted_user_names(), []);
    assert.deepEqual(muting_user.get_muted_user_ids(), []);
    muting_user.add_muted_user([6, 'othello']);
    muting_user.add_muted_user([4, 'hamlet']);
    assert.deepEqual(muting_user.get_muted_user_names().sort(), ['hamlet', 'othello']);
    assert.deepEqual(muting_user.get_muted_user_ids().sort(), [4, 6]);
    muting_user.set_muted_users([
        zoe,
        cordelia,
    ]);
    assert.deepEqual(muting_user.get_muted_user_names().sort(), ['cordelia', 'zoe']);
    assert.deepEqual(muting_user.get_muted_user_ids().sort(), [2, 3]);
}());
