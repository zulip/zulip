zrequire('user_groups');

var error_called = 0;
set_global('blueslip', {
    error: function () {
        error_called += 1;
        return undefined;
    },
});


(function test_get_user_group_from_name() {
    assert(!user_groups.get_user_group_from_name('not_existing'));
    assert.equal(error_called, 0);
}());
