zrequire("typing_data");

(function test_basics() {
    // The typing_data needs to be robust with lists of
    // user ids being in arbitrary sorting order and
    // possibly in string form instead of integer. So all
    // the apparent randomness in these tests has a purpose.
    typing_data.add_typist([5, 10, 15], 15);
    assert.deepEqual(typing_data.get_group_typists([15, 10, 5]), [15]);

    // test that you can add twice
    typing_data.add_typist([5, 10, 15], 15);

    // add another id to our first group
    typing_data.add_typist([5, 10, 15], "10");
    assert.deepEqual(typing_data.get_group_typists([10, 15, 5]), [10, 15]);

    // start adding to a new group
    typing_data.add_typist([7, 15], 7);
    typing_data.add_typist([7, "15"], 15);

    // test get_all_typists
    assert.deepEqual(typing_data.get_all_typists(), [7, 10, 15]);

    // test basic removal
    assert(typing_data.remove_typist([15, 7], "7"));
    assert.deepEqual(typing_data.get_group_typists([7, 15]), [15]);

    // test removing an id that is not there
    assert(!typing_data.remove_typist([15, 7], 7));
    assert.deepEqual(typing_data.get_group_typists([7, 15]), [15]);
    assert.deepEqual(typing_data.get_all_typists(), [10, 15]);

    // remove user from one group, but "15" will still be among
    // "all typists"
    assert(typing_data.remove_typist(["15", 7], "15"));
    assert.deepEqual(typing_data.get_all_typists(), [10, 15]);

    // now remove from the other group
    assert(typing_data.remove_typist([5, 15, 10], 15));
    assert.deepEqual(typing_data.get_all_typists(), [10]);

    // test duplicate ids in a groups
    typing_data.add_typist([20, 40, 20], 20);
    assert.deepEqual(typing_data.get_group_typists([20, 40]), [20]);
}());


(function test_timers() {
    var events = {};

    var stub_timer_id = 'timer_id_stub';
    var stub_group = [5, 10, 15];
    var stub_delay = 99;
    var stub_f = 'function';

    function set_timeout(f, delay) {
        assert.equal(delay, stub_delay);
        events.f = f;
        events.timer_set = true;
        return stub_timer_id;
    }

    function clear_timeout(timer) {
        assert.equal(timer, stub_timer_id);
        events.timer_cleared = true;
    }

    function reset_events() {
        events.f = undefined;
        events.timer_cleared = false;
        events.timer_set = false;
    }

    function kickstart() {
        reset_events();
        typing_data.kickstart_inbound_timer(stub_group, stub_delay, stub_f);
    }

    function clear() {
        reset_events();
        typing_data.clear_inbound_timer(stub_group);
    }

    global.patch_builtin('setTimeout', set_timeout);
    global.patch_builtin('clearTimeout', clear_timeout);

    // first time, we set
    kickstart();
    assert.deepEqual(events, {
        f: stub_f,
        timer_cleared: false,
        timer_set: true,
    });

    // second time we clear and set
    kickstart();
    assert.deepEqual(events, {
        f: stub_f,
        timer_cleared: true,
        timer_set: true,
    });

    // first time clearing, we clear
    clear();
    assert.deepEqual(events, {
        f: undefined,
        timer_cleared: true,
        timer_set: false,
    });

    // second time clearing, we noop
    clear();
    assert.deepEqual(events, {
        f: undefined,
        timer_cleared: false,
        timer_set: false,
    });

}());

