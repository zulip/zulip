import {realm} from "./state_data.ts";

export type OAuthCallProvider = "zoom" | "webex";

export function current_oauth_call_provider(): OAuthCallProvider | null {
    const available_providers = realm.realm_available_video_chat_providers;
    const realm_provider = realm.realm_video_chat_provider;
    if (
        realm_provider === available_providers.zoom?.id ||
        realm_provider === available_providers.zoom_server_to_server?.id
    ) {
        return "zoom";
    }
    if (realm_provider === available_providers.webex?.id) {
        return "webex";
    }
    return null;
}

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
