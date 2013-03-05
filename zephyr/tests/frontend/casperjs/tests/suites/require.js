/*global casper*/
/*jshint strict:false*/
var fs = require('fs');
var modroot = fs.pathJoin(phantom.casperPath, 'tests', 'sample_modules');
var jsmod, csmod, config;

casper.test.comment('Javascript module loading')
try {
    jsmod = require(fs.pathJoin(modroot, 'jsmodule'));
    casper.test.assertTrue(jsmod.ok, 'require() patched version can load a js module');
} catch (e) {
    casper.test.fail('require() patched version can load a js module');
}

casper.test.comment('CoffeeScript module loading')
try {
    csmod = require(fs.pathJoin(modroot, 'csmodule'));
    casper.test.assertTrue(csmod.ok, 'require() patched version can load a coffeescript module');
} catch (e) {
    casper.test.fail('require() patched version can load a coffeescript module');
}

casper.test.comment('JSON module loading')
try {
    config = require(fs.pathJoin(modroot, 'config.json'));
    casper.test.assertTrue(config.ok, 'require() patched version can load a json module');
} catch (e) {
    casper.test.fail('require() patched version can load a json module');
}

casper.test.done(3);
