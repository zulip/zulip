// commonjs code goes here
import i18next from 'i18next';
import localstorage from './localstorage';

window.i18n = i18next;

i18next.init({
    lng: 'lang',
    resources: {
        lang: {
            translation: page_params.translation_data,
        },
    },
    nsSeparator: false,
    keySeparator: false,
    interpolation: {
        prefix: "__",
        suffix: "__",
    },
    returnEmptyString: false,  // Empty string is not a valid translation.
});

// garbage collect all old-style i18n translation maps in localStorage.
$(function () {
    if (!localstorage.supported()) {
        return;
    }

    // this collects all localStorage keys that match the format of:
    //   i18next:dddddddddd:w+ => 1484902202:en
    // these are all language translation strings.
    var translations = Object.keys(localStorage).filter(function (key) {
        return /^i18next:\d{10}:\w+$/.test(key);
    });

    // remove cached translations of older versions.
    translations.forEach(function (translation_key) {
        localStorage.removeItem(translation_key);
    });
    return this;
});
