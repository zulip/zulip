// Track the difference between the server's clock and the client's
// clock, so that time-limit checks (message editing, topic moving,
// etc.) use the server's idea of "now" instead of the local clock.
// Without this, a client whose clock is ahead will hide the edit
// option even when the server would still accept the edit.

let clock_offset_seconds = 0;

export function now(): number {
    return Date.now() / 1000 + clock_offset_seconds;
}

// Called with a server-supplied timestamp (presence responses,
// page load) to update our offset estimate.
export function update_server_offset(server_timestamp: number): void {
    clock_offset_seconds = server_timestamp - Date.now() / 1000;
}

// Test helpers.
export function get_clock_offset_seconds(): number {
    return clock_offset_seconds;
}

export function set_clock_offset_seconds(offset: number): void {
    clock_offset_seconds = offset;
}
