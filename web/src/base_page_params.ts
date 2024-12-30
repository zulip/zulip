import * as v from "valibot";

import {narrow_term_schema, state_data_schema} from "./state_data.ts";

const t1 = performance.now();

// Sync this with zerver.context_processors.zulip_default_context.
const default_params_schema = v.object({
    page_type: v.literal("default"),
    development_environment: v.boolean(),
    google_analytics_id: v.optional(v.string()),
    request_language: v.string(),
});

// These parameters are sent in #page-params for both users and spectators.
//
// Sync this with zerver.lib.home.build_page_params_for_home_page_load.
//
// TODO/typescript: Switch v.looseObject to v.object when all consumers have
// been converted to TypeScript and the schema is complete.
const home_params_schema = v.looseObject({
    ...default_params_schema.entries,
    page_type: v.literal("home"),
    apps_page_url: v.string(),
    bot_types: v.array(
        v.object({
            type_id: v.number(),
            name: v.string(),
            allowed: v.boolean(),
        }),
    ),
    corporate_enabled: v.boolean(),
    furthest_read_time: v.nullable(v.number()),
    is_spectator: v.boolean(),
    // `language_cookie_name` is only sent for spectators.
    language_cookie_name: v.optional(v.string()),
    language_list: v.array(
        v.object({
            code: v.string(),
            locale: v.string(),
            name: v.string(),
            percent_translated: v.optional(v.number()),
        }),
    ),
    login_page: v.string(),
    narrow: v.optional(v.array(narrow_term_schema)),
    narrow_stream: v.optional(v.string()),
    narrow_topic: v.optional(v.string()),
    presence_history_limit_days_for_web_app: v.number(),
    promote_sponsoring_zulip: v.boolean(),
    // `realm_rendered_description` is only sent for spectators, because
    // it isn't displayed for logged-in users and requires markdown
    // processor time to compute.
    realm_rendered_description: v.optional(v.string()),
    show_billing: v.boolean(),
    show_remote_billing: v.boolean(),
    show_plans: v.boolean(),
    show_webathena: v.boolean(),
    sponsorship_pending: v.boolean(),
    state_data: v.nullable(state_data_schema),
    translation_data: v.record(v.string(), v.string()),
});

// Sync this with analytics.views.stats.render_stats.
const stats_params_schema = v.object({
    ...default_params_schema.entries,
    page_type: v.literal("stats"),
    data_url_suffix: v.string(),
    upload_space_used: v.nullable(v.number()),
    guest_users: v.nullable(v.number()),
    translation_data: v.record(v.string(), v.string()),
});

// Sync this with corporate.views.portico.team_view.
const team_params_schema = v.object({
    ...default_params_schema.entries,
    page_type: v.literal("team"),
    contributors: v.optional(
        v.array(
            v.objectWithRest(
                {
                    avatar: v.string(),
                    github_username: v.optional(v.string()),
                    email: v.optional(v.string()),
                    name: v.optional(v.string()),
                },
                // Repository names may change or increase over time,
                // so we use this to parse the contributions of the user in
                // the given repository instead of typing every name.
                v.number(),
            ),
        ),
    ),
});

// Sync this with corporate.lib.stripe.UpgradePageParams.
const upgrade_params_schema = v.object({
    ...default_params_schema.entries,
    page_type: v.literal("upgrade"),
    annual_price: v.number(),
    demo_organization_scheduled_deletion_date: v.nullable(v.number()),
    monthly_price: v.number(),
    seat_count: v.number(),
    billing_base_url: v.string(),
    tier: v.number(),
    flat_discount: v.number(),
    flat_discounted_months: v.number(),
    fixed_price: v.nullable(v.number()),
    setup_payment_by_invoice: v.boolean(),
    free_trial_days: v.nullable(v.number()),
    percent_off_annual_price: v.nullable(v.string()),
    percent_off_monthly_price: v.nullable(v.string()),
});

const page_params_schema = v.variant("page_type", [
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
    if (page_params_div.dataset.params === undefined) {
        throw new Error("Missing #page_params[data-params]");
    }
    page_params_div.remove();
    return page_params_div.dataset.params;
}

export const page_params = v.parse(page_params_schema, JSON.parse(take_params()));

const t2 = performance.now();
export const page_params_parse_time = t2 - t1;
