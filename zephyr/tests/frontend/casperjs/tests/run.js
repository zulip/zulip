/*global phantom CasperError*/

if (!phantom.casperLoaded) {
    console.log('This script must be invoked using the casperjs executable');
    phantom.exit(1);
}

var fs           = require('fs');
var colorizer    = require('colorizer');
var utils        = require('utils');
var f            = utils.format;
var loadIncludes = ['includes', 'pre', 'post'];
var tests        = [];
var casper       = require('casper').create({
    exitOnError: false
});

// local utils
function checkSelfTest(tests) {
    "use strict";
    var isCasperTest = false;
    tests.forEach(function(test) {
        var testDir = fs.absolute(fs.dirname(test));
        if (fs.isDirectory(testDir) && fs.exists(fs.pathJoin(testDir, '.casper'))) {
            isCasperTest = true;
        }
    });
    return isCasperTest;
}

function checkIncludeFile(include) {
    "use strict";
    var absInclude = fs.absolute(include.trim());
    if (!fs.exists(absInclude)) {
        casper.warn("%s file not found, can't be included", absInclude);
        return;
    }
    if (!utils.isJsFile(absInclude)) {
        casper.warn("%s is not a supported file type, can't be included", absInclude);
        return;
    }
    if (fs.isDirectory(absInclude)) {
        casper.warn("%s is a directory, can't be included", absInclude);
        return;
    }
    if (tests.indexOf(include) > -1 || tests.indexOf(absInclude) > -1) {
        casper.warn("%s is a test file, can't be included", absInclude);
        return;
    }
    return absInclude;
}

function checkArgs() {
    "use strict";
    // parse some options from cli
    casper.options.verbose = casper.cli.get('direct') || false;
    casper.options.logLevel = casper.cli.get('log-level') || "error";
    if (casper.cli.get('no-colors') === true) {
        var cls = 'Dummy';
        casper.options.colorizerType = cls;
        casper.colorizer = colorizer.create(cls);
    }
    casper.test.options.failFast = casper.cli.get('fail-fast') || false;

    // test paths are passed as args
    if (casper.cli.args.length) {
        tests = casper.cli.args.filter(function(path) {
            if (fs.isFile(path) || fs.isDirectory(path)) {
                return true;
            }
            throw new CasperError(f("Invalid test path: %s", path));
        });
    } else {
        casper.echo('No test path passed, exiting.', 'RED_BAR', 80);
        casper.exit(1);
    }

    // check for casper selftests
    if (!phantom.casperSelfTest && checkSelfTest(tests)) {
        casper.warn('To run casper self tests, use the `selftest` command.');
        casper.exit(1);
    }
}

function initRunner() {
    "use strict";
    // includes handling
    loadIncludes.forEach(function(include){
        var container;
        if (casper.cli.has(include)) {
            container = casper.cli.get(include).split(',').map(function(file) {
                return checkIncludeFile(file);
            }).filter(function(file) {
                return utils.isString(file);
            });
            casper.test.loadIncludes[include] = utils.unique(container);
        }
    });

    // test suites completion listener
    casper.test.on('tests.complete', function() {
        this.renderResults(true, undefined, casper.cli.get('xunit') || undefined);
        if (this.options.failFast && this.testResults.failures.length > 0) {
            casper.warn('Test suite failed fast, all tests may not have been executed.');
        }
    });
}

var error;
try {
    checkArgs();
} catch (e) {
    error = true;
    casper.warn(e);
    casper.exit(1);
}

if (!error) {
    initRunner();
    casper.test.runSuites.apply(casper.test, tests);
}
