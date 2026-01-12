// For documentation on i18n in Zulip, see:
// https://zulip.readthedocs.io/en/latest/translating/internationalization.html

import type {MessageDescriptor} from "@formatjs/intl";
import {DEFAULT_INTL_CONFIG, IntlErrorCode, createIntl, createIntlCache} from "@formatjs/intl";
import type {
    FormatXMLElementFn,
    Options as IntlMessageFormatOptions,
    PrimitiveType,
} from "intl-messageformat";
import _ from "lodash";

import {page_params} from "./fake_base_page_params.ts";

const cache = createIntlCache();
export const intl = createIntl(
    {
        locale: page_params.request_language,
        defaultLocale: "en",
        messages: "translation_data" in page_params ? page_params.translation_data : {},
        /* istanbul ignore next */
        onError(error) {
            // Ignore complaints about untranslated strings that were
            // added since the last sync-translations run.
            if (error.code !== IntlErrorCode.MISSING_TRANSLATION) {
                DEFAULT_INTL_CONFIG.onError(error);
            }
        },
    },
    cache,
);

export function $t(
    descriptor: MessageDescriptor,
    values?: Record<string, PrimitiveType | FormatXMLElementFn<string, string>>,
    opts?: IntlMessageFormatOptions,
): string {
    return intl.formatMessage(descriptor, values, opts);
}

export const default_html_elements = Object.fromEntries(
    ["b", "code", "em", "i", "kbd", "p", "strong"].map((tag) => [
        tag,
        (content_html: string[]) => `<${tag}>${content_html.join("")}</${tag}>`,
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

export let language_list: ((typeof page_params & {page_type: "home"})["language_list"][number] & {
    display_name: string;
})[];

export function get_language_name(language_code: string): string | undefined {
    return language_list.find((language) => language.code === language_code)?.name;
}

function get_language_display_name(language_code: string): string {
    // For "Monoglian" and "Bqi", "Intl.DisplayNames" returns their English names
    // in Chromium based browsers. So, we hard-code the display names for these
    // two languages.
    if (language_code === "bqi") {
        return "Bakhtiari";
    }

    if (language_code === "mn") {
        return "Монгол";
    }

    const locale = new Intl.Locale(language_code === "en" ? "en-US" : language_code);
    let language_display_name = new Intl.DisplayNames([locale], {type: "language"})
        .of(locale.language)!
        .replace(/^./u, (c) => c.toLocaleUpperCase(locale));

    if (locale.script !== undefined) {
        language_display_name += ` (${new Intl.DisplayNames([locale], {type: "script"}).of(locale.script)})`;
    }
    if (locale.region !== undefined) {
        language_display_name += ` (${new Intl.DisplayNames([locale], {type: "region"}).of(locale.region)})`;
    }
    return language_display_name;
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
                display_name: get_language_display_name(language.code),
            });
        }
    }
}

type Language = {
    code: string;
    name_with_percent: string;
    selected: boolean;
};

export function get_language_list_columns(default_language: string): Language[] {
    const formatted_list: Language[] = [];
    for (const language of language_list) {
        let name_with_percent = language.display_name;
        if (language.percent_translated !== undefined) {
            name_with_percent = `${language.display_name} (${language.percent_translated}%)`;
        }

        const selected = default_language === language.code || default_language === language.locale;
        formatted_list.push({
            code: language.code,
            name_with_percent,
            selected,
        });
    }
    return formatted_list;
}
