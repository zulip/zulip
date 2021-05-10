/*
    See hotkey.js for handlers that are more app-wide.
*/

// Note that these keycodes differ from those in hotkey.js, because
// we're using keydown rather than keypress.  It's unclear whether
// there's a good reason for this difference.
const keys = {
    13: "enter_key", // Enter
    37: "left_arrow", // // Left arrow
    38: "up_arrow", // Up arrow
    39: "right_arrow", // Right arrow
    40: "down_arrow", // Down arrow
    72: "vim_left", // 'H'
    74: "vim_down", // 'J'
    75: "vim_up", // 'K'
    76: "vim_right", // 'L'
};

export function handle(opts) {
    opts.elem.on("keydown", (e) => {
        const key = e.which || e.keyCode;

        if (e.altKey || e.ctrlKey || e.shiftKey) {
            return;
        }

        const key_name = keys[key];

        if (!key_name) {
            return;
        }

        if (!opts.handlers[key_name]) {
            return;
        }

        const handled = opts.handlers[key_name]();

        if (handled) {
            e.preventDefault();
            e.stopPropagation();
        }
    });
}
