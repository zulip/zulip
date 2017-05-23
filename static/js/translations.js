// commonjs code goes here

(function () {
    var i18n = window.i18n = require('i18next');
    var XHR = require('i18next-xhr-backend');
    var lngDetector = require('i18next-browser-languagedetector');
    var Cache = require('i18next-localstorage-cache');

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

    i18n.use(XHR)
        .use(lngDetector)
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

    i18n.ensure_i18n = function (callback) {
        if (initialized) {
            callback();
        } else {
            callbacks.push(callback);
        }
    };

}());
