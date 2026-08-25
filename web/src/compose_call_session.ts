import {type OAuthCallProvider} from "./compose_call.ts";

// A ComposeCallSession manages the XHR and OAuth flow callbacks
// for a message textarea.
class ComposeCallSession {
    oauth_token_callbacks: Map<OAuthCallProvider, () => void>;
    pending_xhrs: Set<JQuery.jqXHR<unknown>>;

    constructor() {
        this.oauth_token_callbacks = new Map<OAuthCallProvider, () => void>();
        this.pending_xhrs = new Set();
    }

    append_pending_xhr(xhr: JQuery.jqXHR<unknown>): void {
        this.pending_xhrs.add(xhr);
    }

    add_oauth_token_callback(provider: OAuthCallProvider, callback: () => void): void {
        this.oauth_token_callbacks.set(provider, callback);
    }

    abort_pending_xhr(xhr: JQuery.jqXHR<unknown>): void {
        // TODO: Use xhr.abort(), if XHR methods are available
        // after https://github.com/getsentry/sentry-javascript/issues/19242
        // gets resolved.
        this.pending_xhrs.delete(xhr);
    }

    // This abandons any OAuth completion callbacks as well as XHR related callbacks
    // by "aborting" the XHRs associated with a message textarea.
    abandon_everything(): void {
        this.pending_xhrs.clear();
        this.oauth_token_callbacks.clear();
    }

    maybe_run_xhr_callback(xhr: JQuery.jqXHR<unknown> | undefined, callback: () => void): void {
        if (xhr === undefined) {
            return;
        }
        if (this.pending_xhrs.has(xhr)) {
            callback();
            this.pending_xhrs.delete(xhr);
        }
    }

    run_and_delete_callback_for_provider(provider: OAuthCallProvider): void {
        const callback = this.oauth_token_callbacks.get(provider);
        if (callback) {
            callback();
        }
        this.oauth_token_callbacks.delete(provider);
    }
}

class ComposeCallSessionManager {
    stored_call_sessions = new Map<string, ComposeCallSession>();

    get_compose_call_session(key: string): ComposeCallSession {
        const existing_call_session = this.stored_call_sessions.get(key);
        if (existing_call_session) {
            return existing_call_session;
        }
        const compose_call_session = new ComposeCallSession();
        this.stored_call_sessions.set(key, compose_call_session);
        return compose_call_session;
    }

    run_and_clear_callbacks_for_provider(provider: OAuthCallProvider): void {
        for (const session of this.stored_call_sessions.values()) {
            session.run_and_delete_callback_for_provider(provider);
        }
    }

    abandon_session(key: string): void {
        const session = this.stored_call_sessions.get(key);
        if (session) {
            session.abandon_everything();
            this.stored_call_sessions.delete(key);
        }
    }
}

export const compose_call_session_manager = new ComposeCallSessionManager();
