import * as Sentry from "@sentry/browser";
import _ from "lodash";

import {page_params} from "./page_params";

type UserInfo = {
    id?: string;
    realm: string;
    role?: string;
};

export function normalize_path(path: string, is_portico = false): string {
    if (path === undefined) {
        return "unknown";
    }
    path = path
        .replace(/\/\d+(\/|$)/, "/*$1")
        .replace(
            /^\/(join|reactivate|new|accounts\/do_confirm|accounts\/confirm_new_email)\/[^/]+(\/?)$/,
            "$1/*$2",
        );
    if (is_portico) {
        return "portico: " + path;
    }
    return path;
}

export function shouldCreateSpanForRequest(url: string): boolean {
    const parsed = new URL(url, window.location.href);
    return !["/json/events", "/json/users/me/presence"].includes(parsed.pathname);
}

if (page_params.server_sentry_dsn) {
    const url_matches = [/^\//, new RegExp("^" + _.escapeRegExp(page_params.webpack_public_path))];
    if (page_params.realm_uri !== undefined) {
        url_matches.push(new RegExp("^" + _.escapeRegExp(page_params.realm_uri) + "/"));
    }
    const sentry_key =
        // No parameter is the portico pages, empty string is the empty realm
        page_params.realm_sentry_key === undefined
            ? "www"
            : page_params.realm_sentry_key === ""
            ? "(root)"
            : page_params.realm_sentry_key;
    const user_info: UserInfo = {
        realm: sentry_key,
    };
    if (sentry_key !== "www") {
        user_info.role = page_params.is_owner
            ? "Organization owner"
            : page_params.is_admin
            ? "Organization administrator"
            : page_params.is_moderator
            ? "Moderator"
            : page_params.is_guest
            ? "Guest"
            : page_params.is_spectator
            ? "Spectator"
            : page_params.user_id
            ? "Member"
            : "Logged out";
        if (page_params.user_id) {
            user_info.id = page_params.user_id.toString();
        }
    }

    Sentry.init({
        dsn: page_params.server_sentry_dsn,
        environment: page_params.server_sentry_environment ?? "development",
        tunnel: "/error_tracing",

        release: "zulip-server@" + ZULIP_VERSION,
        integrations: [
            new Sentry.BrowserTracing({
                tracePropagationTargets: url_matches,
                startTransactionOnLocationChange: false,
                beforeNavigate(context) {
                    return {
                        ...context,
                        metadata: {source: "custom"},
                        name: normalize_path(location.pathname, sentry_key === "www"),
                    };
                },
                shouldCreateSpanForRequest,
            }),
        ],
        allowUrls: url_matches,
        sampleRate: page_params.server_sentry_sample_rate ?? 0,
        tracesSampleRate: page_params.server_sentry_trace_rate ?? 0,
        initialScope: {
            tags: {
                realm: sentry_key,
                user_role: user_info.role ?? "Browser",
                server_version: page_params.zulip_version,
            },
            user: user_info,
        },
    });
} else {
    // Always add the tracing extensions, so Sentry doesn't throw runtime errors if one calls
    // startTransaction without having created the Sentry.BrowserTracing object.
    Sentry.addTracingExtensions();
    Sentry.init({});
}
