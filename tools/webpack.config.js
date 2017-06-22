var path = require('path');
var assets = require('./webpack.assets.json');

module.exports =  {
    context: path.resolve(__dirname, "../"),
    entry: assets,
    module: {
        rules: [
            // Run the typescript compilier on .ts files before webpack
            {
                test: /\.tsx?$/,
                loader: 'ts-loader',
            },
            // This loads and transforms sourcemap files from other compiliers.
            // The typescript comilier will generate a sourcemap and source-map-loaded will output
            // the correct sourcemap from that.
            {
                enforce: 'pre',
                test: /\.js$/,
                loader: "source-map-loader",
            },
            {
                enforce: 'pre',
                test: /\.tsx?$/,
                use: "source-map-loader",
            },
            // Uses script-loader on minified files so we don't change global variables in them.
            // Also has the effect of making processing these files fast
            {
                test: /(min|zxcvbn)\.js/,
                use: [ 'script-loader' ],
            },
            // Expose Global variables to webpack
            {
                test: require.resolve('../static/js/debug.js'),
                use: [
                    {loader: 'expose-loader', options: 'debug'},
                ],
            },
            {
                test: require.resolve('../static/js/blueslip.js'),
                use: [
                    {loader: 'expose-loader', options: 'blueslip'},
                ],
            },
            {
                test: require.resolve('../static/js/common.js'),
                use: [
                    {loader: 'expose-loader', options: 'common'},
                ],
            },
        ],
    },
    output: {
        path: path.resolve(__dirname, '../static/webpack-bundles'),
        filename: '[name].js',
    },
    plugins: [],
    resolve: {
        extensions: [".tsx", ".ts", ".js", ".json"],
    },
};
