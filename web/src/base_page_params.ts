import $ from "jquery";
import {z} from "zod";

import {narrow_term_schema, state_data_schema} from "./state_data";

const t1 = performance.now();

// Sync this with zerver.context_processors.zulip_default_context.
const default_params_schema = z.object({
    page_type: z.literal("default"),
    development_environment: z.boolean(),
    google_analytics_id: z.optional(z.string()),
    realm_sentry_key: z.optional(z.string()),
    request_language: z.string(),
    server_sentry_dsn: z.nullable(z.string()),
    server_sentry_environment: z.optional(z.string()),
    server_sentry_sample_rate: z.optional(z.number()),
    server_sentry_trace_rate: z.optional(z.number()),
});

// These parameters are sent in #page-params for both users and spectators.
//
// Sync this with zerver.lib.home.build_page_params_for_home_page_load.
const home_params_schema = default_params_schema
    .extend({
        page_type: z.literal("home"),
        apps_page_url: z.string(),
        bot_types: z.array(
            z.object({
                type_id: z.number(),
                name: z.string(),
                allowed: z.boolean(),
            }),
        ),
        corporate_enabled: z.boolean(),
        furthest_read_time: z.nullable(z.number()),
        is_spectator: z.boolean(),
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
        needs_tutorial: z.boolean(),
        promote_sponsoring_zulip: z.boolean(),
        // `realm_rendered_description` is only sent for spectators, because
        // it isn't displayed for logged-in users and requires markdown
        // processor time to compute.
        realm_rendered_description: z.optional(z.string()),
        show_billing: z.boolean(),
        show_plans: z.boolean(),
        show_webathena: z.boolean(),
        sponsorship_pending: z.boolean(),
        state_data: state_data_schema.nullable(),
        translation_data: z.record(z.string()),
    })
    // TODO/typescript: Remove .passthrough() when all consumers have been
    // converted to TypeScript and the schema is complete.
    .passthrough();

// Sync this with analytics.views.stats.render_stats.
const stats_params_schema = default_params_schema.extend({
    page_type: z.literal("stats"),
    data_url_suffix: z.string(),
    upload_space_used: z.nullable(z.number()),
    guest_users: z.nullable(z.number()),
    translation_data: z.record(z.string()),
});

// Sync this with corporate.views.portico.team_view.
const team_params_schema = default_params_schema.extend({
    page_type: z.literal("team"),
    contributors: z.unknown(),
});

// Sync this with corporate.lib.stripe.UpgradePageParams.
const upgrade_params_schema = default_params_schema.extend({
    page_type: z.literal("upgrade"),
    annual_price: z.number(),
    demo_organization_scheduled_deletion_date: z.nullable(z.number()),
    monthly_price: z.number(),
    seat_count: z.number(),
    billing_base_url: z.string(),
    tier: z.number(),
    flat_discount: z.number(),
    flat_discounted_months: z.number(),
    fixed_price: z.number().nullable(),
    setup_payment_by_invoice: z.boolean(),
    free_trial_days: z.nullable(z.number()),
});

const page_params_schema = z.discriminatedUnion("page_type", [
    default_params_schema,
    home_params_schema,
    stats_params_schema,
    team_params_schema,
    upgrade_params_schema,
]);

export const page_params = page_params_schema.parse($("#page-params").remove().data("params"));

const t2 = performance.now();
export const page_params_parse_time = t2 - t1;
