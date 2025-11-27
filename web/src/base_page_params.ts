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

// These parameters are sent in #page-params for both users and spectators.
//
// Sync this with zerver.lib.home.build_page_params_for_home_page_load.
//
// TODO/typescript: Replace z.looseObject with z.object when all consumers have
// been converted to TypeScript and the schema is complete.
const home_params_schema = z.looseObject({
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
    presence_history_limit_days_for_web_app: z.number(),
    promote_sponsoring_zulip: z.boolean(),
    realm_rendered_description: z.string(),
    show_try_zulip_modal: z.boolean(),
    state_data: z.nullable(state_data_schema),
    translation_data: z.record(z.string(), z.string()),
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
        throw new Error("Missing #page_params[data-params]");
    }
    page_params_div.remove();
    return params;
}

export const page_params = page_params_schema.parse(JSON.parse(take_params()));

const t2 = performance.now();
export const page_params_parse_time = t2 - t1;
