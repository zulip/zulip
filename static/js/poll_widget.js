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
            // We hide the edit pencil button for non-senders
            elem.find('.poll-edit-question').hide();
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
        } else {
            // Hide the edit pencil icon if the question is still not
            // assigned for the senders
            if (widget_data.question === '') {
                elem.find('.poll-edit-question').hide();
            } else {
                elem.find('.poll-edit-question').show();
            }
        }
        if (widget_data.question !== '') {
            // As soon as a poll-question is assigined
            // we change the "Add Question" button to a check button
            elem.find('button.poll-question').empty().addClass('fa fa-check poll-question-check');
            // The d-none class keeps the cancel editing question button hidden
            // as long as "Add Question" button is displayed
            elem.find('button.poll-question-remove').removeClass('d-none');
            // We hide the whole question bar if question is assigned
            elem.find('.poll-question-bar').hide();
            elem.find('.poll-comment-bar').show();
        } else {
            elem.find('.poll-comment-bar').hide();
            elem.find('.poll-edit-question').hide();
        }
        if (is_my_poll) {
            // We disable the check button if the input field is empty
            // and enable it as soon as something is entered in input field
            elem.find('input.poll-question').on('keyup', function () {
                if (elem.find('input.poll-question').val().length > 0) {
                    elem.find('button.poll-question').removeAttr('disabled');
                } else {
                    elem.find('button.poll-question').attr('disabled', true);

                }
            });
            // However doing above leaves the check button disabled
            // for the next time when someone is trying to enter a question if
            // someone empties the input field and clicks on cancel edit button.
            // We fix this by checking if there is text in input field if
            // edit question pencil icon is clicked and enable the button if
            // there is text in input field.
            elem.find('.poll-edit-question').on('click', function () {
                if (elem.find('input.poll-question').val().length > 0) {
                    elem.find('button.poll-question').removeAttr('disabled');
                }
            });
        }
        elem.find(".poll-edit-question").on('click', function () {
            // As soon as edit question button is clicked
            // we hide the Question and the edit question pencil button
            // and display the input box for editing the question
            elem.find('.poll-question-header').hide();
            elem.find('.poll-question-bar').show();
            elem.find('.poll-edit-question').hide();
            elem.find('input.poll-question').empty().val(widget_data.question).select();
        });

        elem.find("button.poll-question").on('click', function () {
            if (widget_data.question !== '') {
                // we display the question and hide the input box for editing
                elem.find(".poll-question-bar").hide();
                elem.find('.poll-question-header').show();
            }
        });

        elem.find("button.poll-question-remove").on('click', function () {
            // On clicking the cross i.e. cancel editing button
            // we display the previos question as it is
            // and hide the input box and buttons for editing
            elem.find('.poll-question-bar').hide();
            elem.find('.poll-edit-question').show();
            elem.find('.poll-question-header').show();
        });
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
