// This is a framework-free unit test for the message_tour.js
// module.  There's a long comment there explaining the module's
// purpose, but, briefly, it provides an API to keep track of
// messages that you visit on a "tour."

var message_tour = require('../../../../static/js/message_tour.js');
var assert = require('assert');

(function test_basic_tour() {
    message_tour.start_tour(5);
    message_tour.visit(3); // too small
    message_tour.visit(7);
    message_tour.visit(6);
    message_tour.visit(4); // too small
    assert.deepEqual(message_tour.get_tour(), [7,6]);
    message_tour.finish_tour();
    assert.deepEqual(message_tour.get_tour(), []);
    message_tour.visit(7); // should be ignored
    message_tour.start_tour(5);
    message_tour.visit(13);
    assert.deepEqual(message_tour.get_tour(), [13]);
}());

