zrequire('locking');

(function test_edge_cases() {
    assert(!locking.is_topic_locked(undefined, undefined));
    assert(!locking.is_topic_locked('nonexistent', undefined));
}());

(function test_basics() {
    assert(!locking.is_topic_locked('devel', 'java'));
    locking.add_locked_topic('devel', 'java');
    assert(locking.is_topic_locked('devel', 'java'));

    // test idempotentcy
    locking.add_locked_topic('devel', 'java');
    assert(locking.is_topic_locked('devel', 'java'));

    locking.remove_locked_topic('devel', 'java');
    assert(!locking.is_topic_locked('devel', 'java'));

    // test idempotentcy
    locking.remove_locked_topic('devel', 'java');
    assert(!locking.is_topic_locked('devel', 'java'));

    // test unknown stream is harmless too
    locking.remove_locked_topic('unknown', 'java');
    assert(!locking.is_topic_locked('unknown', 'java'));
}());

(function test_set_locked_topics() {
    locking.set_locked_topics([
        ['social', 'breakfast'],
        ['design', 'typography'],
    ]);
    assert(locking.is_topic_locked('social', 'breakfast'));
    assert(locking.is_topic_locked('design', 'typography'));
    locking.set_locked_topics([
        ['devel', 'java'],
    ]);
    assert(!locking.is_topic_locked('social', 'breakfast'));
    assert(!locking.is_topic_locked('design', 'typography'));
    assert(locking.is_topic_locked('devel', 'java'));
}());

(function test_case_insensitivity() {
    locking.set_locked_topics([]);
    assert(!locking.is_topic_locked('SOCial', 'breakfast'));
    locking.set_locked_topics([
        ['SOCial', 'breakfast'],
    ]);
    assert(locking.is_topic_locked('SOCial', 'breakfast'));
    assert(locking.is_topic_locked('social', 'breakfast'));
    assert(locking.is_topic_locked('social', 'breakFAST'));
}());

set_global('page_params', {
    is_admin: false,
});

(function test_can_lock_topic_no_admin() {
    locking.set_locked_topics([]);
    assert(!locking.can_lock_topic('social', 'breakfast'));
    assert(!locking.can_unlock_topic('social', 'breakfast'));
    assert(!locking.can_lock_topic(undefined, 'breakfast'));
    assert(!locking.can_lock_topic('social', undefined));
    assert(!locking.can_unlock_topic(undefined, 'breakfast'));
    assert(!locking.can_unlock_topic('social', undefined));
    locking.add_locked_topic('social', 'breakfast');
    assert(!locking.can_lock_topic('social', 'breakfast'));
    assert(!locking.can_unlock_topic('social', 'breakfast'));
}());

set_global('page_params', {
    is_admin: true,
});

(function test_can_lock_topic_admin() {
    locking.set_locked_topics([]);
    assert(locking.can_lock_topic('social', 'breakfast'));
    assert(!locking.can_unlock_topic('social', 'breakfast'));
    assert(!locking.can_lock_topic(undefined, 'breakfast'));
    assert(!locking.can_lock_topic('social', undefined));
    assert(!locking.can_unlock_topic(undefined, 'breakfast'));
    assert(!locking.can_unlock_topic('social', undefined));
    locking.add_locked_topic('social', 'breakfast');
    assert(!locking.can_lock_topic('social', 'breakfast'));
    assert(locking.can_unlock_topic('social', 'breakfast'));
}());
