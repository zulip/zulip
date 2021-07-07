import $ from "jquery";

const t1 = performance.now();
export const page_params: {
    language_list: {
        code: string;
        locale: string;
        name: string;
        percent_translated: number | undefined;
    }[];
    development_environment: boolean;
    request_language: string;
    translation_data: Record<string, string>;
} = $("#page-params").remove().data("params");
const t2 = performance.now();
export const page_params_parse_time = t2 - t1;
if (!page_params) {
    throw new Error("Missing page-params");
}
