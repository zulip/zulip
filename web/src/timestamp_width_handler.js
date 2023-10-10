import * as timerender from "./timerender";
import {user_settings} from "./user_settings";

const maxlength_all_lang = {
    "id": { "length_12hr": 8, "length_24hr": 5, "name": "Bahasa Indonesia" },
    "en-GB": { "length_12hr": 8, "length_24hr": 5, "name": "British English" },
    "ca": { "length_12hr": 11, "length_24hr": 5, "name": "Català" },
    "cs": { "length_12hr": 10, "length_24hr": 5, "name": "česky" },
    "zh-TW": { "length_12hr": 7, "length_24hr": 5, "name": "繁體中文" },
    "cy": { "length_12hr": 8, "length_24hr": 5, "name": "Cymraeg" },
    "de": { "length_12hr": 8, "length_24hr": 5, "name": "Deutsch" },
    "es": { "length_12hr": 11, "length_24hr": 5, "name": "Español" },
    "fr": { "length_12hr": 8, "length_24hr": 5, "name": "Français" },
    "it": { "length_12hr": 8, "length_24hr": 5, "name": "Italiano" },
    "lt": { "length_12hr": 15, "length_24hr": 5, "name": "Lietuviškai" },
    "lrc": { "length_12hr": 8, "length_24hr": 5, "name": "Luri (Bakhtiari)" },
    "hu": { "length_12hr": 9, "length_24hr": 5, "name": "Magyar" },
    "mn": { "length_12hr": 10, "length_24hr": 5, "name": "Mongolian" },
    "nl": { "length_12hr": 10, "length_24hr": 5, "name": "Nederlands" },
    "pl": { "length_12hr": 8, "length_24hr": 5, "name": "Polski" },
    "pt": { "length_12hr": 8, "length_24hr": 5, "name": "Português" },
    "pt-BR": { "length_12hr": 8, "length_24hr": 5, "name": "Português Brasileiro" },
    "pt-PT": { "length_12hr": 14, "length_24hr": 5, "name": "Portuguese (Portugal)" },
    "ro": { "length_12hr": 10, "length_24hr": 5, "name": "Română" },
    "si": { "length_12hr": 11, "length_24hr": 5, "name": "Sinhala" },
    "fi": { "length_12hr": 9, "length_24hr": 5, "name": "Suomi" },
    "sv": { "length_12hr": 8, "length_24hr": 5, "name": "Svenska" },
    "tl": { "length_12hr": 8, "length_24hr": 5, "name": "Tagalog" },
    "vi": { "length_12hr": 8, "length_24hr": 5, "name": "Tiếng Việt" },
    "tr": { "length_12hr": 8, "length_24hr": 5, "name": "Türkçe" },
    "be": { "length_12hr": 8, "length_24hr": 5, "name": "Беларуская" },
    "bg": { "length_12hr": 15, "length_24hr": 8, "name": "Български" },
    "ru": { "length_12hr": 8, "length_24hr": 5, "name": "Русский" },
    "sr": { "length_12hr": 8, "length_24hr": 5, "name": "Српски" },
    "uk": { "length_12hr": 8, "length_24hr": 5, "name": "Українська" },
    "ar": { "length_12hr": 7, "length_24hr": 5, "name": "العربيّة" },
    "fa": { "length_12hr": 15, "length_24hr": 5, "name": "فارسی" },
    "hi": { "length_12hr": 8, "length_24hr": 5, "name": "हिंदी" },
    "ta": { "length_12hr": 14, "length_24hr": 5, "name": "தமிழ்" },
    "ml": { "length_12hr": 8, "length_24hr": 5, "name": "മലയാളം" },
    "ko": { "length_12hr": 8, "length_24hr": 5, "name": "한국어" },
    "ja": { "length_12hr": 7, "length_24hr": 5, "name": "日本語" },
    "zh-CN": { "length_12hr": 7, "length_24hr": 5, "name": "简体中文" }
};

export function calculateFormattedTimeWidth() {
    const locale = timerender.get_user_locale();
    const localeData = maxlength_all_lang[locale];
    let formattedTimeWidth = 8; // Default width if locale is not found

    if (localeData) {
        formattedTimeWidth = user_settings.twenty_four_hour_time ? localeData.length_24hr : localeData.length_12hr;
    }
    formattedTimeWidth+=1; //Extra space for alignment
    document.documentElement.style.setProperty('--formatted-time-width', `${formattedTimeWidth}ch`);
}
