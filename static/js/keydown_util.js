/*
    See hotkey.js for handlers that are more app-wide.
*/

export const vim_left = "h";
export const vim_down = "j";
export const vim_up = "k";
export const vim_right = "l";

export function handle(opts) {
    opts.elem.on("keydown", (e) => {
        if (e.altKey || e.ctrlKey || e.shiftKey) {
            return;
        }

        const {key} = e;
        const handler = opts.handlers[key];
        if (!handler) {
            return;
        }

        const handled = handler();
        if (handled) {
            e.preventDefault();
            e.stopPropagation();
        }
    });
}
