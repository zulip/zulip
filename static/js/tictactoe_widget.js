var tictactoe_widget = (function () {

var exports = {};

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
                square_values[line[1]] === token &&
                square_values[line[2]] === token);
        }

        var board = [1, 2, 3, 4, 5, 6, 7, 8, 9];
        function filled(i) {
            return square_values[i];
        }

        return _.any(lines, line_won) || _.all(board, filled);
    }

    self.get_widget_data = function () {
        function square(i) {
            return {
                val: square_values[i],
                idx: i,
                disabled: waiting || square_values[i] || game_over,
            };
        }

        var squares = [
            [square(1), square(2), square(3)],
            [square(4), square(5), square(6)],
            [square(7), square(8), square(9)],
        ];

        var token = num_filled % 2 === 0 ? 'X' : 'O';
        var move_status = token + "'s turn";

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

                var token = num_filled % 2 === 0 ? 'X' : 'O';

                if (square_values[idx]) {
                    return;
                }

                waiting = sender_id === me;

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

exports.activate = function (opts) {
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

    elem.handle_events = function (events) {
        _.each(events, function (event) {
            tictactoe_data.handle_event(event.sender_id, event.data);
        });
        render();
    };

    render();
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = tictactoe_widget;
}

window.tictactoe_widget = tictactoe_widget;
