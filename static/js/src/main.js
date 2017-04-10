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
        prefix: page_params.server_generation + ':',
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

    // garbage collect all old i18n translation maps in localStorage.
    i18n.remove_old_translations = function () {
        // this collects all localStorage keys that match the format of:
        // - dddddddddd:w+ => 1484902202:en
        // these are all language translation strings.
        var translations = Object.keys(localStorage).filter(function (key) {
            return /\d{10}:\w+/.test(key);
        });

        // by sorting them we get the lowest timestamps at the bottom and the
        // most recent at the top.
        translations = translations.sort();

        // remove the latest translation (our current working one) from the list.
        translations.pop();

        // remove all the old translations.
        translations.forEach(function (translation_key) {
            localStorage.removeItem(translation_key);
        });

        return this;
    };

    // run gc of old sessions on startup.
    i18n.remove_old_translations();
}());
