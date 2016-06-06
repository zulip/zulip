// commonjs code goes here

var i18n = window.i18n = require('i18next');
var XHR = require('i18next-xhr-backend');
var lngDetector = require('i18next-browser-languagedetector');
var backendOptions = {
    loadPath: '/static/locale/__lng__/translations.json'
};

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
});
