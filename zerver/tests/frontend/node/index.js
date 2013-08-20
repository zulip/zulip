var fs = require('fs');

// Run all the JS scripts in our test directory.  The order that the scripts
// run in now is fairly arbitrary, as they run isolated from each other, and
// none of them are particularly slow.

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
