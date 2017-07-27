var config = require('./webpack.config.js');
var BundleTracker = require('webpack-bundle-tracker');
var webpack = require('webpack');

// Built webpack dev asset reloader
config.entry.common.unshift('webpack/hot/dev-server');
// Use 0.0.0.0 so that we can set a port but still use the host
// the browser is connected to.
config.entry.common.unshift('webpack-dev-server/client?http://0.0.0.0:9994');

// Out JS debugging tools
config.entry.common.push('./static/js/debug.js');

config.devtool = 'eval';
config.output.publicPath = '/webpack/';
config.plugins.push(new BundleTracker({filename: 'var/webpack-stats-dev.json'}));
// Hot Reload of code in development
config.plugins.push(new webpack.HotModuleReplacementPlugin());
// Better logging from console for hot reload
config.plugins.push(new webpack.NamedModulesPlugin());

// script-loader should load sourceURL in dev
config.plugins.push(new webpack.LoaderOptionsPlugin({debug: true}));

config.devServer = {
    clientLogLevel: "warning",
    hot: true,
    inline: false,
    stats: "errors-only",
    watchOptions: {
        aggregateTimeout: 300,
        poll: 1000,
    },
};

module.exports = config;
