// For documentation on i18n in Zulip, see:
// https://zulip.readthedocs.io/en/latest/translating/internationalization.html

import {DEFAULT_INTL_CONFIG, IntlErrorCode, createIntl, createIntlCache} from "@formatjs/intl";
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

export const $t = intl.formatMessage;

export const default_html_elements = Object.fromEntries(
    ["b", "code", "em", "i", "kbd", "p", "strong"].map((tag) => [
        tag,
        (content_html) => `<${tag}>${content_html}</${tag}>`,
    ]),
);

export function $t_html(descriptor, values) {
    return intl.formatMessage(descriptor, {
        ...default_html_elements,
        ...Object.fromEntries(
            Object.entries(values ?? {}).map(([key, value]) => [
                key,
                typeof value === "function" ? value : _.escape(value),
            ]),
        ),
    });
}

// This formats language data for the language selection modal in a
// 2-column format.
export function get_language_list_columns(default_language) {
    const language_list = [];

    // Only render languages with percentage translation >= 5%
    for (const language of page_params.language_list) {
        if (language.percent_translated === undefined || language.percent_translated >= 5) {
            language_list.push({
                code: language.code,
                locale: language.locale,
                name: language.name,
                percent_translated: language.percent_translated,
            });
        }
    }

    const formatted_list = [];
    const language_len = language_list.length;
    const firsts_end = Math.floor(language_len / 2) + (language_len % 2);
    const firsts = _.range(0, firsts_end);
    const seconds = _.range(firsts_end, language_len);

    const longest_zip = [];

    // Create a zip (itertool.zip_longest in python)
    for (const value of firsts) {
        longest_zip.push([value, seconds[value]]);
    }

    for (const row of longest_zip) {
        const item = {};
        const zip_row = [
            ["first", row[0]],
            ["second", row[1]],
        ];
        for (const zip_value of zip_row) {
            if (zip_value[1] !== undefined) {
                const lang = language_list[zip_value[1]];
                const name = lang.name;
                let name_with_percent = name;
                if (lang.percent_translated !== undefined) {
                    name_with_percent = name + " (" + lang.percent_translated + "%)";
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
