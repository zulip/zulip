"use strict";

const render_widgets_tictactoe_widget = require("../templates/widgets/tictactoe_widget.hbs");

const people = require("./people");

class TicTacToeData {
    me = people.my_current_user_id();
    square_values = new Map();
    num_filled = 0;
    waiting = false;
    game_over = false;

    is_game_over() {
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

        const line_won = (line) => {
            const token = this.square_values.get(line[0]);

            if (!token) {
                return false;
            }

            return (
                this.square_values.get(line[1]) === token &&
                this.square_values.get(line[2]) === token
            );
        };

        const board = [1, 2, 3, 4, 5, 6, 7, 8, 9];
        const filled = (i) => this.square_values.get(i);

        return lines.some(line_won) || board.every(filled);
    }

    get_widget_data() {
        const square = (i) => ({
            val: this.square_values.get(i),
            idx: i,
            disabled: this.waiting || this.square_values.get(i) || this.game_over,
        });

        const squares = [
            [square(1), square(2), square(3)],
            [square(4), square(5), square(6)],
            [square(7), square(8), square(9)],
        ];

        const token = this.num_filled % 2 === 0 ? "X" : "O";
        let move_status = token + "'s turn";

        if (this.game_over) {
            move_status = "Game over!";
        }

        const widget_data = {
            squares,
            move_status,
        };

        return widget_data;
    }

    handle = {
        square_click: {
            outbound: (idx) => {
                const event = {
                    type: "square_click",
                    idx,
                    num_filled: this.num_filled,
                };
                return event;
            },

            inbound: (sender_id, data) => {
                const idx = data.idx;

                if (data.num_filled !== this.num_filled) {
                    blueslip.info("out of sync", data.num_filled);
                    return;
                }

                const token = this.num_filled % 2 === 0 ? "X" : "O";

                if (this.square_values.has(idx)) {
                    return;
                }

                this.waiting = sender_id === this.me;

                this.square_values.set(idx, token);
                this.num_filled += 1;

                this.game_over = this.is_game_over();
            },
        },
    };

    handle_event(sender_id, data) {
        const type = data.type;
        if (this.handle[type]) {
            this.handle[type].inbound(sender_id, data);
        }
    }
}

exports.activate = function (opts) {
    const elem = opts.elem;
    const callback = opts.callback;

    const tictactoe_data = new TicTacToeData();

    function render() {
        const widget_data = tictactoe_data.get_widget_data();
        const html = render_widgets_tictactoe_widget(widget_data);
        elem.html(html);

        elem.find("button.tictactoe-square").on("click", (e) => {
            e.stopPropagation();
            const str_idx = $(e.target).attr("data-idx");
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
