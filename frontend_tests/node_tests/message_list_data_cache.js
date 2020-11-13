"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

const {Filter} = zrequire("filter");
const hash_util = zrequire("hash_util");
const {mld_cache} = zrequire("message_list_data_cache");
const {MessageListData} = zrequire("../js/message_list_data");
const people = zrequire("people");

const hamlet = {
    user_id: 8,
    email: "user8@example.com",
    full_name: "Hamlet",
};

const zoe = {
    user_id: 10,
    email: "user10@example.com",
    full_name: "Zoe",
};

people.add_active_user(hamlet);
people.add_active_user(zoe);

run_test("basics", () => {
    const msg = {id: 1};
    const operators = [
        {operator: "stream", operand: "foo"},
        {operator: "topic", operand: "bar"},
    ];
    const filter = new Filter(operators);
    const mld = new MessageListData({
        muting_enabled: false,
        filter,
    });

    const mld_operators = mld.filter.operators();
    const key = hash_util.operators_to_hash(operators);
    const mld_key = hash_util.operators_to_hash(mld_operators);
    assert.equal(key, mld_key);

    assert.deepEqual(mld_cache.keys(), []);

    // cannot add empty message list data objects.
    mld_cache.add(mld);
    assert(!mld_cache.has(filter));

    mld.append([msg]);

    filter.can_apply_locally = () => false;
    mld_cache.add(mld);
    assert(!mld_cache.has(filter));

    filter.can_apply_locally = () => true;
    mld_cache.add(mld);
    assert(mld_cache.has(filter));
    assert.equal(mld_cache._get_key(mld.filter), key);

    const duplicate_mld = new MessageListData({
        muting_enabled: false,
        filter,
    });
    duplicate_mld.append([msg]);
    assert.deepEqual(mld_cache.get(filter), duplicate_mld);
    assert(mld_cache.get(filter) !== duplicate_mld);

    const nonexistant_key = "#narrow/group-pm-with/joe.40example.2Ecom";
    assert.equal(mld_cache._get_by_key(nonexistant_key), undefined);

    mld_cache.delete(filter);
    assert.deepEqual(mld_cache.keys(), []);

    const all_keys = [];
    for (const key of mld_cache.keys()) {
        all_keys.push(key);
    }
    assert.deepEqual(all_keys, mld_cache.keys());

    mld_cache.empty();
    assert.deepEqual(mld_cache.keys(), []);
});

run_test("get_valid_mlds", () => {
    function get_filter_from_key(key) {
        const operators = hash_util.parse_narrow(key.split("/"));
        return new Filter(operators);
    }

    const keys = [
        "#narrow/is/private",
        "#narrow/pm-with/8-user8",
        "#narrow/pm-with/8,10-group",
        "#narrow/stream/14-foo",
        "#narrow/stream/14-foo/topic/bar",
    ];

    const expected_keys = [
        ["#narrow/is/private"],
        ["#narrow/pm-with/8-user8", "#narrow/is/private"],
        ["#narrow/pm-with/8,10-group", "#narrow/is/private"],
        ["#narrow/stream/14-foo"],
        ["#narrow/stream/14-foo/topic/bar", "#narrow/stream/14-foo"],
    ];

    for (const key of keys) {
        const mld = new MessageListData({
            muting_enabled: false,
            filter: get_filter_from_key(key),
        });
        mld.append([{id: 1}]);
        mld_cache.add(mld);
    }

    for (const [index, key] of keys.entries()) {
        const mld = mld_cache._get_by_key(key);
        const valid_mlds = mld_cache.get_valid_mlds(mld.filter);
        const valid_keys = valid_mlds.map((mld) => mld_cache._get_key(mld.filter));

        assert.deepEqual(valid_keys, expected_keys[index]);
    }
    assert.equal(mld_cache.entries().length, expected_keys.length);

    mld_cache.delete(get_filter_from_key(keys[3]));

    const mld = mld_cache._get_by_key(keys[4]);
    const valid_mlds = mld_cache.get_valid_mlds(mld.filter);
    const valid_keys = valid_mlds.map((mld) => mld_cache._get_key(mld.filter));

    assert.deepEqual(valid_keys, [keys[4]]);
    mld_cache.empty();
});
