zrequire('stream_topic_history');
zrequire('stream_data');
zrequire('stream_sort');
set_global('page_params', {
    sort_streams_by_activity: false,
});
const with_overrides = global.with_overrides;

run_test('no_subscribed_streams', () => {
    assert.equal(stream_sort.sort_groups(''), undefined);
    assert.equal(stream_sort.first_stream_id(), undefined);
});

const scalene = {
    subscribed: true,
    name: 'scalene',
    stream_id: 1,
    pin_to_top: true,
};
const fast_tortoise = {
    subscribed: true,
    name: 'fast tortoise',
    stream_id: 2,
    pin_to_top: false,
};
const pneumonia = {
    subscribed: true,
    name: 'pneumonia',
    stream_id: 3,
    pin_to_top: false,
};
const clarinet = {
    subscribed: true,
    name: 'clarinet',
    stream_id: 4,
    pin_to_top: false,
};
const weaving = {
    subscribed: false,
    name: 'weaving',
    stream_id: 5,
    pin_to_top: false,
};

stream_data.add_sub(scalene);
stream_data.add_sub(fast_tortoise);
stream_data.add_sub(pneumonia);
stream_data.add_sub(clarinet);
stream_data.add_sub(weaving);

const scalene_opts = {
    stream_id: scalene.stream_id,
    message_id: 3,
    topic_name: 'test_topic',
};

const fast_tortoise_opts = {
    stream_id: fast_tortoise.stream_id,
    message_id: 2,
    topic_name: 'test_topic',
};

const pneumonia_opts = {
    stream_id: pneumonia.stream_id,
    message_id: 7,
    topic_name: 'test_topic',
};

const clarinet_opts = {
    stream_id: clarinet.stream_id,
    message_id: 1,
    topic_name: 'test_topic',
};

const weaving_opts = {
    stream_id: weaving.stream_id,
    message_id: 12,
    topic_name: 'test_topic',
};

stream_topic_history.add_message(scalene_opts);
stream_topic_history.add_message(fast_tortoise_opts);
stream_topic_history.add_message(pneumonia_opts);
stream_topic_history.add_message(clarinet_opts);
stream_topic_history.add_message(weaving_opts);

function sort_groups(query) {
    const streams = stream_data.subscribed_streams();
    return stream_sort.sort_groups(streams, query);
}

with_overrides(function (override) {
    override('stream_data.is_active', function (sub) {
        return sub.name !== "pneumonia";
    });

    // Test sorting into categories/alphabetized
    let sorted = sort_groups("");
    assert.deepEqual(sorted.pinned_streams, ['scalene']);
    assert.deepEqual(sorted.normal_streams, ['clarinet', 'fast tortoise']);
    assert.deepEqual(sorted.dormant_streams, ['pneumonia']);

    // Test cursor helpers.
    assert.equal(stream_sort.first_stream_id(), scalene.stream_id);

    assert.equal(stream_sort.prev_stream_id(scalene.stream_id), undefined);
    assert.equal(stream_sort.prev_stream_id(clarinet.stream_id), scalene.stream_id);

    assert.equal(stream_sort.next_stream_id(fast_tortoise.stream_id), pneumonia.stream_id);
    assert.equal(stream_sort.next_stream_id(pneumonia.stream_id), undefined);

    // Test filtering
    sorted = sort_groups("s");
    assert.deepEqual(sorted.pinned_streams, ['scalene']);
    assert.deepEqual(sorted.normal_streams, []);
    assert.deepEqual(sorted.dormant_streams, []);

    assert.equal(stream_sort.prev_stream_id(clarinet.stream_id), undefined);

    assert.equal(stream_sort.next_stream_id(clarinet.stream_id), undefined);

    // Test searching entire word, case-insensitive
    sorted = sort_groups("PnEuMoNiA");
    assert.deepEqual(sorted.pinned_streams, []);
    assert.deepEqual(sorted.normal_streams, []);
    assert.deepEqual(sorted.dormant_streams, ['pneumonia']);

    // Test searching part of word
    sorted = sort_groups("tortoise");
    assert.deepEqual(sorted.pinned_streams, []);
    assert.deepEqual(sorted.normal_streams, ['fast tortoise']);
    assert.deepEqual(sorted.dormant_streams, []);

    // Test searching stream with spaces
    sorted = sort_groups("fast t");
    assert.deepEqual(sorted.pinned_streams, []);
    assert.deepEqual(sorted.normal_streams, ['fast tortoise']);
    assert.deepEqual(sorted.dormant_streams, []);

    page_params.sort_streams_by_activity = true;

    // Test sorting into catagories by most recent activity.
    sorted = sort_groups("");
    assert.deepEqual(sorted.pinned_streams, ['scalene']);
    assert.deepEqual(sorted.normal_streams, ['fast tortoise', 'clarinet']);
    assert.deepEqual(sorted.dormant_streams, ['pneumonia']);

    clarinet_opts.message_id = 99;
    stream_topic_history.add_message(clarinet_opts);

    // Test after updating the activity of a stream.
    sorted = sort_groups("");
    assert.deepEqual(sorted.normal_streams, ['clarinet', 'fast tortoise']);
});
