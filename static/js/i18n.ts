// For documentation on i18n in Zulip, see:
// https://zulip.readthedocs.io/en/latest/translating/internationalization.html

import type {MessageDescriptor} from "@formatjs/intl";
import {DEFAULT_INTL_CONFIG, IntlErrorCode, createIntl, createIntlCache} from "@formatjs/intl";
import type {FormatXMLElementFn, PrimitiveType} from "intl-messageformat";
import _ from "lodash";

import {page_params} from "./page_params";

const cache = createIntlCache();
export const intl = createIntl(
    {
        locale: page_params.request_language,
        defaultLocale: "en",
        messages: page_params.translation_data,
        onError: /* istanbul ignore next */ (error) => {
            // Ignore complaints about untranslated strings that were
            // added since the last sync-translations run.
            if (error.code !== IntlErrorCode.MISSING_TRANSLATION) {
                DEFAULT_INTL_CONFIG.onError(error);
            }
        },
    },
    cache,
);

export const $t = intl.formatMessage.bind(intl);

export const default_html_elements = Object.fromEntries(
    ["b", "code", "em", "i", "kbd", "p", "strong"].map((tag) => [
        tag,
        (content_html: string) => `<${tag}>${content_html}</${tag}>`,
    ]),
);

export function $t_html(
    descriptor: MessageDescriptor,
    values?: Record<string, PrimitiveType | FormatXMLElementFn<string, string>>,
): string {
    return intl.formatMessage(descriptor, {
        ...default_html_elements,
        ...Object.fromEntries(
            Object.entries(values ?? {}).map(([key, value]) => [
                key,
                typeof value === "function" ? value : _.escape(value?.toString()),
            ]),
        ),
    });
}

export let language_list: typeof page_params["language_list"];

export function get_language_name(language_code: string): string {
    const language_list_map: Record<string, string> = {};

    // One-to-one mapping from code to name for all languages
    for (const language of language_list) {
        language_list_map[language.code] = language.name;
    }
    return language_list_map[language_code];
}

export function initialize(language_params: {language_list: typeof language_list}): void {
    const language_list_raw = language_params.language_list;

    // Limit offered languages to options with percentage translation >= 5%
    language_list = [];
    for (const language of language_list_raw) {
        if (language.percent_translated === undefined || language.percent_translated >= 5) {
            language_list.push({
                code: language.code,
                locale: language.locale,
                name: language.name,
                percent_translated: language.percent_translated,
            });
        }
    }
}

// This formats language data for the language selection modal in a
// 2-column format.
type LanguageListColumn = {
    [prop in "first" | "second"]?: {
        code: string;
        name: string;
        name_with_percent: string;
        selected: boolean;
    };
};

export function get_language_list_columns(default_language: string): LanguageListColumn[] {
    const formatted_list: LanguageListColumn[] = [];
    const language_len = language_list.length;
    const firsts_end = Math.floor(language_len / 2) + (language_len % 2);
    const firsts = _.range(0, firsts_end);
    const seconds = _.range(firsts_end, language_len);
    const longest_zip: [number, number][] = [];

    // Create a zip (itertool.zip_longest in python)
    for (const value of firsts) {
        longest_zip.push([value, seconds[value]]);
    }

    for (const row of longest_zip) {
        const item: LanguageListColumn = {};
        const zip_row = [
            ["first", row[0]],
            ["second", row[1]],
        ] as const;
        for (const zip_value of zip_row) {
            if (zip_value[1] !== undefined) {
                const lang = language_list[zip_value[1]];
                const name = lang.name;
                let name_with_percent = name;
                if (lang.percent_translated !== undefined) {
                    name_with_percent = `${name} (${lang.percent_translated}%)`;
                }

                let selected = false;

                if (default_language === lang.code || default_language === lang.locale) {
                    selected = true;
                }

                item[zip_value[0]] = {
                    name,
                    code: lang.code,
                    name_with_percent,
                    selected,
                };
            }
        }

        formatted_list.push(item);
    }
    return formatted_list;
}
