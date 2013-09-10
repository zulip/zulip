var assert = require('assert');

add_dependencies({
    _: 'third/underscore/underscore.js',
    Dict: 'js/dict.js'
});

set_global('page_params', {
    domain: 'zulip.com'
});

var muting = require('js/muting.js');

(function test_basics() {
    assert(!muting.is_topic_muted('devel', 'java'));
    muting.mute_topic('devel', 'java');
    assert(muting.is_topic_muted('devel', 'java'));

    // test idempotentcy
    muting.mute_topic('devel', 'java');
    assert(muting.is_topic_muted('devel', 'java'));

    muting.unmute_topic('devel', 'java');
    assert(!muting.is_topic_muted('devel', 'java'));

    // test idempotentcy
    muting.unmute_topic('devel', 'java');
    assert(!muting.is_topic_muted('devel', 'java'));

    // test unknown stream is harmless too
    muting.unmute_topic('unknown', 'java');
    assert(!muting.is_topic_muted('unknown', 'java'));
}());

(function test_get_and_set_muted_topics() {
    assert.deepEqual(muting.get_muted_topics(), []);
    muting.mute_topic('office', 'gossip');
    muting.mute_topic('devel', 'java');
    assert.deepEqual(muting.get_muted_topics().sort(), [
        ['devel', 'java'],
        ['office', 'gossip']
    ]);

    muting.set_muted_topics([
        ['social', 'breakfast'],
        ['design', 'typography']
    ]);
    assert.deepEqual(muting.get_muted_topics().sort(), [
        ['design', 'typography'],
        ['social', 'breakfast']
    ]);
}());
