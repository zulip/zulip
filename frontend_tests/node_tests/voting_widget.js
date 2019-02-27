zrequire('poll_widget');

set_global('$', global.make_zjquery());
set_global('i18n', global.stub_i18n);

set_global('people', {});
set_global('blueslip', global.make_zblueslip());
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
        options: [],
        question: 'Favorite color?',
    });

    const question_event = {
        type: 'question',
        question: 'best plan?',
    };

    data_holder.handle_event(sender_id, question_event);
    data = data_holder.get_widget_data();

    assert.deepEqual(data, {
        options: [],
        question: 'best plan?',
    });

    const option_event = {
        type: 'new_option',
        idx: 1,
        option: 'release now',
    };

    people.safe_full_names = () => '';

    data_holder.handle_event(sender_id, option_event);
    data = data_holder.get_widget_data();

    assert.deepEqual(data, {
        options: [
            {
                option: 'release now',
                names: '',
                count: 0,
                key: '99,1',
                current_user_vote: false,
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
        options: [
            {
                option: 'release now',
                names: '',
                count: 1,
                key: '99,1',
                current_user_vote: true,
            },
        ],
        question: 'best plan?',
    });

    const invalid_vote_event = {
        type: 'vote',
        key: '98,1',
        vote: 1,
    };

    blueslip.set_test_data('warn', `unknown key for poll: ${invalid_vote_event.key}`);
    data_holder.handle_event(sender_id, invalid_vote_event);
    data = data_holder.get_widget_data();
    assert.equal(blueslip.get_test_logs('warn').length, 1);
    blueslip.clear_test_data();

    const option_outbound_event = data_holder.handle.new_option.outbound('new option');
    assert.deepEqual(option_outbound_event, {
        type: 'new_option',
        idx: 2,
        option: 'new option',
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
        options: [
            {
                option: 'release now',
                names: '',
                count: 0,
                key: '99,1',
                current_user_vote: false,
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
        extra_data: {
            question: 'What do you want?',
        },
    };

    const set_widget_find_result = (selector) => {
        const elem = $.create(selector);
        widget_elem.set_find_results(selector, elem);
        return elem;
    };

    const poll_option = set_widget_find_result('button.poll-option');
    const poll_option_input = set_widget_find_result('input.poll-option');
    const widget_option_container = set_widget_find_result('ul.poll-widget');

    const poll_question_submit = set_widget_find_result('button.poll-question-check');
    const poll_edit_question = set_widget_find_result('.poll-edit-question');
    const poll_question_header = set_widget_find_result('.poll-question-header');
    const poll_question_container = set_widget_find_result('.poll-question-bar');
    const poll_option_container = set_widget_find_result('.poll-option-bar');

    const poll_vote_button = set_widget_find_result('button.poll-vote');
    const poll_please_wait = set_widget_find_result('.poll-please-wait');
    const poll_author_help = set_widget_find_result('.poll-author-help');

    set_widget_find_result('button.poll-question-remove');
    set_widget_find_result('input.poll-question');

    let option_button_callback;
    let vote_button_callback;

    poll_option.on = (event, func) => {
        assert.equal(event, 'click');
        option_button_callback = func;
    };

    poll_vote_button.on = (event, func) => {
        assert.equal(event, 'click');
        vote_button_callback = func;
    };

    poll_question_header.toggle = (show) => {
        assert(show);
    };

    poll_edit_question.toggle = (show) => {
        assert(!show);
    };

    var show_submit = false;
    poll_question_submit.toggle = (show) => {
        assert.equal(show, show_submit);
    };

    poll_question_container.toggle = (show) => {
        assert(!show);
    };

    poll_option_container.toggle = (show) => {
        assert.equal(show, true);
    };

    poll_please_wait.toggle = (show) => {
        assert.equal(show, false);
    };

    poll_author_help.toggle = (show) => {
        assert(!show);
    };

    poll_widget.activate(opts);

    assert.equal(widget_elem.html(), 'poll-widget');
    assert.equal(widget_option_container.html(), 'poll-widget-results');
    assert.equal(poll_question_header.text(), 'What do you want?');

    const e = {
        stopPropagation: noop,
    };

    {
        /* Testing data sent to server on adding option */
        poll_option_input.val('cool choice');
        out_data = undefined;
        option_button_callback(e);
        assert.deepEqual(out_data,  { type: 'new_option', idx: 1, option: 'cool choice' });

        poll_option_input.val('');
        out_data = undefined;
        option_button_callback(e);
        assert.deepEqual(out_data, undefined);
    }

    const vote_events = [
        {
            sender_id: 100,
            data: {
                type: 'new_option',
                idx: 1,
                option: 'release now',
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

    widget_elem.handle_events(add_question_event);
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

    const poll_option = set_widget_find_result('button.poll-option');
    const poll_option_input = set_widget_find_result('input.poll-option');
    const widget_option_container = set_widget_find_result('ul.poll-widget');

    const poll_question_submit = set_widget_find_result('button.poll-question-check');
    const poll_edit_question = set_widget_find_result('.poll-edit-question');
    const poll_question_input = set_widget_find_result('input.poll-question');
    const poll_question_header = set_widget_find_result('.poll-question-header');
    const poll_question_container = set_widget_find_result('.poll-question-bar');
    const poll_option_container = set_widget_find_result('.poll-option-bar');

    const poll_vote_button = set_widget_find_result('button.poll-vote');
    const poll_please_wait = set_widget_find_result('.poll-please-wait');
    const poll_author_help = set_widget_find_result('.poll-author-help');

    set_widget_find_result('button.poll-question-remove');

    let question_button_callback;

    poll_question_submit.on = (event, func) => {
        assert.equal(event, 'click');
        question_button_callback = func;
    };

    // Following event handler are already tested and doesn't make sense
    // to test them again
    poll_option.on = noop;
    poll_vote_button.on = noop;

    poll_question_header.toggle = (show) => {
        assert(show);
    };

    poll_edit_question.toggle = (show) => {
        assert(show);
    };

    var show_submit = false;
    poll_question_submit.toggle = (show) => {
        assert.equal(show, show_submit);
    };

    poll_question_container.toggle = (show) => {
        assert(!show);
    };

    poll_option_container.toggle = (show) => {
        assert(show);
    };

    poll_please_wait.toggle = (show) => {
        assert(!show);
    };

    poll_author_help.toggle = (show) => {
        assert(!show);
    };

    poll_widget.activate(opts);

    assert.equal(widget_elem.html(), 'poll-widget');
    assert.equal(widget_option_container.html(), 'poll-widget-results');
    assert.equal(poll_question_header.text(), 'Where to go?');

    {
        /* Testing data sent to server on editing question */
        const e = {
            stopPropagation: noop,
        };

        poll_question_input.val('Is it new?');
        out_data = undefined;
        show_submit = true;
        question_button_callback(e);
        assert.deepEqual(out_data,  { type: 'question', question: 'Is it new?' });

        poll_option_input.val('');
        out_data = undefined;
        question_button_callback(e);
        assert.deepEqual(out_data, undefined);
    }
});
