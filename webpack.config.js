module.exports = {
    entry: [
        'webpack-dev-server/client?http://localhost:9991/socket.io',
        './static/js/src/main.js'
    ],
    devtool: 'eval',
    output: {
        publicPath: 'http://localhost:9991/webpack/',
        path: './static/js',
        filename: 'bundle.js'
    },
    devServer: {
        port: 9994,
        stats: "errors-only",
        watchOptions: {
            aggregateTimeout: 300,
            poll: 1000
        }
    }
};
