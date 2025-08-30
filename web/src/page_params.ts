import assert from "minimalistic-assert";
import {page_params as base_page_params} from "./base_page_params.ts";

assert(base_page_params.page_type === "home");

interface LanguageInfo {
    name: string;
    percent_translated: number;
    code: string;
}

interface PageParams {
    default_language: string;
    page_type: "home";
    all_languages?: Record<string, LanguageInfo>;
    // add other fields here as needed
}

// Export with narrowed type
export const page_params: PageParams = base_page_params as PageParams;
