"use strict";

const assert = require("node:assert/strict");

const {make_stream} = require("./lib/example_stream.cjs");
const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const channel_folders = zrequire("channel_folders");
const stream_data = zrequire("stream_data");

run_test("basics", () => {
    const params = {};
    const frontend_folder = {
        name: "Frontend",
        description: "Channels for frontend discussions",
        rendered_description: "<p>Channels for frontend discussions</p>",
        creator_id: null,
        date_created: 1596710000,
        id: 1,
        is_archived: false,
    };
    const backend_folder = {
        name: "Backend",
        description: "Channels for backend discussions",
        rendered_description: "<p>Channels for backend discussions</p>",
        creator_id: null,
        date_created: 1596720000,
        id: 2,
        is_archived: false,
    };
    params.channel_folders = [frontend_folder, backend_folder];
    channel_folders.initialize(params);

    assert.deepEqual(channel_folders.get_channel_folders(), [frontend_folder, backend_folder]);

    const devops_folder = {
        name: "Devops",
        description: "",
        rendered_description: "",
        creator_id: 1,
        date_created: 1596810000,
        id: 3,
        is_archived: false,
    };
    channel_folders.add(devops_folder);
    assert.deepEqual(channel_folders.get_channel_folders(), [
        frontend_folder,
        backend_folder,
        devops_folder,
    ]);

    devops_folder.is_archived = true;
    assert.deepEqual(channel_folders.get_channel_folders(), [frontend_folder, backend_folder]);

    assert.deepEqual(channel_folders.get_channel_folders(true), [
        frontend_folder,
        backend_folder,
        devops_folder,
    ]);

    assert.ok(channel_folders.is_valid_folder_id(frontend_folder.id));
    assert.ok(!channel_folders.is_valid_folder_id(999));

    assert.equal(channel_folders.get_channel_folder_by_id(frontend_folder.id), frontend_folder);

    const stream_1 = make_stream({
        stream_id: 1,
        name: "Stream 1",
        folder_id: null,
    });
    const stream_2 = make_stream({
        stream_id: 2,
        name: "Stream 2",
        folder_id: frontend_folder.id,
    });
    const stream_3 = make_stream({
        stream_id: 3,
        name: "Stream 3",
        folder_id: devops_folder.id,
    });
    const stream_4 = make_stream({
        stream_id: 4,
        name: "Stream 4",
        folder_id: frontend_folder.id,
    });
    stream_data.add_sub(stream_1);
    stream_data.add_sub(stream_2);
    stream_data.add_sub(stream_3);
    stream_data.add_sub(stream_4);

    assert.deepEqual(channel_folders.get_stream_ids_in_folder(frontend_folder.id), [
        stream_2.stream_id,
        stream_4.stream_id,
    ]);
    assert.deepEqual(channel_folders.get_stream_ids_in_folder(devops_folder.id), [
        stream_3.stream_id,
    ]);
    assert.deepEqual(channel_folders.get_stream_ids_in_folder(backend_folder.id), []);
});
