/*global casper*/
try {
    exports.ok = true;
} catch (e) {
    casper.test.fail('error in js module code' + e);
    casper.test.done()
}
