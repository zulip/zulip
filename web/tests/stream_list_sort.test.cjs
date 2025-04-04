"use strict";

const assert = require("node:assert/strict");

const _ = require("lodash");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const stream_data = zrequire("stream_data");
const stream_list_sort = zrequire("stream_list_sort");
const settings_config = zrequire("settings_config");
const {initialize_user_settings} = zrequire("user_settings");

// Start with always filtering out inactive streams.
const user_settings = {
    demote_inactive_streams: settings_config.demote_inactive_streams_values.always.code,
};
initialize_user_settings({user_settings});
stream_list_sort.set_filter_out_inactives();

const scalene = {
    subscribed: true,
    name: "scalene",
    stream_id: 1,
    pin_to_top: true,
    is_recently_active: true,
};
const fast_tortoise = {
    subscribed: true,
    name: "fast tortoise",
    stream_id: 2,
    pin_to_top: false,
    is_recently_active: true,
};
const pneumonia = {
    subscribed: true,
    name: "pneumonia",
    stream_id: 3,
    pin_to_top: false,
    is_recently_active: false,
};
const clarinet = {
    subscribed: true,
    name: "clarinet",
    stream_id: 4,
    pin_to_top: false,
    is_recently_active: true,
};
const weaving = {
    subscribed: false,
    name: "weaving",
    stream_id: 5,
    pin_to_top: false,
    is_recently_active: true,
};
const stream_hyphen_underscore_slash_colon = {
    subscribed: true,
    name: "stream-hyphen_underscore/slash:colon",
    stream_id: 6,
    pin_to_top: false,
    is_recently_active: true,
};
const muted_active = {
    subscribed: true,
    name: "muted active",
    stream_id: 7,
    pin_to_top: false,
    is_recently_active: true,
    is_muted: true,
};
const muted_pinned = {
    subscribed: true,
    name: "muted pinned",
    stream_id: 8,
    pin_to_top: true,
    is_recently_active: true,
    is_muted: true,
};
const archived = {
    subscribed: true,
    name: "archived channel",
    stream_id: 9,
    pin_to_top: true,
    is_archived: true,
};

function sort_groups(query) {
    const streams = stream_data.subscribed_stream_ids();
    return stream_list_sort.sort_groups(streams, query);
}

function test(label, f) {
    run_test(label, (helpers) => {
        stream_data.clear_subscriptions();
        f(helpers);
    });
}

test("no_subscribed_streams", () => {
    const sorted = sort_groups("");
    assert.deepEqual(sorted, {
        dormant_streams: [],
        muted_active_streams: [],
        muted_pinned_streams: [],
        normal_streams: [],
        pinned_streams: [],
        same_as_before: sorted.same_as_before,
    });
    assert.equal(stream_list_sort.first_stream_id(), undefined);
});

