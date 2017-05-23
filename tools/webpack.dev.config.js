var config = require('./webpack.config.js');

config.entry.push('webpack-dev-server/client?http://0.0.0.0:9991/socket.io');
config.devtool = 'eval';
config.output.publicPath = 'http://0.0.0.0:9991/webpack/';

config.devServer = {
    port: 9994,
    stats: "errors-only",
    watchOptions: {
        aggregateTimeout: 300,
        poll: 1000,
    },
};

module.exports = config;
