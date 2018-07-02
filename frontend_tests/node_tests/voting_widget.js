zrequire('voting_widget');

set_global('people', {});

run_test('poll_data_holder my question', () => {
    const is_my_poll = true;
    const question = 'Favorite color?';

    const sender_id = 99;
    people.my_current_user_id = () => sender_id;

    const data_holder = voting_widget.poll_data_holder(is_my_poll, question);

    var data = data_holder.get_widget_data();

    assert.deepEqual(data, {
        comments: [],
        question: 'Favorite color?',
    });

    const question_event = {
        type: 'question',
        question: 'best plan?',
    };

    data_holder.handle_event(sender_id, question_event);
    data = data_holder.get_widget_data();

    assert.deepEqual(data, {
        comments: [],
        question: 'best plan?',
    });

    const comment_event = {
        type: 'new_comment',
        idx: 1,
        comment: 'release now',
    };

    people.safe_full_names = () => '';

    data_holder.handle_event(sender_id, comment_event);
    data = data_holder.get_widget_data();

    assert.deepEqual(data, {
        comments: [
            {
                comment: 'release now',
                names: '',
                count: 0,
                key: '99,1',
            },
        ],
        question: 'best plan?',
    });

    const vote_event = {
        type: 'vote',
        key: '99,1',
        vote: 1,
    };

    data_holder.handle_event(sender_id, vote_event);
    data = data_holder.get_widget_data();
    data = data_holder.get_widget_data();

    assert.deepEqual(data, {
        comments: [
            {
                comment: 'release now',
                names: '',
                count: 1,
                key: '99,1',
            },
        ],
        question: 'best plan?',
    });

});