test("basics", () => {
    stream_data.add_sub(scalene);
    stream_data.add_sub(fast_tortoise);
    stream_data.add_sub(pneumonia);
    stream_data.add_sub(clarinet);
    stream_data.add_sub(weaving);
    stream_data.add_sub(stream_hyphen_underscore_slash_colon);
    stream_data.add_sub(muted_active);
    stream_data.add_sub(muted_pinned);
    stream_data.add_sub(archived);

    // Test sorting into categories/alphabetized
    let sorted = sort_groups("");
    assert.deepEqual(sorted.pinned_streams, [scalene.stream_id]);
    assert.deepEqual(sorted.normal_streams, [
        clarinet.stream_id,
        fast_tortoise.stream_id,
        stream_hyphen_underscore_slash_colon.stream_id,
    ]);
    assert.deepEqual(sorted.muted_pinned_streams, [muted_pinned.stream_id]);
    assert.deepEqual(sorted.muted_active_streams, [muted_active.stream_id]);
    assert.deepEqual(sorted.dormant_streams, [pneumonia.stream_id]);

    // Test cursor helpers.
    assert.equal(stream_list_sort.first_stream_id(), scalene.stream_id);

    assert.equal(stream_list_sort.prev_stream_id(scalene.stream_id), undefined);
    assert.equal(stream_list_sort.prev_stream_id(muted_pinned.stream_id), scalene.stream_id);
    assert.equal(stream_list_sort.prev_stream_id(clarinet.stream_id), muted_pinned.stream_id);

    assert.equal(
        stream_list_sort.next_stream_id(fast_tortoise.stream_id),
        stream_hyphen_underscore_slash_colon.stream_id,
    );
    assert.equal(
        stream_list_sort.next_stream_id(stream_hyphen_underscore_slash_colon.stream_id),
        muted_active.stream_id,
    );
    assert.equal(
        stream_list_sort.next_stream_id(fast_tortoise.stream_id),
        stream_hyphen_underscore_slash_colon.stream_id,
    );
    assert.equal(stream_list_sort.next_stream_id(muted_active.stream_id), pneumonia.stream_id);
    assert.equal(stream_list_sort.next_stream_id(pneumonia.stream_id), undefined);

    // Test filtering
    sorted = sort_groups("s");
    assert.deepEqual(sorted.pinned_streams, [scalene.stream_id]);
    assert.deepEqual(sorted.normal_streams, [stream_hyphen_underscore_slash_colon.stream_id]);
    assert.deepEqual(sorted.dormant_streams, []);

    assert.equal(stream_list_sort.prev_stream_id(clarinet.stream_id), undefined);

    assert.equal(stream_list_sort.next_stream_id(clarinet.stream_id), undefined);

    // Test searching entire word, case-insensitive
    sorted = sort_groups("PnEuMoNiA");
    assert.deepEqual(sorted.pinned_streams, []);
    assert.deepEqual(sorted.normal_streams, []);
    assert.deepEqual(sorted.dormant_streams, [pneumonia.stream_id]);

    // Test searching part of word
    sorted = sort_groups("tortoise");
    assert.deepEqual(sorted.pinned_streams, []);
    assert.deepEqual(sorted.normal_streams, [fast_tortoise.stream_id]);
    assert.deepEqual(sorted.dormant_streams, []);

    // Test searching stream with spaces
    sorted = sort_groups("fast t");
    assert.deepEqual(sorted.pinned_streams, []);
    assert.deepEqual(sorted.normal_streams, [fast_tortoise.stream_id]);
    assert.deepEqual(sorted.dormant_streams, []);

    // Test searching part of stream name with non space word separators
    sorted = sort_groups("hyphen");
    assert.deepEqual(sorted.pinned_streams, []);
    assert.deepEqual(sorted.normal_streams, [stream_hyphen_underscore_slash_colon.stream_id]);
    assert.deepEqual(sorted.dormant_streams, []);

    sorted = sort_groups("hyphen_underscore");
    assert.deepEqual(sorted.pinned_streams, []);
    assert.deepEqual(sorted.normal_streams, [stream_hyphen_underscore_slash_colon.stream_id]);
    assert.deepEqual(sorted.dormant_streams, []);

    sorted = sort_groups("colon");
    assert.deepEqual(sorted.pinned_streams, []);
    assert.deepEqual(sorted.normal_streams, [stream_hyphen_underscore_slash_colon.stream_id]);
    assert.deepEqual(sorted.dormant_streams, []);

    sorted = sort_groups("underscore");
    assert.deepEqual(sorted.pinned_streams, []);
    assert.deepEqual(sorted.normal_streams, [stream_hyphen_underscore_slash_colon.stream_id]);
    assert.deepEqual(sorted.dormant_streams, []);
});

test("filter inactives", ({override}) => {
    // Test that we automatically switch to filtering out inactive streams
    // once the user has more than 30 streams.
    override(
        user_settings,
        "demote_inactive_streams",
        settings_config.demote_inactive_streams_values.automatic.code,
    );

    stream_list_sort.set_filter_out_inactives();
    assert.ok(!stream_list_sort.is_filtering_inactives());

    _.times(30, (i) => {
        const name = "random" + i.toString();
        const stream_id = 100 + i;

        const sub = {
            name,
            subscribed: true,
            newly_subscribed: false,
            stream_id,
        };
        stream_data.add_sub(sub);
    });
    stream_list_sort.set_filter_out_inactives();

    assert.ok(stream_list_sort.is_filtering_inactives());

    override(
        user_settings,
        "demote_inactive_streams",
        settings_config.demote_inactive_streams_values.never.code,
    );
    stream_list_sort.set_filter_out_inactives();
    assert.ok(!stream_list_sort.is_filtering_inactives());
    // Even inactive channels are marked active.
    assert.ok(!pneumonia.is_recently_active);
    assert.ok(stream_list_sort.has_recent_activity(pneumonia));
});

test("initialize", ({override}) => {
    override(user_settings, "demote_inactive_streams", 1);
    stream_list_sort.initialize();

    assert.ok(!stream_list_sort.is_filtering_inactives());
});
