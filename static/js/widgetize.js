var widgetize = (function () {

var exports = {};

var widgets = {};

var tictactoe_data_holder = function () {
    var self = {};

    var me = people.my_current_user_id();
    var square_values = {};
    var num_filled = 0;
    var waiting = false;
    var game_over = false;

    function is_game_over() {
        var lines = [
            [1, 2, 3],
            [4, 5, 6],
            [7, 8, 9],
            [1, 4, 7],
            [2, 5, 8],
            [3, 6, 9],
            [1, 5, 9],
            [7, 5, 3],
        ];

        function line_won(line) {
            var token = square_values[line[0]];

            if (!token) {
                return false;
            }

            return (
                (square_values[line[1]] === token) &&
                (square_values[line[2]] === token));
        }

        return _.any(lines, line_won);
    }

    self.get_widget_data = function () {
        function square(i) {
            return {
                val: square_values[i] || i,
                idx: i,
                disabled: waiting || square_values[i] || game_over,
            };
        }

        var squares = [
            [square(1), square(2), square(3)],
            [square(4), square(5), square(6)],
            [square(7), square(8), square(9)],
        ];

        var move_status = waiting? "Wait..." : "Go ahead!";

        if (game_over) {
            move_status = "Game over!";
        }

        var widget_data = {
            squares: squares,
            move_status: move_status,
        };

        return widget_data;
    };

    self.handle = {
        square_click: {
            outbound: function (idx) {
                var event = {
                    type: 'square_click',
                    idx: idx,
                    num_filled: num_filled,
                };
                return event;
            },

            inbound: function (sender_id, data) {
                var idx = data.idx;

                if (data.num_filled !== num_filled) {
                    blueslip.info('out of sync', data.num_filled);
                    return;
                }

                var token = (num_filled % 2 === 0) ? 'X' : 'O';

                if (square_values[idx]) {
                    return;
                }

                waiting = (sender_id === me);

                square_values[idx] = token;
                num_filled += 1;

                game_over = is_game_over();
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

widgets.tictactoe = (function () {
    var cls = {};

    cls.activate = function (opts) {
        var self = {};

        var elem = opts.elem;
        var callback = opts.callback;

        var tictactoe_data = tictactoe_data_holder();

        function render() {
            var widget_data = tictactoe_data.get_widget_data();
            var html = templates.render('tictactoe-widget', widget_data);
            elem.html(html);

            elem.find("button.tictactoe-square").on('click', function (e) {
                e.stopPropagation();
                var idx = $(e.target).attr('data-idx');

                var data = tictactoe_data.handle.square_click.outbound(idx);
                callback(data);
            });
        }

        self.handle_events = function (events) {
            _.each(events, function (event) {
                tictactoe_data.handle_event(event.sender_id, event.data);
            });
            render();
        };

        render();

        return self;
    };

    return cls;
}());

var poll_data_holder = function () {
    // This object just holds data for a poll, although it
    // works closely with the widget's concept of how data
    // should be represented for rendering, plus how the
    // server sends us data.
    var self = {};

    var me = people.my_current_user_id();
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

                votes[sender_id] = 1;

                key_to_comment[key] = {
                    comment: comment,
                    user_id: sender_id,
                    votes: votes,
                };
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

                var votes = key_to_comment[key].votes;

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

widgets.poll = (function () {
    var cls = {};

    cls.activate = function (opts) {
        var self = {};

        var elem = opts.elem;
        var callback = opts.callback;

        var poll_data = poll_data_holder();

        function render() {
            var html = templates.render('poll-widget');
            elem.html(html);

            elem.find("button.poll-comment").on('click', function (e) {
                e.stopPropagation();
                var comment = elem.find("input.poll-comment").val();

                var data = poll_data.handle.new_comment.outbound(comment);
                callback(data);
            });
        }

        function render_results() {
            var widget_data = poll_data.get_widget_data();
            var html = templates.render('poll-widget-results', widget_data);
            elem.find('ul.poll-widget').html(html);

            elem.find("button.poll-vote").on('click', function (e) {
                e.stopPropagation();
                var key = $(e.target).attr('data-key');

                var data = poll_data.handle.vote.outbound(key);
                callback(data);
            });
        }

        self.handle_events = function (events) {
            _.each(events, function (event) {
                poll_data.handle_event(event.sender_id, event.data);
            });
            render_results();
        };

        render();
        render_results();

        return self;
    };

    return cls;
}());

exports.activate = function (in_opts) {
    var widget_type = in_opts.widget_type;
    var events = in_opts.events;
    var row = in_opts.row;
    var message = in_opts.message;
    var post_to_server = in_opts.post_to_server;

    events.shift();

    if (!widgets[widget_type]) {
        blueslip.warn('unknown widget_type', widget_type);
        return;
    }

    var content_holder = row.find('.message_content');

    if (message.widget) {
        content_holder.html(message.widget_elem);
        return;
    }

    var callback = function (data) {
        post_to_server({
            msg_type: 'widget',
            data: data,
        });
    };

    var elem = $('<div>');
    content_holder.html(elem);

    var widget = widgets[widget_type].activate({
        elem: elem,
        callback: callback,
        message: message,
    });

    // This is hacky, we should just maintain our own list.
    message.widget = widget;
    message.widget_elem = elem;

    // Replay any events that already happened.  (This is common
    // when you narrow to a message after other users have already
    // interacted with it.)
    widget.handle_events(events);
};

exports.handle_event = function (widget_event) {
    var message = message_store.get(widget_event.message_id);

    var events = [widget_event];

    message.widget.handle_events(events);
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = widgetize;
}
