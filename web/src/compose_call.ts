import {realm} from "./state_data.ts";

const call_xhrs = new Map<string, JQuery.jqXHR<unknown>[]>();
export const ignored_call_xhrs = new Set<JQuery.jqXHR>();

export type OAuthCallProvider = "zoom";
const oauth_providers = new Set<OAuthCallProvider>(["zoom"]);

export const oauth_call_provider_token_callbacks = new Map<
    OAuthCallProvider,
    Map<string, () => void>
>();

export function current_oauth_call_provider(): OAuthCallProvider | null {
    const available_providers = realm.realm_available_video_chat_providers;
    const realm_provider = realm.realm_video_chat_provider;
    if (
        realm_provider === available_providers.zoom?.id ||
        realm_provider === available_providers.zoom_server_to_server?.id
    ) {
        return "zoom";
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

export function track_xhr_for_key(key: string, xhr: JQuery.jqXHR): void {
    const existing_xhrs = call_xhrs.get(key);
    if (existing_xhrs) {
        existing_xhrs.push(xhr);
    } else {
        call_xhrs.set(key, [xhr]);
    }
}

// This abandons any OAuth completion callbacks as well as XHR related callbacks
// by "aborting" the XHRs associated with a message textarea identified by the id.
export function abandon_all_callbacks_for_key(key: string): void {
    for (const provider of oauth_providers) {
        abandon_oauth_provider_token_callbacks_for_key(provider, key);
    }
    abandon_pending_xhrs_for_key(key);
}

function abandon_pending_xhrs_for_key(key: string): void {
    const existing_xhrs = call_xhrs.get(key);
    if (existing_xhrs === undefined) {
        return;
    }
    for (const xhr of existing_xhrs) {
        // TODO: Use xhr.abort(), if XHR methods are available
        // after https://github.com/getsentry/sentry-javascript/issues/19242
        // gets resolved.
        ignored_call_xhrs.add(xhr);
    }
    call_xhrs.delete(key);
}

export function update_oauth_provider_callback_for_key(
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

function abandon_oauth_provider_token_callbacks_for_key(
    provider: OAuthCallProvider,
    key: string,
): void {
    const provider_callbacks = oauth_call_provider_token_callbacks.get(provider);
    if (provider_callbacks === undefined || provider_callbacks.size === 0) {
        return;
    }
    provider_callbacks.delete(key);
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
