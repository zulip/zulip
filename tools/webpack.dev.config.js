var config = require('./webpack.config.js');
var BundleTracker = require('webpack-bundle-tracker');

// katex should be an array, to inject webpack dependencies in dev config
// better to be moved to common.js when common.js is added to assets
config.entry.katex.unshift('webpack-dev-server/client?/sockjs-node');
config.devtool = 'eval';
config.output.publicPath = '/webpack/';
config.plugins.push(new BundleTracker({filename: 'static/webpack-bundles/webpack-stats-dev.json'}));

config.devServer = {
    port: 9994,
    inline: false,
    stats: "errors-only",
    watchOptions: {
        aggregateTimeout: 300,
        poll: 1000,
    },
};

module.exports = config;
