"use strict";

const pm_conversations = zrequire("pm_conversations");
pm_conversations.recent = {};

zrequire("muting");
zrequire("unread");
zrequire("stream_data");
zrequire("stream_topic_history");
zrequire("stream_sort");
const tg = zrequire("topic_generator");

function is_even(i) {
    return i % 2 === 0;
}
function is_odd(i) {
    return i % 2 === 1;
}

run_test("basics", () => {
    let gen = tg.list_generator([10, 20, 30]);
    assert.equal(gen.next(), 10);
    assert.equal(gen.next(), 20);
    assert.equal(gen.next(), 30);
    assert.equal(gen.next(), undefined);
    assert.equal(gen.next(), undefined);

    const gen1 = tg.list_generator([100, 200]);
    const gen2 = tg.list_generator([300, 400]);
    const outers = [gen1, gen2];
    gen = tg.chain(outers);
    assert.equal(gen.next(), 100);
    assert.equal(gen.next(), 200);
    assert.equal(gen.next(), 300);
    assert.equal(gen.next(), 400);
    assert.equal(gen.next(), undefined);
    assert.equal(gen.next(), undefined);

    gen = tg.wrap([5, 15, 25, 35], 25);
    assert.equal(gen.next(), 25);
    assert.equal(gen.next(), 35);
    assert.equal(gen.next(), 5);
    assert.equal(gen.next(), 15);
    assert.equal(gen.next(), undefined);
    assert.equal(gen.next(), undefined);

    gen = tg.wrap_exclude([5, 15, 25, 35], 25);
    assert.equal(gen.next(), 35);
    assert.equal(gen.next(), 5);
    assert.equal(gen.next(), 15);
    assert.equal(gen.next(), undefined);
    assert.equal(gen.next(), undefined);

    gen = tg.wrap([5, 15, 25, 35], undefined);
    assert.equal(gen.next(), 5);

    gen = tg.wrap_exclude([5, 15, 25, 35], undefined);
    assert.equal(gen.next(), 5);

    gen = tg.wrap([5, 15, 25, 35], 17);
    assert.equal(gen.next(), 5);

    gen = tg.wrap([], 42);
    assert.equal(gen.next(), undefined);

    let ints = tg.list_generator([1, 2, 3, 4, 5]);
    gen = tg.filter(ints, is_even);
    assert.equal(gen.next(), 2);
    assert.equal(gen.next(), 4);
    assert.equal(gen.next(), undefined);
    assert.equal(gen.next(), undefined);

    ints = tg.list_generator([]);
    gen = tg.filter(ints, is_even);
    assert.equal(gen.next(), undefined);
    assert.equal(gen.next(), undefined);

    ints = tg.list_generator([10, 20, 30]);

    function mult10(x) {
        return x * 10;
    }

    gen = tg.map(ints, mult10);
    assert.equal(gen.next(), 100);
    assert.equal(gen.next(), 200);
});

run_test("reverse", () => {
    let gen = tg.reverse_list_generator([10, 20, 30]);
    assert.equal(gen.next(), 30);
    assert.equal(gen.next(), 20);
    assert.equal(gen.next(), 10);
    assert.equal(gen.next(), undefined);
    assert.equal(gen.next(), undefined);

    // If second parameter is not in the list, we just traverse the list
    // in reverse.
    gen = tg.reverse_wrap_exclude([10, 20, 30]);
    assert.equal(gen.next(), 30);
    assert.equal(gen.next(), 20);
    assert.equal(gen.next(), 10);
    assert.equal(gen.next(), undefined);
    assert.equal(gen.next(), undefined);

    gen = tg.reverse_wrap_exclude([10, 20, 30], "whatever");
    assert.equal(gen.next(), 30);
    assert.equal(gen.next(), 20);
    assert.equal(gen.next(), 10);
    assert.equal(gen.next(), undefined);
    assert.equal(gen.next(), undefined);

    // Witness the mostly typical cycling behavior.
    gen = tg.reverse_wrap_exclude([5, 10, 20, 30], 20);
    assert.equal(gen.next(), 10);
    assert.equal(gen.next(), 5);
    assert.equal(gen.next(), 30);
    assert.equal(gen.next(), undefined);
    assert.equal(gen.next(), undefined);

    gen = tg.reverse_wrap_exclude([5, 10, 20, 30], 5);
    assert.equal(gen.next(), 30);
    assert.equal(gen.next(), 20);
    assert.equal(gen.next(), 10);
    assert.equal(gen.next(), undefined);
    assert.equal(gen.next(), undefined);

    gen = tg.reverse_wrap_exclude([5, 10, 20, 30], 30);
    assert.equal(gen.next(), 20);
    assert.equal(gen.next(), 10);
    assert.equal(gen.next(), 5);
    assert.equal(gen.next(), undefined);
    assert.equal(gen.next(), undefined);

    // Test small lists.
    gen = tg.reverse_wrap_exclude([], 5);
    assert.equal(gen.next(), undefined);
    assert.equal(gen.next(), undefined);

    gen = tg.reverse_wrap_exclude([5], 5);
    assert.equal(gen.next(), undefined);
    assert.equal(gen.next(), undefined);

    gen = tg.reverse_wrap_exclude([5], 10);
    assert.equal(gen.next(), 5);
    assert.equal(gen.next(), undefined);
    assert.equal(gen.next(), undefined);
});

