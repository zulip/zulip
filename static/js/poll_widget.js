var poll_widget = (function () {

var exports = {};

exports.poll_data_holder = function (is_my_poll, question) {
    // This object just holds data for a poll, although it
    // works closely with the widget's concept of how data
    // should be represented for rendering, plus how the
    // server sends us data.
    var self = {};

    var me = people.my_current_user_id();
    var poll_question = question;
    var key_to_comment = {};
    var my_idx = 1;

    var input_mode = is_my_poll; // for now

    self.set_question = function (new_question) {
        input_mode = false;
        poll_question = new_question;
    };

    self.get_question = function () {
        return poll_question;
    };

    self.set_input_mode = function () {
        input_mode = true;
    };

    self.clear_input_mode = function () {
        input_mode = false;
    };

    self.get_input_mode = function () {
        return input_mode;
    };

    if (question) {
        self.set_question(question);
    }

    self.get_widget_data = function () {
        var comments = [];

        _.each(key_to_comment, function (obj, key) {
            var voters = _.keys(obj.votes);

            comments.push({
                comment: obj.comment,
                names: people.safe_full_names(voters),
                count: voters.length,
                key: key,
            });
        });


        var widget_data = {
            comments: comments,
            question: poll_question,
        };

        return widget_data;
    };

    self.handle = {
        new_comment: {
            outbound: function (comment) {
                var event = {
                    type: 'new_comment',
                    idx: my_idx,
                    comment: comment,
                };

                my_idx += 1;

                return event;
            },

            inbound: function (sender_id, data) {
                var idx = data.idx;
                var key = sender_id + ',' + idx;
                var comment = data.comment;
                var votes = {};

                key_to_comment[key] = {
                    comment: comment,
                    user_id: sender_id,
                    votes: votes,
                };

                if (my_idx <= idx) {
                    my_idx = idx + 1;
                }
            },
        },

        question: {
            outbound: function (question) {
                var event = {
                    type: 'question',
                    question: question,
                };
                if (is_my_poll) {
                    return event;
                }
                return;

            },

            inbound: function (sender_id, data) {
                self.set_question(data.question);
            },
        },

        vote: {
            outbound: function (key) {
                var vote = 1;

                // toggle
                if (key_to_comment[key].votes[me]) {
                    vote = -1;
                }

                var event = {
                    type: 'vote',
                    key: key,
                    vote: vote,
                };

                return event;
            },

            inbound: function (sender_id, data) {
                var key = data.key;
                var vote = data.vote;
                var comment = key_to_comment[key];

                if (comment === undefined) {
                    blueslip.error('unknown key for poll: ' + key);
                    return;
                }

                var votes = comment.votes;

                if (vote === 1) {
                    votes[sender_id] = 1;
                } else {
                    delete votes[sender_id];
                }
            },
        },
    };

    self.handle_event = function (sender_id, data) {
        var type = data.type;
        if (self.handle[type]) {
            self.handle[type].inbound(sender_id, data);
        }
    };

    return self;
};

exports.activate = function (opts) {
    var elem = opts.elem;
    var callback = opts.callback;

    var question = '';
    if (opts.extra_data) {
        question = opts.extra_data.question || '';
    }

    var is_my_poll = people.is_my_user_id(opts.message.sender_id);
    var poll_data = exports.poll_data_holder(is_my_poll, question);

    function update_edit_controls() {
        var has_question = elem.find('input.poll-question').val().trim() !== '';
        elem.find('button.poll-question-check').toggle(has_question);
    }

    function render_question() {
        var question = poll_data.get_question();
        var input_mode = poll_data.get_input_mode();
        var can_edit = is_my_poll && !input_mode;
        var has_question = question.trim() !== '';
        var can_vote = has_question;
        var waiting = !is_my_poll && !has_question;
        var author_help = is_my_poll && !has_question;

        elem.find('.poll-question-header').toggle(!input_mode);
        elem.find('.poll-question-header').text(question);
        elem.find('.poll-edit-question').toggle(can_edit);
        update_edit_controls();

        elem.find('.poll-question-bar').toggle(input_mode);
        elem.find('.poll-comment-bar').toggle(can_vote);

        elem.find('.poll-please-wait').toggle(waiting);

        elem.find('.poll-author-help').toggle(author_help);
    }

    function start_editing() {
        poll_data.set_input_mode();

        var question = poll_data.get_question();
        elem.find('input.poll-question').val(question);
        render_question();
        elem.find('input.poll-question').focus();
    }

    function abort_edit() {
        poll_data.clear_input_mode();
        render_question();
    }

    function submit_question() {
        var poll_question_input = elem.find("input.poll-question");
        var new_question = poll_question_input.val().trim();
        var old_question = poll_data.get_question();

        // We should disable the button for blank questions,
        // so this is just defensive code.
        if (new_question.trim() === '') {
            new_question = old_question;
        }

        // Optimistically set the question locally.
        poll_data.set_question(new_question);
        render_question();

        // If there were no actual edits, we can exit now.
        if (new_question === old_question) {
            return;
        }

        // Broadcast the new question to our peers.
        var data = poll_data.handle.question.outbound(new_question);
        callback(data);
    }

    function submit_option() {
        var poll_comment_input = elem.find("input.poll-comment");
        var comment = poll_comment_input.val().trim();

        if (comment === '') {
            return;
        }

        poll_comment_input.val('').focus();

        var data = poll_data.handle.new_comment.outbound(comment);
        callback(data);
    }

    function submit_vote(key) {
        var data = poll_data.handle.vote.outbound(key);
        callback(data);
    }

    function build_widget() {
        var html = templates.render('poll-widget');
        elem.html(html);

        elem.find('input.poll-question').on('keyup', function (e) {
            e.stopPropagation();
            update_edit_controls();
        });

        elem.find('input.poll-question').on('keydown', function (e) {
            e.stopPropagation();

            if (e.keyCode === 13) {
                submit_question();
                return;
            }

            if (e.keyCode === 27) {
                abort_edit();
                return;
            }
        });

        elem.find('.poll-edit-question').on('click', function (e) {
            e.stopPropagation();
            start_editing();
        });

        elem.find("button.poll-question-check").on('click', function (e) {
            e.stopPropagation();
            submit_question();
        });

        elem.find("button.poll-question-remove").on('click', function (e) {
            e.stopPropagation();
            abort_edit();
        });

        elem.find("button.poll-comment").on('click', function (e) {
            e.stopPropagation();
            submit_option();
        });

        elem.find('input.poll-comment').on('keydown', function (e) {
            e.stopPropagation();

            if (e.keyCode === 13) {
                submit_option();
                return;
            }

            if (e.keyCode === 27) {
                $('input.poll-comment').val('');
                return;
            }
        });

    }

    function render_results() {
        var widget_data = poll_data.get_widget_data();

        var html = templates.render('poll-widget-results', widget_data);
        elem.find('ul.poll-widget').html(html);

        elem.find("button.poll-vote").off('click').on('click', function (e) {
            e.stopPropagation();
            var key = $(e.target).attr('data-key');
            submit_vote(key);
        });
    }

    elem.handle_events = function (events) {
        _.each(events, function (event) {
            poll_data.handle_event(event.sender_id, event.data);
        });
        render_question();
        render_results();
    };

    build_widget();
    render_question();
    render_results();
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = poll_widget;
}

window.poll_widget = poll_widget;
