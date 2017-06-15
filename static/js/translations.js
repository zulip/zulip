// commonjs code goes here

import i18next from 'i18next';
import XHR from 'i18next-xhr-backend';
import LngDetector from 'i18next-browser-languagedetector';
import Cache from 'i18next-localstorage-cache';

window.i18n = i18next;

var backendOptions = {
    loadPath: '/static/locale/__lng__/translations.json',
};
var callbacks = [];
var initialized = false;

var detectionOptions = {
    order: ['htmlTag'],
    htmlTag: document.documentElement,
};

var cacheOptions = {
    enabled: true,
    prefix: 'i18next:' + page_params.server_generation + ':',
    expirationTime: 2*7*24*60*60*1000,  // 2 weeks
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
