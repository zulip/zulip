var config = require('./webpack.config.js');
var BundleTracker = require('webpack-bundle-tracker');

// Built webpack dev asset reloader
config.entry.common.unshift('webpack-dev-server/client?/sockjs-node');
// Out JS debugging tools
config.entry.common.push('./static/js/debug.js');

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
