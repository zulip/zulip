zrequire('util');
zrequire('stream_data');
zrequire('stream_sort');
var with_overrides = global.with_overrides;

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

stream_data.add_sub(scalene.name, scalene);
stream_data.add_sub(fast_tortoise.name, fast_tortoise);
stream_data.add_sub(pneumonia.name, pneumonia);
stream_data.add_sub(clarinet.name, clarinet);
stream_data.add_sub(weaving.name, weaving);

with_overrides(function (override) {
    override('stream_data.is_active', function (sub) {
        return sub.name !== "pneumonia";
    });

    // Test sorting into categories/alphabetized
    var sorted = stream_sort.sort_groups("");
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
    sorted = stream_sort.sort_groups("s");
    assert.deepEqual(sorted.pinned_streams, ['scalene']);
    assert.deepEqual(sorted.normal_streams, []);
    assert.deepEqual(sorted.dormant_streams, []);

    assert.equal(stream_sort.prev_stream_id(clarinet.stream_id), undefined);

    assert.equal(stream_sort.next_stream_id(clarinet.stream_id), undefined);

    // Test searching entire word, case-insensitive
    sorted = stream_sort.sort_groups("PnEuMoNiA");
    assert.deepEqual(sorted.pinned_streams, []);
    assert.deepEqual(sorted.normal_streams, []);
    assert.deepEqual(sorted.dormant_streams, ['pneumonia']);

    // Test searching part of word
    sorted = stream_sort.sort_groups("tortoise");
    assert.deepEqual(sorted.pinned_streams, []);
    assert.deepEqual(sorted.normal_streams, ['fast tortoise']);
    assert.deepEqual(sorted.dormant_streams, []);

    // Test searching stream with spaces
    sorted = stream_sort.sort_groups("fast t");
    assert.deepEqual(sorted.pinned_streams, []);
    assert.deepEqual(sorted.normal_streams, ['fast tortoise']);
    assert.deepEqual(sorted.dormant_streams, []);
});
