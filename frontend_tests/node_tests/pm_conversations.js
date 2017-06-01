var assert = require('assert');
var pmc = require('js/pm_conversations.js');

(function test_partners() {
    var user1_id = 1;
    var user2_id = 2;
    var user3_id = 3;

    pmc.set_partner(user1_id);
    pmc.set_partner(user3_id);

    assert.equal(pmc.is_partner(user1_id), true);
    assert.equal(pmc.is_partner(user2_id), false);
    assert.equal(pmc.is_partner(user3_id), true);
}());
