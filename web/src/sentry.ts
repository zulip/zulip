import * as Sentry from "@sentry/browser";
import $ from "jquery";
import _ from "lodash";

import * as sentry_util from "./sentry_util";

const page_params: {
    is_admin: boolean;
    is_guest: boolean;
    is_moderator: boolean;
    is_owner: boolean;
    is_spectator: boolean;
    realm_sentry_key: string | undefined;
    realm_uri: string;
    server_sentry_dsn: string | undefined;
    server_sentry_environment: string | undefined;
    server_sentry_sample_rate: number | undefined;
    server_sentry_trace_rate: number | undefined;
    user_id: number | undefined;
    zulip_version: string;
} = $("#page-params").data("params");

type UserInfo = {
    id?: string;
    realm: string;
    role?: string;
};

if (page_params.server_sentry_dsn) {
    const url_matches = [/^\//];
    if (document.currentScript instanceof HTMLScriptElement) {
        url_matches.push(
            new RegExp("^" + _.escapeRegExp(new URL(".", document.currentScript.src).href)),
        );
    }
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

    const sample_rates = new Map([
        // This is controlled by shouldCreateSpanForRequest, above, but also put here for consistency
        ["call GET /json/events", 0],
        // These requests are high-volume and do not add much data
        ["call POST /json/users/me/presence", 0.01],
        ["call POST /json/typing", 0.05],
    ]);

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
                        name: sentry_util.normalize_path(location.pathname, sentry_key === "www"),
                    };
                },
                shouldCreateSpanForRequest: sentry_util.shouldCreateSpanForRequest,
            }),
        ],
        allowUrls: url_matches,
        sampleRate: page_params.server_sentry_sample_rate ?? 0,
        tracesSampler(samplingContext) {
            const base_rate = page_params.server_sentry_trace_rate ?? 0;
            const name = samplingContext.transactionContext.name;
            return base_rate * (sample_rates.get(name) ?? 1);
        },
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
