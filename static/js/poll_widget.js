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
                poll_question = data.question;
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
        question = opts.extra_data.question;
    }

    var is_my_poll = people.is_my_user_id(opts.message.sender_id);
    var poll_data = exports.poll_data_holder(is_my_poll, question);

    function render() {
        var html = templates.render('poll-widget');
        elem.html(html);

        elem.find("button.poll-comment").on('click', function (e) {
            e.stopPropagation();
            var poll_comment_input = elem.find("input.poll-comment");
            var comment = poll_comment_input.val().trim();

            if (comment === '') {
                return;
            }

            poll_comment_input.val('').focus();

            var data = poll_data.handle.new_comment.outbound(comment);
            callback(data);
        });

        elem.find("button.poll-question").on('click', function (e) {
            e.stopPropagation();
            var poll_question_input = elem.find("input.poll-question");
            var question = poll_question_input.val().trim();

            if (question === '') {
                return;
            }

            poll_question_input.val('').focus();

            var data = poll_data.handle.question.outbound(question);
            callback(data);
        });
    }

    function render_results() {
        var widget_data = poll_data.get_widget_data();
        var html = templates.render('poll-widget-results', widget_data);
        elem.find('ul.poll-widget').html(html);

        elem.find('.poll-question-header').text(widget_data.question);
        if (!is_my_poll) {
            if (widget_data.question !== '') {
                // For the non-senders, we hide the question input bar
                // when we have a question assigned to the poll
                elem.find('.poll-question-bar').hide();
            } else {
                // For the non-senders we disable the question input bar
                // when we have no question assigned to the poll
                elem.find('button.poll-question').attr('disabled', true);
                elem.find('input.poll-question').attr('disabled', true);
            }
        }
        if (widget_data.question !== '') {
            elem.find('button.poll-question').text(i18n.t('Edit question'));
            elem.find('.poll-comment-bar').show();
        } else {
            elem.find('.poll-comment-bar').hide();
        }

        elem.find("button.poll-vote").on('click', function (e) {
            e.stopPropagation();
            var key = $(e.target).attr('data-key');

            var data = poll_data.handle.vote.outbound(key);
            callback(data);
        });
    }

    elem.handle_events = function (events) {
        _.each(events, function (event) {
            poll_data.handle_event(event.sender_id, event.data);
        });
        render_results();
    };

    render();
    render_results();
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = poll_widget;
}

window.poll_widget = poll_widget;
