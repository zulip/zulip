zrequire('unread');
zrequire('util');

zrequire('Filter', 'js/filter');
zrequire('MessageListData', 'js/message_list_data');

set_global('page_params', {});
set_global('blueslip', global.make_zblueslip());

global.patch_builtin('setTimeout', (f, delay) => {
    assert.equal(delay, 0);
    return f();
});

function make_msg(msg_id) {
    return {
        id: msg_id,
        unread: true,
    };
}

function make_msgs(msg_ids) {
    return _.map(msg_ids, make_msg);
}

(function test_basics() {
    const mld = new MessageListData({
        muting_enabled: false,
        filter: undefined,
    });

    assert.equal(mld.is_search(), false);

    mld.add(make_msgs([35, 25, 15, 45]));

    function assert_contents(msg_ids) {
        const msgs = mld.all_messages();
        assert.deepEqual(msgs, make_msgs(msg_ids));
    }
    assert_contents([15, 25, 35, 45]);

    const new_msgs = make_msgs([10, 20, 30, 40, 50, 60, 70]);
    const info = mld.triage_messages(new_msgs);

    assert.deepEqual(info, {
        top_messages: make_msgs([10]),
        interior_messages: make_msgs([20, 30, 40]),
        bottom_messages: make_msgs([50, 60, 70]),
    });

    mld.prepend(info.top_messages);
    mld.append(info.bottom_messages);

    assert_contents([10, 15, 25, 35, 45, 50, 60, 70]);

    mld.add(info.interior_messages);

    assert_contents([10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70]);

    assert.equal(mld.selected_id(), -1);
    assert.equal(mld.closest_id(8), 10);
    assert.equal(mld.closest_id(27), 25);
    assert.equal(mld.closest_id(72), 70);

    mld.set_selected_id(50);
    assert.equal(mld.selected_id(), 50);
    assert.equal(mld.selected_idx(), 8);

    mld.remove([mld.get(50)]);
    assert_contents([10, 15, 20, 25, 30, 35, 40, 45, 60, 70]);

    mld.update_items_for_muting();
    assert_contents([10, 15, 20, 25, 30, 35, 40, 45, 60, 70]);

    mld.reset_select_to_closest();
    assert.equal(mld.selected_id(), 45);
    assert.equal(mld.selected_idx(), 7);

    assert.equal(mld.first_unread_message_id(), 10);
    mld.get(10).unread = false;
    assert.equal(mld.first_unread_message_id(), 15);


    mld.clear();
    assert_contents([]);
    assert.equal(mld.closest_id(99), -1);
    assert.equal(mld.get_last_message_sent_by_me(), undefined);

    mld.add(make_msgs([120, 125.01, 130, 140]));
    assert_contents([120, 125.01, 130, 140]);
    mld.set_selected_id(125.01);
    assert.equal(mld.selected_id(), 125.01);

    mld.get(125.01).id = 145;
    mld.change_message_id(125.01, 145, {
        re_render: () => {},
    });
    assert_contents([120, 130, 140, 145]);

    _.each(mld.all_messages(), (msg) => {
        msg.unread = false;
    });

    assert.equal(mld.first_unread_message_id(), 145);
}());

(function test_errors() {
    const mld = new MessageListData({
        muting_enabled: false,
        filter: undefined,
    });
    assert.equal(mld.get('bogus-id'), undefined);
}());
