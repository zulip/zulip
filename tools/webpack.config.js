var path = require('path');

module.exports = {
    entry: [
        'webpack-dev-server/client?http://0.0.0.0:9991/socket.io',
        './static/js/src/main.js',
    ],
    devtool: 'eval',
    output: {
        publicPath: 'http://0.0.0.0:9991/webpack/',
        path: path.resolve(__dirname, '../static/js'),
        filename: 'bundle.js',
    },
    devServer: {
        port: 9994,
        stats: "errors-only",
        watchOptions: {
            aggregateTimeout: 300,
            poll: 1000,
        },
    },
};
