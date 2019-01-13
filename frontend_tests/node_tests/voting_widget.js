zrequire('poll_widget');

set_global('$', global.make_zjquery());
set_global('i18n', global.stub_i18n);

set_global('people', {});
set_global('blueslip', {});
set_global('templates', {});

const noop = () => {};
const return_false = () => false;
const return_true = () => true;

run_test('poll_data_holder my question', () => {
    const is_my_poll = true;
    const question = 'Favorite color?';

    const sender_id = 99;
    people.my_current_user_id = () => sender_id;

    const data_holder = poll_widget.poll_data_holder(is_my_poll, question);

    let data = data_holder.get_widget_data();

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

    let  vote_event = {
        type: 'vote',
        key: '99,1',
        vote: 1,
    };

    data_holder.handle_event(sender_id, vote_event);
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

    const invalid_vote_event = {
        type: 'vote',
        key: '98,1',
        vote: 1,
    };

    blueslip.error = (msg) => {
        assert.equal(msg, `unknown key for poll: ${invalid_vote_event.key}`);
    };
    data_holder.handle_event(sender_id, invalid_vote_event);
    data = data_holder.get_widget_data();

    const comment_outbound_event = data_holder.handle.new_comment.outbound('new comment');
    assert.deepEqual(comment_outbound_event, {
        type: 'new_comment',
        idx: 2,
        comment: 'new comment',
    });

    const new_question = 'Any new plan?';
    const question_outbound_event = data_holder.handle.question.outbound(new_question);
    assert.deepEqual(question_outbound_event, {
        type: 'question',
        question: new_question,
    });

    const vote_outbound_event = data_holder.handle.vote.outbound('99,1');
    assert.deepEqual(vote_outbound_event, { type: 'vote', key: '99,1', vote: -1 });

    vote_event = {
        type: 'vote',
        key: '99,1',
        vote: -1,
    };

    data_holder.handle_event(sender_id, vote_event);
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
});

run_test('activate another person poll', () => {
    people.is_my_user_id = return_false;
    templates.render = (template_name) => {
        if (template_name === 'poll-widget') {
            return 'poll-widget';
        }
        if (template_name === 'poll-widget-results') {
            return 'poll-widget-results';
        }
    };

    const widget_elem = $('<div>').addClass('widget-content');

    let out_data;   // Used to check the event data sent to the server
    const callback = (data) => {
        out_data = data;
    };

    const opts = {
        elem: widget_elem,
        callback: callback,
        message: {
            sender_id: 100,
        },
    };

    const set_widget_find_result = (selector) => {
        const elem = $.create(selector);
        widget_elem.set_find_results(selector, elem);
        return elem;
    };

    const poll_comment = set_widget_find_result('button.poll-comment');
    const poll_comment_input = set_widget_find_result('input.poll-comment');
    const widget_comment_container = set_widget_find_result('ul.poll-widget');

    const poll_question = set_widget_find_result('button.poll-question');
    const poll_question_input = set_widget_find_result('input.poll-question');
    const poll_question_header = set_widget_find_result('.poll-question-header');
    const poll_question_container = set_widget_find_result('.poll-question-bar');
    const poll_comment_container = set_widget_find_result('.poll-comment-bar');

    const poll_vote_button = set_widget_find_result('button.poll-vote');

    let question_button_callback;
    let comment_button_callback;
    let vote_button_callback;

    poll_question.on = (event, func) => {
        assert.equal(event, 'click');
        question_button_callback = func;
    };

    poll_comment.on = (event, func) => {
        assert.equal(event, 'click');
        comment_button_callback = func;
    };

    poll_vote_button.on = (event, func) => {
        assert.equal(event, 'click');
        vote_button_callback = func;
    };

    poll_widget.activate(opts);

    assert.equal(widget_elem.html(), 'poll-widget');
    assert.equal(widget_comment_container.html(), 'poll-widget-results');
    assert.equal(poll_question_header.text(), '');

    const e = {
        stopPropagation: noop,
    };

    {
        /* Testing no data sent to server on clicking add question button */
        poll_question_input.val('Is it new?');
        out_data = undefined;
        question_button_callback(e);
        assert.deepEqual(out_data, undefined);
    }

    {
        /* Testing data sent to server on adding comment */
        poll_comment_input.val('cool choice');
        out_data = undefined;
        comment_button_callback(e);
        assert.deepEqual(out_data,  { type: 'new_comment', idx: 1, comment: 'cool choice' });

        poll_comment_input.val('');
        out_data = undefined;
        comment_button_callback(e);
        assert.deepEqual(out_data, undefined);
    }

    const vote_events = [
        {
            sender_id: 100,
            data: {
                type: 'new_comment',
                idx: 1,
                comment: 'release now',
            },
        },
        {
            sender_id: 100,
            data: {
                type: 'vote',
                key: '100,1',
                vote: 1,
            },
        },
    ];

    widget_elem.handle_events(vote_events);

    assert(poll_question.attr('disabled'));
    assert(poll_question_input.attr('disabled'));

    {
        /* Testing data sent to server on voting */
        poll_vote_button.attr('data-key', '100,1');
        const e = {
            stopPropagation: noop,
            target: poll_vote_button,
        };
        out_data = undefined;
        vote_button_callback(e);
        assert.deepEqual(out_data, { type: 'vote', key: '100,1', vote: 1 });
    }

    const add_question_event = [
        {
            sender_id: 100,
            data: {
                type: 'question',
                question: 'best plan?',
            },
        },
    ];

    poll_question_container.show();

    widget_elem.handle_events(add_question_event);

    assert(!poll_question_container.visible());
    assert(poll_comment_container.visible());
});

