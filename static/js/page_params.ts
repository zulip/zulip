import $ from "jquery";

const t1 = performance.now();
export const page_params: {
    enable_desktop_notifications: boolean;
    enable_offline_email_notifications: boolean;
    enable_offline_push_notifications: boolean;
    enable_sounds: boolean;
    enable_stream_audible_notifications: boolean;
    enable_stream_desktop_notifications: boolean;
    enable_stream_email_notifications: boolean;
    enable_stream_push_notifications: boolean;
    language_list: {
        code: string;
        locale: string;
        name: string;
        percent_translated: number | undefined;
    }[];
    development_environment: boolean;
    realm_push_notifications_enabled: boolean;
    request_language: string;
    translation_data: Record<string, string>;
    wildcard_mentions_notify: boolean;
} = $("#page-params").remove().data("params");
const t2 = performance.now();
export const page_params_parse_time = t2 - t1;
if (!page_params) {
    throw new Error("Missing page-params");
}
