var path = require('path');

module.exports =  {
    context: path.resolve(__dirname, "../"),
    entry: {
        activity: './static/third/sorttable/sorttable.js',
        api: './static/js/portico/api.js',
        // katex should be an array, to inject webpack dependencies in dev config
        // better to be moved to common.js
        katex: ['./node_modules/katex/dist/katex.js'],
        'landing-page': './static/js/portico/landing-page.js',
        translations: './static/js/translations.js',
        zxcvbn: './node_modules/zxcvbn/dist/zxcvbn.js',
    },
    output: {
        path: path.resolve(__dirname, '../static/webpack-bundles'),
        filename: '[name].js',
    },
    plugins: [],
};
