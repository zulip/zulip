/*global casper*/
/*jshint strict:false*/
var fs = require('fs');
var modroot = fs.pathJoin(phantom.casperPath, 'tests', 'sample_modules');
var jsmod, csmod;

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

casper.test.done();
