// commonjs code goes here

(function () {
    var i18n = window.i18n = require('i18next');
    var XHR = require('i18next-xhr-backend');
    var lngDetector = require('i18next-browser-languagedetector');
    var backendOptions = {
        loadPath: '/static/locale/__lng__/translations.json'
    };
    var callbacks = [];
    var initialized = false;

    var detectionOptions = {
        order: ['htmlTag'],
        htmlTag: document.documentElement
    };

    i18n.use(XHR)
        .use(lngDetector)
        .init({
            nsSeparator: false,
            keySeparator: false,
            interpolation: {
                prefix: "__",
                suffix: "__"
            },
            backend: backendOptions,
            detection: detectionOptions
        }, function () {
            var i;
            initialized = true;
            for (i=0; i<callbacks.length; i++) {
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
