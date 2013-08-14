var assert = require('assert');

global._ = require('third/underscore/underscore.js');
global.util = require('js/util.js');
global.Dict = require('js/dict.js');
var ct = global.composebox_typeahead = require('js/composebox_typeahead.js');

(function test_add_topic () {
    ct.add_topic('Denmark', 'civil fears');
    ct.add_topic('devel', 'fading');
    ct.add_topic('denmark', 'acceptance');
    ct.add_topic('denmark', 'Acceptance');
    ct.add_topic('Denmark', 'With Twisted Metal');

    assert.deepEqual(ct.topics_seen_for('Denmark'), ['With Twisted Metal', 'acceptance', 'civil fears']);
}());
