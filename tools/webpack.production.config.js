var config = require('./webpack.config.js');
var BundleTracker = require('webpack-bundle-tracker');

config.devtool = 'source-map';
config.output.filename = '[name]-[hash].js';
config.plugins.push(new BundleTracker({filename: 'webpack-stats-production.json'}));

module.exports = config;
