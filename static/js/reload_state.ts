/*
    We want his module to load pretty early in the process
    of starting the app, so that people.js can load early.
    All the heavy lifting for reload logic happens in
    reload.js, which has lots of UI dependencies.  If we
    didn't split out this module, our whole dependency tree
    would be kind of upside down.
*/

let reload_in_progress = false;
let reload_pending = false;
export let csrf_failed_handler: (() => void) | undefined;

export function clear_for_testing(): void {
    reload_in_progress = false;
    reload_pending = false;
    csrf_failed_handler = undefined;
}

export function is_pending(): boolean {
    return reload_pending;
}

export function is_in_progress(): boolean {
    return reload_in_progress;
}

export function set_state_to_pending(): void {
    // Why do we never set this back to false?
    // Because the reload is gonna happen next. :)
    // I was briefly confused by this, hence the comment.
    reload_pending = true;
}

export function set_state_to_in_progress(): void {
    reload_in_progress = true;
}

export function set_csrf_failed_handler(handler: () => void): void {
    csrf_failed_handler = handler;
}
