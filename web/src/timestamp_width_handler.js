import * as timerender from "./timerender";
import {user_settings} from "./user_settings";

// candidate_timestamps are contains max possible timestamps in every locale
const candidate_timestamps = {
    id: {
        maxtimestamp12_hr: "11:59 PM",
        maxtimestamp24_hr: "23:59",
        name: "Bahasa Indonesia",
    },
    "en-GB": {
        maxtimestamp12_hr: "11:59 PM",
        maxtimestamp24_hr: "23:59",
        name: "British English",
    },
    ca: {
        maxtimestamp12_hr: "11:59 p. m.",
        maxtimestamp24_hr: "23:59",
        name: "Català",
    },
    cs: {
        maxtimestamp12_hr: "11:59 odp.",
        maxtimestamp24_hr: "23:59",
        name: "česky",
    },
    "zh-TW": {
        maxtimestamp12_hr: "下午11:59",
        maxtimestamp24_hr: "23:59",
        name: "繁體中文",
    },
    cy: {
        maxtimestamp12_hr: "11:59 yh",
        maxtimestamp24_hr: "23:59",
        name: "Cymraeg",
    },
    de: {
        maxtimestamp12_hr: "11:59 PM",
        maxtimestamp24_hr: "23:59",
        name: "Deutsch",
    },
    es: {
        maxtimestamp12_hr: "11:59 p. m.",
        maxtimestamp24_hr: "23:59",
        name: "Español",
    },
    fr: {
        maxtimestamp12_hr: "11:59 PM",
        maxtimestamp24_hr: "23:59",
        name: "Français",
    },
    it: {
        maxtimestamp12_hr: "11:59 PM",
        maxtimestamp24_hr: "23:59",
        name: "Italiano",
    },
    lt: {
        maxtimestamp12_hr: "11:59 popiet",
        maxtimestamp24_hr: "23:59",
        name: "Lietuviškai",
    },
    lrc: {
        maxtimestamp12_hr: "۱۱:۵۹ PM",
        maxtimestamp24_hr: "۲۳:۵۹",
        name: "Luri (Bakhtiari)",
    },
    hu: {
        maxtimestamp12_hr: "du. 11:59",
        maxtimestamp24_hr: "23:59",
        name: "Magyar",
    },
    mn: {
        maxtimestamp12_hr: "11:59 ү.х.",
        maxtimestamp24_hr: "23:59",
        name: "Mongolian",
    },
    nl: {
        maxtimestamp12_hr: "11:59 p.m.",
        maxtimestamp24_hr: "23:59",
        name: "Nederlands",
    },
    pl: {
        maxtimestamp12_hr: "11:59 PM",
        maxtimestamp24_hr: "23:59",
        name: "Polski",
    },
    pt: {
        maxtimestamp12_hr: "11:59 PM",
        maxtimestamp24_hr: "23:59",
        name: "Português",
    },
    "pt-BR": {
        maxtimestamp12_hr: "11:59 PM",
        maxtimestamp24_hr: "23:59",
        name: "Português Brasileiro",
    },
    "pt-PT": {
        maxtimestamp12_hr: "11:59 da tarde",
        maxtimestamp24_hr: "23:59",
        name: "Portuguese (Portugal)",
    },
    ro: {
        maxtimestamp12_hr: "11:59 p.m.",
        maxtimestamp24_hr: "23:59",
        name: "Română",
    },
    si: {
        maxtimestamp12_hr: "ප.ව. 11:59",
        maxtimestamp24_hr: "23:59",
        name: "Sinhala",
    },
    fi: {
        maxtimestamp12_hr: "11:59 ip.",
        maxtimestamp24_hr: "23:59",
        name: "Suomi",
    },
    sv: {
        maxtimestamp12_hr: "11:59 em",
        maxtimestamp24_hr: "23:59",
        name: "Svenska",
    },
    tl: {
        maxtimestamp12_hr: "11:59 PM",
        maxtimestamp24_hr: "23:59",
        name: "Tagalog",
    },
    vi: {
        maxtimestamp12_hr: "11:59 CH",
        maxtimestamp24_hr: "23:59",
        name: "Tiếng Việt",
    },
    tr: {
        maxtimestamp12_hr: "ÖS 11:59",
        maxtimestamp24_hr: "23:59",
        name: "Türkçe",
    },
    be: {
        maxtimestamp12_hr: "11:59 PM",
        maxtimestamp24_hr: "23:59",
        name: "Беларуская",
    },
    bg: {
        maxtimestamp12_hr: "11:59 ч. сл.об.",
        maxtimestamp24_hr: "23:59 ч.",
        name: "Български",
    },
    ru: {
        maxtimestamp12_hr: "11:59 PM",
        maxtimestamp24_hr: "23:59",
        name: "Русский",
    },
    sr: {
        maxtimestamp12_hr: "11:59 PM",
        maxtimestamp24_hr: "23:59",
        name: "Српски",
    },
    uk: {
        maxtimestamp12_hr: "11:59 пп",
        maxtimestamp24_hr: "23:59",
        name: "Українська",
    },
    ar: {
        maxtimestamp12_hr: "١١:٥٩ م",
        maxtimestamp24_hr: "٢٣:٥٩",
        name: "العربيّة",
    },
    fa: {
        maxtimestamp12_hr: "۱۱:۵۹ بعدازظهر",
        maxtimestamp24_hr: "۲۳:۵۹",
        name: "فارسی",
    },
    hi: {
        maxtimestamp12_hr: "11:59 PM",
        maxtimestamp24_hr: "23:59",
        name: "हिंदी",
    },
    ta: {
        maxtimestamp12_hr: "பிற்பகல் 11:59",
        maxtimestamp24_hr: "23:59",
        name: "தமிழ்",
    },
    ml: {
        maxtimestamp12_hr: "11:59 PM",
        maxtimestamp24_hr: "23:59",
        name: "മലയാളം",
    },
    ko: {
        maxtimestamp12_hr: "오후 11:59",
        maxtimestamp24_hr: "23:59",
        name: "한국어",
    },
    ja: {
        maxtimestamp12_hr: "午後11:59",
        maxtimestamp24_hr: "23:59",
        name: "日本語",
    },
    "zh-CN": {
        maxtimestamp12_hr: "下午11:59",
        maxtimestamp24_hr: "23:59",
        name: "简体中文",
    },
};

export function calculateFormattedTimeWidth() {
    const locale = timerender.get_user_locale();
    const localeData = candidate_timestamps[locale];
    let formattedTimeWidth = 45; // Default width if locale is not found

    if (localeData) {
        // timestamp contains the string according to timeformat.
        const timestamp = user_settings.twenty_four_hour_time
            ? localeData.maxtimestamp24_hr
            : localeData.maxtimestamp12_hr;

        // logic for rendering timestamp in hidden div and calculating it's width.
        const hiddenDiv = document.createElement("div");

        hiddenDiv.style.visibility = "hidden";
        hiddenDiv.style.position = "absolute";
        hiddenDiv.style.whiteSpace = "nowrap";
        hiddenDiv.textContent = timestamp;

        document.body.append(hiddenDiv);

        formattedTimeWidth = hiddenDiv.offsetWidth;

        hiddenDiv.remove();
    }

    formattedTimeWidth += 9; // Extra space for alignment as pixel size differs fontsize.
    document.documentElement.style.setProperty("--formatted-time-width", `${formattedTimeWidth}px`);
}