run_test("fchain", () => {
    const mults = function (n) {
        let ret = 0;
        return {
            next() {
                ret += n;
                return ret <= 100 ? ret : undefined;
            },
        };
    };

    let ints = tg.list_generator([29, 43]);
    let gen = tg.fchain(ints, mults);
    assert.equal(gen.next(), 29);
    assert.equal(gen.next(), 58);
    assert.equal(gen.next(), 87);
    assert.equal(gen.next(), 43);
    assert.equal(gen.next(), 86);
    assert.equal(gen.next(), undefined);
    assert.equal(gen.next(), undefined);

    ints = tg.wrap([33, 34, 37], 37);
    ints = tg.filter(ints, is_odd);
    gen = tg.fchain(ints, mults);
    assert.equal(gen.next(), 37);
    assert.equal(gen.next(), 74);
    assert.equal(gen.next(), 33);
    assert.equal(gen.next(), 66);
    assert.equal(gen.next(), 99);
    assert.equal(gen.next(), undefined);
    assert.equal(gen.next(), undefined);

    const undef = function () {
        return;
    };

    blueslip.expect("error", "Invalid generator returned.");
    ints = tg.list_generator([29, 43]);
    gen = tg.fchain(ints, undef);
    gen.next();
});

run_test("streams", () => {
    function assert_next_stream(curr_stream, expected) {
        const actual = tg.get_next_stream(curr_stream);
        assert.equal(actual, expected);
    }

    global.stream_sort.get_streams = function () {
        return ["announce", "muted", "devel", "test here"];
    };

    assert_next_stream(undefined, "announce");
    assert_next_stream("NOT THERE", "announce");

    assert_next_stream("announce", "muted");
    assert_next_stream("test here", "announce");

    function assert_prev_stream(curr_stream, expected) {
        const actual = tg.get_prev_stream(curr_stream);
        assert.equal(actual, expected);
    }

    assert_prev_stream(undefined, "test here");
    assert_prev_stream("test here", "devel");
    assert_prev_stream("announce", "test here");
});

run_test("topics", () => {
    const streams = [1, 2, 3, 4];
    const topics = new Map([
        [1, ["read", "read", "1a", "1b", "read", "1c"]],
        [2, []],
        [3, ["3a", "read", "read", "3b", "read"]],
        [4, ["4a"]],
    ]);

    function has_unread_messages(stream, topic) {
        return topic !== "read";
    }

    function get_topics(stream) {
        return topics.get(stream);
    }

    function next_topic(curr_stream, curr_topic) {
        return tg.next_topic(streams, get_topics, has_unread_messages, curr_stream, curr_topic);
    }

    assert.deepEqual(next_topic(1, "1a"), {stream: 1, topic: "1b"});
    assert.deepEqual(next_topic(1, undefined), {stream: 1, topic: "1a"});
    assert.deepEqual(next_topic(2, "bogus"), {stream: 3, topic: "3a"});
    assert.deepEqual(next_topic(3, "3b"), {stream: 3, topic: "3a"});
    assert.deepEqual(next_topic(4, "4a"), {stream: 1, topic: "1a"});
    assert.deepEqual(next_topic(undefined, undefined), {stream: 1, topic: "1a"});

    // Now test the deeper function that is wired up to
    // real functions stream_data/stream_sort/unread.

    global.stream_sort.get_streams = function () {
        return ["announce", "muted", "devel", "test here"];
    };

    const muted_stream_id = 400;
    const devel_stream_id = 401;

    const stream_id_dct = {
        muted: muted_stream_id,
        devel: devel_stream_id,
    };

    stream_topic_history.get_recent_topic_names = function (stream_id) {
        switch (stream_id) {
            case muted_stream_id:
                return ["ms-topic1", "ms-topic2"];
            case devel_stream_id:
                return ["muted", "python"];
        }

        return [];
    };

    global.stream_data.get_stream_id = function (stream_name) {
        return stream_id_dct[stream_name];
    };

    global.stream_data.is_stream_muted_by_name = function (stream_name) {
        return stream_name === "muted";
    };

    global.unread.topic_has_any_unread = function (stream_id) {
        return [devel_stream_id, muted_stream_id].includes(stream_id);
    };

    global.muting.is_topic_muted = function (stream_name, topic) {
        return topic === "muted";
    };

    let next_item = tg.get_next_topic("announce", "whatever");
    assert.deepEqual(next_item, {
        stream: "devel",
        topic: "python",
    });

    next_item = tg.get_next_topic("muted", undefined);
    assert.deepEqual(next_item, {
        stream: "muted",
        topic: "ms-topic1",
    });
});

run_test("get_next_unread_pm_string", () => {
    pm_conversations.recent.get_strings = function () {
        return ["1", "read", "2,3", "4", "unk"];
    };

    unread.num_unread_for_person = function (user_ids_string) {
        if (user_ids_string === "unk") {
            return;
        }

        if (user_ids_string === "read") {
            return 0;
        }

        return 5; // random non-zero value
    };

    assert.equal(tg.get_next_unread_pm_string(), "1");
    assert.equal(tg.get_next_unread_pm_string("4"), "1");
    assert.equal(tg.get_next_unread_pm_string("unk"), "1");
    assert.equal(tg.get_next_unread_pm_string("4"), "1");
    assert.equal(tg.get_next_unread_pm_string("1"), "2,3");
    assert.equal(tg.get_next_unread_pm_string("read"), "2,3");
    assert.equal(tg.get_next_unread_pm_string("2,3"), "4");
});
