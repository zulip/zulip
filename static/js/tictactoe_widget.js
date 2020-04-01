const render_widgets_tictactoe_widget = require('../templates/widgets/tictactoe_widget.hbs');

const tictactoe_data_holder = function () {
    const self = {};

    const me = people.my_current_user_id();
    const square_values = new Map();
    let num_filled = 0;
    let waiting = false;
    let game_over = false;

    function is_game_over() {
        const lines = [
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
            const token = square_values.get(line[0]);

            if (!token) {
                return false;
            }

            return (
                square_values.get(line[1]) === token &&
                square_values.get(line[2]) === token);
        }

        const board = [1, 2, 3, 4, 5, 6, 7, 8, 9];
        function filled(i) {
            return square_values.get(i);
        }

        return lines.some(line_won) || board.every(filled);
    }

    self.get_widget_data = function () {
        function square(i) {
            return {
                val: square_values.get(i),
                idx: i,
                disabled: waiting || square_values.get(i) || game_over,
            };
        }

        const squares = [
            [square(1), square(2), square(3)],
            [square(4), square(5), square(6)],
            [square(7), square(8), square(9)],
        ];

        const token = num_filled % 2 === 0 ? 'X' : 'O';
        let move_status = token + "'s turn";

        if (game_over) {
            move_status = "Game over!";
        }

        const widget_data = {
            squares: squares,
            move_status: move_status,
        };

        return widget_data;
    };

    self.handle = {
        square_click: {
            outbound: function (idx) {
                const event = {
                    type: 'square_click',
                    idx: idx,
                    num_filled: num_filled,
                };
                return event;
            },

            inbound: function (sender_id, data) {
                const idx = data.idx;

                if (data.num_filled !== num_filled) {
                    blueslip.info('out of sync', data.num_filled);
                    return;
                }

                const token = num_filled % 2 === 0 ? 'X' : 'O';

                if (square_values.has(idx)) {
                    return;
                }

                waiting = sender_id === me;

                square_values.set(idx, token);
                num_filled += 1;

                game_over = is_game_over();
            },
        },
    };


    self.handle_event = function (sender_id, data) {
        const type = data.type;
        if (self.handle[type]) {
            self.handle[type].inbound(sender_id, data);
        }
    };

    return self;
};

exports.activate = function (opts) {
    const elem = opts.elem;
    const callback = opts.callback;

    const tictactoe_data = tictactoe_data_holder();

    function render() {
        const widget_data = tictactoe_data.get_widget_data();
        const html = render_widgets_tictactoe_widget(widget_data);
        elem.html(html);

        elem.find("button.tictactoe-square").on('click', function (e) {
            e.stopPropagation();
            const str_idx = $(e.target).attr('data-idx');
            const idx = parseInt(str_idx, 10);

            const data = tictactoe_data.handle.square_click.outbound(idx);
            callback(data);
        });
    }

    elem.handle_events = function (events) {
        for (const event of events) {
            tictactoe_data.handle_event(event.sender_id, event.data);
        }

        render();
    };

    render();
};

window.tictactoe_widget = exports;
