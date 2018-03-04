zrequire('locking');

(function test_edge_cases() {
    assert(!locking.is_topic_locked(undefined, undefined));
    assert(!locking.is_topic_locked('nonexistent', undefined));
}());

(function test_basics() {
    assert(!locking.is_topic_locked(1, 'java'));
    locking.add_locked_topic(1, 'java');
    assert(locking.is_topic_locked(1, 'java'));

    // test idempotentcy
    locking.add_locked_topic(1, 'java');
    assert(locking.is_topic_locked(1, 'java'));

    locking.remove_locked_topic(1, 'java');
    assert(!locking.is_topic_locked(1, 'java'));

    // test idempotentcy
    locking.remove_locked_topic(1, 'java');
    assert(!locking.is_topic_locked(1, 'java'));

    // test unknown stream is harmless too
    locking.remove_locked_topic(3, 'java');
    assert(!locking.is_topic_locked(3, 'java'));
}());

(function test_set_locked_topics() {
    locking.set_locked_topics([
        {stream_id: 2, topic: 'breakfast'},
        {stream_id: 4, topic: 'typography'},
    ]);
    assert(locking.is_topic_locked(2, 'breakfast'));
    assert(locking.is_topic_locked(4, 'typography'));
    locking.set_locked_topics([
        {stream_id: 1, topic: 'java'},
    ]);
    assert(!locking.is_topic_locked(2, 'breakfast'));
    assert(!locking.is_topic_locked(4, 'typography'));
    assert(locking.is_topic_locked(1, 'java'));
}());

(function test_case_insensitivity() {
    locking.set_locked_topics([]);
    assert(!locking.is_topic_locked(2, 'breakfast'));
    locking.set_locked_topics([
        {stream_id: 2, topic: 'breakfast'},
    ]);
    assert(locking.is_topic_locked(2, 'breakfast'));
    assert(locking.is_topic_locked(2, 'breakFAST'));
}());

set_global('page_params', {
    is_admin: false,
});

(function test_can_lock_topic_no_admin() {
    locking.set_locked_topics([]);
    assert(!locking.can_lock_topic(2, 'breakfast'));
    assert(!locking.can_unlock_topic(2, 'breakfast'));
    assert(!locking.can_lock_topic(undefined, 'breakfast'));
    assert(!locking.can_lock_topic(2, undefined));
    assert(!locking.can_unlock_topic(undefined, 'breakfast'));
    assert(!locking.can_unlock_topic(2, undefined));
    locking.add_locked_topic(2, 'breakfast');
    assert(!locking.can_lock_topic(2, 'breakfast'));
    assert(!locking.can_unlock_topic(2, 'breakfast'));
}());

set_global('page_params', {
    is_admin: true,
});

(function test_can_lock_topic_admin() {
    locking.set_locked_topics([]);
    assert(locking.can_lock_topic(2, 'breakfast'));
    assert(!locking.can_unlock_topic(2, 'breakfast'));
    assert(!locking.can_lock_topic(undefined, 'breakfast'));
    assert(!locking.can_lock_topic(2, undefined));
    assert(!locking.can_unlock_topic(undefined, 'breakfast'));
    assert(!locking.can_unlock_topic(2, undefined));
    locking.add_locked_topic(2, 'breakfast');
    assert(!locking.can_lock_topic(2, 'breakfast'));
    assert(locking.can_unlock_topic(2, 'breakfast'));
}());
