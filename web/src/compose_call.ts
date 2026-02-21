import {realm} from "./state_data.ts";

export const zoom_token_callbacks = new Map();
export const call_xhrs = new Map<string, JQuery.jqXHR<unknown>>();
export const ignored_call_xhrs = new Set<JQuery.jqXHR>();

export function get_jitsi_server_url(video_call_id?: string): URL | null {
    const base_url = realm.realm_jitsi_server_url ?? realm.server_jitsi_server_url;
    if (!base_url) {
        return null;
    }
    const url = new URL(base_url);
    if (video_call_id !== undefined) {
        url.pathname = `/${video_call_id}`;
    }
    return url;
}

export function abort_video_callbacks(edit_message_id = ""): void {
    zoom_token_callbacks.delete(edit_message_id);
    const xhr = call_xhrs.get(edit_message_id);
    if (xhr !== undefined) {
        // TODO: Use xhr.abort(), if XHR methods are available
        // after https://github.com/getsentry/sentry-javascript/issues/19242
        // gets resolved.
        ignored_call_xhrs.add(xhr);
        call_xhrs.delete(edit_message_id);
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
        (realm.realm_video_chat_provider === available_providers.jitsi_meet?.id &&
            get_jitsi_server_url() !== null) ||
        realm.realm_video_chat_provider === available_providers.zoom?.id ||
        realm.realm_video_chat_provider === available_providers.big_blue_button?.id ||
        realm.realm_video_chat_provider === available_providers.zoom_server_to_server?.id
    ) {
        return true;
    }
    return false;
}
