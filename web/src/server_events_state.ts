import type {StateData} from "./state_data";

export let queue_id: string | null;
export let assert_get_events_running: (error_message: string) => void;
export let restart_get_events: () => void;

// True once /json/events has successfully returned at least once
// since this page's queue was created. Until then, the people store
// may legitimately lack users that exist server-side but were created
// after the /register snapshot's last_event_id; report_late_add uses
// this to demote "Added user late" from blueslip.error to a log.
let first_events_response_received = false;

export function has_received_first_events_response(): boolean {
    return first_events_response_received;
}

export function mark_first_events_response_received(): void {
    first_events_response_received = true;
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
