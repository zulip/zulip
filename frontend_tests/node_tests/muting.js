zrequire('muting');

(function test_edge_cases() {
    // private messages
    assert(!muting.is_topic_muted(undefined, undefined));

    // defensive
    assert(!muting.is_topic_muted('nonexistent', undefined));
}());

(function test_basics() {
    assert(!muting.is_topic_muted('devel', 'java'));
    muting.add_muted_topic('devel', 'java');
    assert(muting.is_topic_muted('devel', 'java'));

    // test idempotentcy
    muting.add_muted_topic('devel', 'java');
    assert(muting.is_topic_muted('devel', 'java'));

    muting.remove_muted_topic('devel', 'java');
    assert(!muting.is_topic_muted('devel', 'java'));

    // test idempotentcy
    muting.remove_muted_topic('devel', 'java');
    assert(!muting.is_topic_muted('devel', 'java'));

    // test unknown stream is harmless too
    muting.remove_muted_topic('unknown', 'java');
    assert(!muting.is_topic_muted('unknown', 'java'));
}());

(function test_get_and_set_muted_topics() {
    assert.deepEqual(muting.get_muted_topics(), []);
    muting.add_muted_topic('office', 'gossip');
    muting.add_muted_topic('devel', 'java');
    assert.deepEqual(muting.get_muted_topics().sort(), [
        ['devel', 'java'],
        ['office', 'gossip'],
    ]);

    muting.set_muted_topics([
        ['social', 'breakfast'],
        ['design', 'typography'],
    ]);
    assert.deepEqual(muting.get_muted_topics().sort(), [
        ['design', 'typography'],
        ['social', 'breakfast'],
    ]);
}());

(function test_case_insensitivity() {
    muting.set_muted_topics([]);
    assert(!muting.is_topic_muted('SOCial', 'breakfast'));
    muting.set_muted_topics([
        ['SOCial', 'breakfast'],
    ]);
    assert(muting.is_topic_muted('SOCial', 'breakfast'));
    assert(muting.is_topic_muted('social', 'breakfast'));
    assert(muting.is_topic_muted('social', 'breakFAST'));
}());
