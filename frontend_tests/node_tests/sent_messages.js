var sent_messages = require('js/sent_messages.js');

(function test_ids() {
    sent_messages.reset_id_state();

    var client_message_id = sent_messages.get_new_client_message_id({
        local_id: 42,
    });

    assert.equal(client_message_id, 1);

    var local_id = sent_messages.get_local_id({
        client_message_id: 1,
    });

    assert.equal(local_id, 42);


    client_message_id = sent_messages.get_new_client_message_id({});

    assert.equal(client_message_id, 2);

    local_id = sent_messages.get_local_id({
        client_message_id: 2,
    });

    assert.equal(local_id, undefined);

    local_id = sent_messages.get_local_id({
        client_message_id: undefined,
    });
    assert.equal(local_id, undefined);

}());
