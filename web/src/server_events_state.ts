import type {StateData} from "./state_data";

export let queue_id: string | null;
export let assert_get_events_running: (error_message: string) => void;
export let restart_get_events: () => void;

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
