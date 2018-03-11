// commonjs code goes here

import i18next from 'i18next';
import XHR from 'i18next-xhr-backend';
import LngDetector from 'i18next-browser-languagedetector';
import Cache from 'i18next-localstorage-cache';
import localstorage from './localstorage';

window.i18n = i18next;

// Add those keys in this list which are received from the backend
// and are translated by calling i18n.t function on variables. For example,
// i18n.t(receivedFromBackend);
var toBeTranslated = [  // eslint-disable-line no-unused-vars
    // The Emoji type name for the "text" emojiset choice
    i18n.t('Plain text'),
];

function loadPath(languages) {
    var language = languages[0];
    if (language.indexOf('-') >= 0) {
        language = language.replace('-', '_');  // Change zh-Hans to zh_Hans.
    }

    return '/static/locale/' + language + '/translations.json';
}

var backendOptions = {
    loadPath: loadPath,
};
var callbacks = [];
var initialized = false;

var detectionOptions = {
    order: ['htmlTag'],
    htmlTag: document.documentElement,
};

var cacheOptions = {
    enabled: !page_params.development,
    prefix: 'i18next:' + page_params.server_generation + ':',
    expirationTime: 2*24*60*60*1000,  // 2 days
};

i18next.use(XHR)
    .use(LngDetector)
    .use(Cache)
    .init({
        nsSeparator: false,
        keySeparator: false,
        interpolation: {
            prefix: "__",
            suffix: "__",
        },
        backend: backendOptions,
        detection: detectionOptions,
        cache: cacheOptions,
        fallbackLng: 'en',
        returnEmptyString: false,  // Empty string is not a valid translation.
    }, function () {
        var i;
        initialized = true;
        for (i=0; i<callbacks.length; i += 1) {
            callbacks[i]();
        }
    });

i18next.ensure_i18n = function (callback) {
    if (initialized) {
        callback();
    } else {
        callbacks.push(callback);
    }
};

// garbage collect all old i18n translation maps in localStorage.
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

    var current_generation_key = 'i18next:' + page_params.server_generation;
    // remove cached translations of older versions.
    translations.forEach(function (translation_key) {
        if (translation_key.indexOf(current_generation_key) !== 0) {
            localStorage.removeItem(translation_key);
        }
    });
    return this;
});
