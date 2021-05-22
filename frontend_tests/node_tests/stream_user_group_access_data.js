"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

const stream_user_group_access_data = zrequire("stream_user_group_access_data");

run_test("stream_user_group_access", () => {
    const perm_1 = {
        id: 1,
        group_id: 1,
        stream_id: 1,
    };

    const perm_2 = {
        id: 2,
        group_id: 2,
        stream_id: 1,
    };
    const params = {};
    params.stream_user_group_access_data = [perm_1];

    stream_user_group_access_data.initialize(params);
    assert.deepEqual(
        stream_user_group_access_data.get_stream_user_group_access_obj_by_id(perm_1.id),
        perm_1,
    );
    assert.deepEqual(stream_user_group_access_data.get_allowed_user_group_ids(perm_1.stream_id), [
        perm_1.id,
    ]);
    assert.deepEqual(
        stream_user_group_access_data.get_allowed_user_groups_access_obj_for_stream(
            perm_1.stream_id,
        ),
        [perm_1],
    );
    assert(stream_user_group_access_data.can_user_group_post(perm_1.id, perm_1.stream_id));
    assert(!stream_user_group_access_data.can_user_group_post(perm_2.id, perm_1.stream_id));
    // test that for an stream_id not present no user_groups are returned.
    assert.deepEqual(stream_user_group_access_data.get_allowed_user_group_ids(9999), []);

    const stream_user_group_access_add_event = {
        stream_user_group_access_object: perm_2,
    };
    stream_user_group_access_data.add_access_obj(
        stream_user_group_access_add_event.stream_user_group_access_object,
    );
    assert.deepEqual(stream_user_group_access_data.get_allowed_user_group_ids(perm_1.stream_id), [
        perm_1.id,
        perm_2.id,
    ]);
    assert.deepEqual(
        stream_user_group_access_data.get_allowed_user_groups_access_obj_for_stream(
            perm_1.stream_id,
        ),
        [perm_1, perm_2],
    );
    assert(stream_user_group_access_data.can_user_group_post(perm_2.id, perm_2.stream_id));
    const stream_user_group_access_delete_event = {
        access_object_id: perm_2.id,
    };
    stream_user_group_access_data.delete_access_obj(
        stream_user_group_access_delete_event.access_object_id,
    );
    assert.deepEqual(
        stream_user_group_access_data.get_stream_user_group_access_obj_by_id(perm_1.id),
        perm_1,
    );
    assert.deepEqual(stream_user_group_access_data.get_allowed_user_group_ids(perm_1.stream_id), [
        perm_1.id,
    ]);
    assert.deepEqual(
        stream_user_group_access_data.get_allowed_user_groups_access_obj_for_stream(
            perm_1.stream_id,
        ),
        [perm_1],
    );
    assert(stream_user_group_access_data.can_user_group_post(perm_1.id, perm_1.stream_id));
    assert(!stream_user_group_access_data.can_user_group_post(perm_2.id, perm_1.stream_id));

    // try adding a user_group that is already allowed.
    stream_user_group_access_data.add_access_obj(perm_1);
    // check that still only one perm_1 is allowed and is not changed
    assert.deepEqual(
        stream_user_group_access_data.get_allowed_user_groups_access_obj_for_stream(
            perm_1.stream_id,
        ),
        [perm_1],
    );
    assert.deepEqual(stream_user_group_access_data.get_allowed_user_group_ids(perm_1.stream_id), [
        perm_1.id,
    ]);

    // try removing a user_group that is already allowed.
    stream_user_group_access_data.delete_access_obj(perm_2.id);
    // check that still only one perm_1 is allowed and is not changed
    assert.deepEqual(
        stream_user_group_access_data.get_allowed_user_groups_access_obj_for_stream(
            perm_1.stream_id,
        ),
        [perm_1],
    );
    assert.deepEqual(stream_user_group_access_data.get_allowed_user_group_ids(perm_1.stream_id), [
        perm_1.id,
    ]);
});
