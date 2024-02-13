import $ from "jquery";

import type {Term} from "./filter";

const t1 = performance.now();
export const page_params: {
    apps_page_url: string;
    bot_types: {
        type_id: number;
        name: string;
        allowed: boolean;
    }[];
    corporate_enabled: boolean;
    development_environment: boolean;
    furthest_read_time: number | null;
    is_spectator: boolean;
    language_list: {
        code: string;
        locale: string;
        name: string;
        percent_translated?: number;
    }[];
    login_page: string;
    max_message_id: number;
    narrow?: Term[];
    narrow_stream?: string;
    needs_tutorial: boolean;
    promote_sponsoring_zulip: boolean;
    realm_sentry_key?: string;
    request_language: string;
    server_sentry_dsn: string | null;
    server_sentry_environment?: string;
    server_sentry_sample_rate?: number;
    server_sentry_trace_rate?: number;
    show_billing: boolean;
    show_plans: boolean;
    show_webathena: boolean;
    sponsorship_pending: boolean;
    translation_data: Record<string, string>;
} = $("#page-params").remove().data("params");
const t2 = performance.now();
export const page_params_parse_time = t2 - t1;
if (!page_params) {
    throw new Error("Missing page-params");
}
