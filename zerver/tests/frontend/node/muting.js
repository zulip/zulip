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
}());