run_test('activate own poll', () => {
    $.clear_all_elements();

    people.is_my_user_id = return_true;
    templates.render = (template_name) => {
        if (template_name === 'poll-widget') {
            return 'poll-widget';
        }
        if (template_name === 'poll-widget-results') {
            return 'poll-widget-results';
        }
    };

    const widget_elem = $('<div>').addClass('widget-content');
    let out_data;
    const callback = (data) => {
        out_data = data;
    };
    const opts = {
        elem: widget_elem,
        callback: callback,
        message: {
            sender_id: 100,
        },
        extra_data: {
            question: 'Where to go?',
        },
    };

    const set_widget_find_result = (selector) => {
        const elem = $.create(selector);
        widget_elem.set_find_results(selector, elem);
        return elem;
    };

    const poll_comment = set_widget_find_result('button.poll-comment');
    const poll_comment_input = set_widget_find_result('input.poll-comment');
    const widget_comment_container = set_widget_find_result('ul.poll-widget');

    const poll_question = set_widget_find_result('button.poll-question');
    const poll_question_input = set_widget_find_result('input.poll-question');
    const poll_question_header = set_widget_find_result('.poll-question-header');
    const poll_question_container = set_widget_find_result('.poll-question-bar');
    const poll_comment_container = set_widget_find_result('.poll-comment-bar');

    const poll_vote_button = set_widget_find_result('button.poll-vote');

    let question_button_callback;

    poll_question.on = (event, func) => {
        assert.equal(event, 'click');
        question_button_callback = func;
    };

    // Following event handler are already tested and doesn't make sense
    // to test them again
    poll_comment.on = noop;
    poll_vote_button.on = noop;

    poll_question.attr('disabled', false);
    poll_question_input.attr('disabled', false);
    // Setting visiblity to true as default is false
    poll_question_container.show();

    poll_widget.activate(opts);

    assert.equal(widget_elem.html(), 'poll-widget');
    assert.equal(widget_comment_container.html(), 'poll-widget-results');
    assert.equal(poll_question_header.text(), 'Where to go?');
    assert(poll_question.attr('disabled', false));
    assert(poll_question_input.attr('disabled', false));

    {
        /* Testing data sent to server on editing question */
        const e = {
            stopPropagation: noop,
        };

        poll_question_input.val('Is it new?');
        out_data = undefined;
        question_button_callback(e);
        assert.deepEqual(out_data,  { type: 'question', question: 'Is it new?' });

        poll_comment_input.val('');
        out_data = undefined;
        question_button_callback(e);
        assert.deepEqual(out_data, undefined);
    }
    assert(poll_comment_container.visible());
});
