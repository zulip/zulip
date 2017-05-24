var path = require('path');
var assets = require('./webpack.assets.json');

module.exports =  {
    context: path.resolve(__dirname, "../"),
    entry: assets,
    module: {
        noParse: /(min)\.js/,
        rules: [
            {
                test: /\.tsx?$/,
                loader: 'ts-loader',
            },
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
