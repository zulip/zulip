import {realm} from "./state_data.ts";

export type OAuthCallProvider = "zoom";
export const oauth_call_provider_token_callbacks = new Map<
    OAuthCallProvider,
    Map<string, () => void>
>();
export const oauth_call_xhrs = new Map<string, JQuery.jqXHR<unknown>>();

export function current_oauth_call_provider(): OAuthCallProvider | null {
    const available_providers = realm.realm_available_video_chat_providers;
    const realm_provider = realm.realm_video_chat_provider;
    if (realm_provider === available_providers.zoom?.id) {
        return "zoom";
    }
    if (realm_provider === available_providers.zoom_server_to_server?.id) {
        return "zoom";
    }
    return null;
}

export function get_jitsi_server_url(): string | null {
    return realm.realm_jitsi_server_url ?? realm.server_jitsi_server_url;
}

export function update_provider_callback_for_key(
    provider: OAuthCallProvider,
    key: string,
    callback: () => void,
): void {
    let provider_callbacks = oauth_call_provider_token_callbacks.get(provider);

    if (provider_callbacks === undefined) {
        provider_callbacks = new Map<string, () => void>();
        oauth_call_provider_token_callbacks.set(provider, provider_callbacks);
    }

    provider_callbacks.set(key, callback);
}

export function abort_video_callbacks(
    provider: OAuthCallProvider,
    edit_message_id = "",
): void {
    const provider_callbacks = oauth_call_provider_token_callbacks.get(provider);
    if(provider_callbacks === undefined)return;
    provider_callbacks.delete(edit_message_id);
    const xhr = oauth_call_xhrs.get(edit_message_id);
    if (xhr !== undefined) {
        xhr.abort();
        oauth_call_xhrs.delete(edit_message_id);
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
