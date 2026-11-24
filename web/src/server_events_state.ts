import type {StateData} from "./state_data";

export let queue_id: string | null;
export let assert_get_events_running: (error_message: string) => void;
export let restart_get_events: () => void;

// True once the events from at least one successful /json/events
// response have been applied since this page's queue was created.
// Until then, the people store may legitimately lack users that exist
// server-side but were created after the /register snapshot's
// last_event_id; report_late_add uses this to demote "Added user late"
// from blueslip.error to a log.
let first_events_response_applied = false;

export function has_applied_first_events_response(): boolean {
    return first_events_response_applied;
}

export function mark_first_events_response_applied(): void {
    first_events_response_applied = true;
}

export function clear_for_testing(): void {
    first_events_response_applied = false;
}

export function initialize(
    params: StateData["server_events_state"] & {
        assert_get_events_running: (error_message: string) => void;
        restart_get_events: () => void;
    },
): void {
    queue_id = params.queue_id;
    assert_get_events_running = params.assert_get_events_running;
    restart_get_events = params.restart_get_events;
}
