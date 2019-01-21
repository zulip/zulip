set_global('channel', {});
set_global('page_params', {});
zrequire('user_status');

function initialize() {
    page_params.user_status = {
        1: {away: true},
        2: {away: true},
        3: {away: true},
    };
    user_status.initialize();
}

run_test('basics', () => {
    initialize();
    assert(user_status.is_away(2));
    assert(!user_status.is_away(99));

    assert(!user_status.is_away(4));
    user_status.set_away(4);
    assert(user_status.is_away(4));
    user_status.revoke_away(4);
    assert(!user_status.is_away(4));
});

run_test('server', () => {
    initialize();

    var away_arg;

    channel.post = (opts) => {
        away_arg = opts.data.away;
        assert.equal(opts.url, '/json/users/me/status');
    };

    assert.equal(away_arg, undefined);

    user_status.server_set_away();
    assert.equal(away_arg, true);

    user_status.server_revoke_away();
    assert.equal(away_arg, false);
});
