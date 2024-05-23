import {realm} from "./state_data";

export const zoom_token_callbacks = new Map();
export const video_call_xhrs = new Map<string, JQuery.jqXHR<unknown>>();

export function get_jitsi_server_url(): string | null {
    return realm.realm_jitsi_server_url ?? realm.server_jitsi_server_url;
}

export function abort_video_callbacks(edit_message_id = ""): void {
    zoom_token_callbacks.delete(edit_message_id);
    const xhr = video_call_xhrs.get(edit_message_id);
    if (xhr !== undefined) {
        xhr.abort();
        video_call_xhrs.delete(edit_message_id);
    }
}

export function compute_show_video_chat_button(): boolean {
    const available_providers = realm.realm_available_video_chat_providers;
    if (realm.realm_video_chat_provider === available_providers.disabled.id) {
        return false;
    }

    if (
        realm.realm_video_chat_provider === available_providers.jitsi_meet.id &&
        !get_jitsi_server_url()
    ) {
        return false;
    }

    return true;
}

export function compute_show_audio_chat_button(): boolean {
    const available_providers = realm.realm_available_video_chat_providers;
    if (
        (available_providers.jitsi_meet &&
            get_jitsi_server_url() !== null &&
            realm.realm_video_chat_provider === available_providers.jitsi_meet.id) ||
        (available_providers.zoom &&
            realm.realm_video_chat_provider === available_providers.zoom.id)
    ) {
        return true;
    }
    return false;
}
