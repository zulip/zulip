var path = require('path');
var assets = require('./webpack.assets.json');

module.exports =  {
    context: path.resolve(__dirname, "../"),
    entry: assets,
    module: {
        noParse: /(min)\.js/,
    },
    output: {
        path: path.resolve(__dirname, '../static/webpack-bundles'),
        filename: '[name].js',
    },
    plugins: [],
};
