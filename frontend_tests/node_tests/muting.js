zrequire('muting');
zrequire('stream_data');
set_global('blueslip', global.make_zblueslip());
set_global('page_params', {});

run_test('edge_cases', () => {
    // private messages
    assert(!muting.is_topic_muted(undefined, undefined));

    // defensive
    assert(!muting.is_topic_muted('nonexistent', undefined));
});

var design = {
    stream_id: 100,
    name: 'design',
};

var devel = {
    stream_id: 101,
    name: 'devel',
};

var office = {
    stream_id: 102,
    name: 'office',
};

var social = {
    stream_id: 103,
    name: 'social',
};

var unknown = {
    stream_id: 999,
    name: 'whatever',
};

stream_data.add_sub(design.name, design);
stream_data.add_sub(devel.name, devel);
stream_data.add_sub(office.name, office);
stream_data.add_sub(social.name, social);

run_test('basics', () => {
    assert(!muting.is_topic_muted(devel.stream_id, 'java'));
    muting.add_muted_topic(devel.stream_id, 'java');
    assert(muting.is_topic_muted(devel.stream_id, 'java'));

    // test idempotentcy
    muting.add_muted_topic(devel.stream_id, 'java');
    assert(muting.is_topic_muted(devel.stream_id, 'java'));

    muting.remove_muted_topic(devel.stream_id, 'java');
    assert(!muting.is_topic_muted(devel.stream_id, 'java'));

    // test idempotentcy
    muting.remove_muted_topic(devel.stream_id, 'java');
    assert(!muting.is_topic_muted(devel.stream_id, 'java'));

    // test unknown stream is harmless too
    muting.remove_muted_topic(unknown.stream_id, 'java');
    assert(!muting.is_topic_muted(unknown.stream_id, 'java'));
});

run_test('get_and_set_muted_topics', () => {
    assert.deepEqual(muting.get_muted_topics(), []);
    muting.add_muted_topic(office.stream_id, 'gossip');
    muting.add_muted_topic(devel.stream_id, 'java');
    assert.deepEqual(muting.get_muted_topics().sort(), [
        [devel.stream_id, 'java'],
        [office.stream_id, 'gossip'],
    ]);

    blueslip.set_test_data('warn', 'Unknown stream in set_muted_topics: BOGUS STREAM');

    page_params.muted_topics = [
        ['social', 'breakfast'],
        ['design', 'typography'],
        ['BOGUS STREAM', 'whatever'],
    ];
    muting.initialize();

    blueslip.clear_test_data();


    assert.deepEqual(muting.get_muted_topics().sort(), [
        [design.stream_id, 'typography'],
        [social.stream_id, 'breakfast'],
    ]);
});

run_test('case_insensitivity', () => {
    muting.set_muted_topics([]);
    assert(!muting.is_topic_muted(social.stream_id, 'breakfast'));
    muting.set_muted_topics([
        ['SOCial', 'breakfast'],
    ]);
    assert(muting.is_topic_muted(social.stream_id, 'breakfast'));
    assert(muting.is_topic_muted(social.stream_id, 'breakFAST'));
});
