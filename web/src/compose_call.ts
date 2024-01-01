import {state_data} from "./state_data";

export const zoom_token_callbacks = new Map();
export const video_call_xhrs = new Map();

export function get_jitsi_server_url(): string | null {
    return state_data.realm_jitsi_server_url ?? state_data.server_jitsi_server_url;
}

export function abort_video_callbacks(edit_message_id = ""): void {
    zoom_token_callbacks.delete(edit_message_id);
    if (video_call_xhrs.has(edit_message_id)) {
        video_call_xhrs.get(edit_message_id).abort();
        video_call_xhrs.delete(edit_message_id);
    }
}

export function compute_show_video_chat_button(): boolean {
    const available_providers = state_data.realm_available_video_chat_providers;
    if (state_data.realm_video_chat_provider === available_providers.disabled.id) {
        return false;
    }

    if (
        state_data.realm_video_chat_provider === available_providers.jitsi_meet.id &&
        !get_jitsi_server_url()
    ) {
        return false;
    }

    return true;
}

export function compute_show_audio_chat_button(): boolean {
    const available_providers = state_data.realm_available_video_chat_providers;
    if (
        (available_providers.jitsi_meet &&
            get_jitsi_server_url() !== null &&
            state_data.realm_video_chat_provider === available_providers.jitsi_meet.id) ||
        (available_providers.zoom &&
            state_data.realm_video_chat_provider === available_providers.zoom.id)
    ) {
        return true;
    }
    return false;
}
