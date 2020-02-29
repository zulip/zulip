import i18next from 'i18next';

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

window.i18n = i18next;
