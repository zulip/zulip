import * as z from "zod/mini";

import {narrow_term_schema, state_data_schema} from "./state_data.ts";

const t1 = performance.now();

// Sync this with zerver.context_processors.zulip_default_context.
const default_params_schema = z.object({
    page_type: z.literal("default"),
    development_environment: z.boolean(),
    google_analytics_id: z.optional(z.string()),
    request_language: z.string(),
});
// Sync this with zerver.context_processors.login_context.
const login_page_params_schema = z.object({
    ...default_params_schema.shape,
    page_type: z.literal("login"),
    realm_default_emojiset: z.string(),
});

// These parameters are sent in #page-params for both users and spectators.
//
// Sync this with zerver.lib.home.build_page_params_for_home_page_load.
//
const home_params_schema = z.object({
    ...default_params_schema.shape,
    page_type: z.literal("home"),
    apps_page_url: z.string(),
    corporate_enabled: z.boolean(),
    embedded_bots_enabled: z.boolean(),
    furthest_read_time: z.nullable(z.number()),
    insecure_desktop_app: z.boolean(),
    is_node_test: z.optional(z.literal(true)),
    is_spectator: z.boolean(),
    // `language_cookie_name` is only sent for spectators.
    language_cookie_name: z.optional(z.string()),
    language_list: z.array(
        z.object({
            code: z.string(),
            locale: z.string(),
            name: z.string(),
            percent_translated: z.optional(z.number()),
        }),
    ),
    login_page: z.string(),
    narrow: z.optional(z.array(narrow_term_schema)),
    narrow_stream: z.optional(z.string()),
    narrow_topic: z.optional(z.string()),
    no_event_queue: z.boolean(),
    presence_history_limit_days_for_web_app: z.number(),
    promote_sponsoring_zulip: z.boolean(),
    realm_rendered_description: z.string(),
    show_try_zulip_modal: z.boolean(),
    state_data: z.nullable(state_data_schema),
    test_suite: z.boolean(),
    translation_data: z.record(z.string(), z.string()),
    two_fa_enabled: z.boolean(),
    two_fa_enabled_user: z.boolean(),
    warn_no_email: z.boolean(),
});

// Sync this with analytics.views.stats.render_stats.
const stats_params_schema = z.object({
    ...default_params_schema.shape,
    page_type: z.literal("stats"),
    data_url_suffix: z.string(),
    upload_space_used: z.nullable(z.number()),
    guest_users: z.nullable(z.number()),
    translation_data: z.record(z.string(), z.string()),
});

// Sync this with corporate.views.portico.team_view.
const team_params_schema = z.object({
    ...default_params_schema.shape,
    page_type: z.literal("team"),
    contributors: z.optional(
        z.array(
            z.catchall(
                z.object({
                    avatar: z.string(),
                    github_username: z.optional(z.string()),
                    email: z.optional(z.string()),
                    name: z.optional(z.string()),
                }),
                // Repository names may change or increase over time,
                // so we use this to parse the contributions of the user in
                // the given repository instead of typing every name.
                z.number(),
            ),
        ),
    ),
});

// Sync this with corporate.lib.stripe.UpgradePageParams.
const upgrade_params_schema = z.object({
    ...default_params_schema.shape,
    page_type: z.literal("upgrade"),
    annual_price: z.number(),
    monthly_price: z.number(),
    seat_count: z.number(),
    billing_base_url: z.string(),
    tier: z.number(),
    flat_discount: z.number(),
    flat_discounted_months: z.number(),
    fixed_price: z.nullable(z.number()),
    setup_payment_by_invoice: z.boolean(),
    free_trial_days: z.nullable(z.number()),
    percent_off_annual_price: z.nullable(z.string()),
    percent_off_monthly_price: z.nullable(z.string()),
});

const page_params_schema = z.discriminatedUnion("page_type", [
    default_params_schema,
    login_page_params_schema,
    home_params_schema,
    stats_params_schema,
    team_params_schema,
    upgrade_params_schema,
]);

function take_params(): string {
    const page_params_div = document.querySelector<HTMLElement>("#page-params");
    if (page_params_div === null) {
        throw new Error("Missing #page-params");
    }

    const params = page_params_div.getAttribute("data-params");
    if (params === null) {
        // The div exists but data-params was already consumed.  This
        // happens when Firefox restores a background tab from a cached
        // DOM state (e.g. after tab discarding or BFCache restoration),
        // since we remove the attribute below after extracting it.
        //
        // Force a single server reload to get fresh page params;
        // sessionStorage persists across the reload so we can detect
        // the second attempt and stop.  If sessionStorage is
        // unavailable (crawlers, private browsing edge cases), we skip
        // the reload to avoid a potential infinite loop and let the
        // user reload manually.
        try {
            if (sessionStorage.getItem("reload_for_tab_restore") === null) {
                sessionStorage.setItem("reload_for_tab_restore", "1");
                window.location.reload();
            }
        } catch {
            // sessionStorage unavailable; fall through to throw.
        }
        throw new Error("Missing #page-params data after tab restore");
    }

    // Clear the reload guard on a successful load so it's ready
    // for the next tab-restore event.
    try {
        sessionStorage.removeItem("reload_for_tab_restore");
    } catch {
        // Ignore; the stale flag just means the next tab-restore
        // won't auto-reload, which is the safe default.
    }

    // Remove the attribute to free the (potentially multi-megabyte)
    // JSON string from the DOM, but keep the div as a sentinel so
    // we can distinguish tab-restore from a truly missing element.
    page_params_div.removeAttribute("data-params");
    return params;
}

export const page_params = page_params_schema.parse(JSON.parse(take_params()));

const t2 = performance.now();
export const page_params_parse_time = t2 - t1;
