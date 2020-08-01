"use strict";

set_global("channel", {});
zrequire("user_status");

function initialize() {
    const params = {
        user_status: {
            1: {away: true, status_text: "in a meeting"},
            2: {away: true},
            3: {away: true},
        },
    };
    user_status.initialize(params);
}

run_test("basics", () => {
    initialize();
    assert(user_status.is_away(2));
    assert(!user_status.is_away(99));

    assert(!user_status.is_away(4));
    user_status.set_away(4);
    assert(user_status.is_away(4));
    user_status.revoke_away(4);
    assert(!user_status.is_away(4));

    assert.equal(user_status.get_status_text(1), "in a meeting");

    user_status.set_status_text({
        user_id: 2,
        status_text: "out to lunch",
    });
    assert.equal(user_status.get_status_text(2), "out to lunch");

    user_status.set_status_text({
        user_id: 2,
        status_text: "",
    });
    assert.equal(user_status.get_status_text(2), undefined);
});

run_test("server", () => {
    initialize();

    let sent_data;
    let success;

    channel.post = (opts) => {
        sent_data = opts.data;
        assert.equal(opts.url, "/json/users/me/status");
        success = opts.success;
    };

    assert.equal(sent_data, undefined);

    user_status.server_set_away();
    assert.deepEqual(sent_data, {away: true, status_text: undefined});

    user_status.server_revoke_away();
    assert.deepEqual(sent_data, {away: false, status_text: undefined});

    let called;

    user_status.server_update({
        status_text: "out to lunch",
        success: () => {
            called = true;
        },
    });

    success();
    assert(called);
});

run_test("defensive checks", () => {
    blueslip.expect("error", "need ints for user_id", 2);
    user_status.set_away("string");
    user_status.revoke_away("string");
});
