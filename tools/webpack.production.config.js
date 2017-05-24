var path = require('path');

module.exports = {
    entry: './static/js/src/main.js',
    output: {
        path: path.resolve(__dirname, '../static/js'),
        filename: 'bundle.js',
    },
};
