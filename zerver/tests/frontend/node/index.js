var fs = require('fs');

// Run all the JS scripts in our test directory.  Tests do NOT run
// in isolation.

var tests = fs.readdirSync(__dirname)
    .filter(function (filename) { return (/\.js$/i).test(filename); })
    .map(function (filename) { return filename.replace(/\.js$/i, ''); });

tests.forEach(function (filename) {
    if (filename === 'index.js') {
        return;
    }
    console.info('running tests for ' + filename);
    require('./' + filename);
});
