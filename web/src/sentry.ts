import * as Sentry from "@sentry/browser";
import * as v from "valibot";

type UserInfo = {
    id?: string;
    realm: string;
    role?: string;
};

const sentry_params_schema = v.object({
    dsn: v.string(),
    environment: v.string(),
    realm_key: v.string(),
    sample_rate: v.number(),
    server_version: v.string(),
    trace_rate: v.number(),
    user: v.optional(v.object({id: v.number(), role: v.string()})),
});

const sentry_params_json =
    window.document?.querySelector("script#sentry-params")?.textContent ?? undefined;
const sentry_params =
    sentry_params_json === undefined
        ? undefined
        : v.parse(sentry_params_schema, JSON.parse(sentry_params_json));

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
    return parsed.pathname !== "/json/events";
}

if (sentry_params !== undefined) {
    const sample_rates = new Map([
        // This is controlled by shouldCreateSpanForRequest, above, but also put here for consistency
        ["call GET /json/events", 0],
        // These requests are high-volume and do not add much data
        ["call POST /json/users/me/presence", 0.01],
        ["call POST /json/typing", 0.05],
    ]);

    Sentry.init({
        dsn: sentry_params.dsn,
        environment: sentry_params.environment,
        tunnel: "/error_tracing",

        release: "zulip-server@" + ZULIP_VERSION,
        integrations: [
            Sentry.browserTracingIntegration({
                instrumentNavigation: false,
                beforeStartSpan(context) {
                    return {
                        ...context,
                        metadata: {source: "custom"},
                        name: normalize_path(
                            window.location.pathname,
                            sentry_params.realm_key === "www",
                        ),
                    };
                },
                shouldCreateSpanForRequest,
            }),
        ],
        sampleRate: sentry_params.sample_rate,
        tracesSampler(samplingContext) {
            const base_rate = sentry_params.trace_rate;
            const name = samplingContext.name;
            return base_rate * (sample_rates.get(name) ?? 1);
        },
        initialScope(scope) {
            const user_role = sentry_params.user?.role ?? "Logged out";
            const user_info: UserInfo = {
                realm: sentry_params.realm_key,
                role: user_role,
            };
            if (sentry_params.user !== undefined) {
                user_info.id = sentry_params.user.id.toString();
            }
            scope.setTags({
                realm: sentry_params.realm_key,
                server_version: sentry_params.server_version,
                user_role,
            });
            scope.setUser(user_info);
            return scope;
        },
    });
} else {
    Sentry.init({});
}
