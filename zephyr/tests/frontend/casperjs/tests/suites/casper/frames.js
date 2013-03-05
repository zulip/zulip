/*global casper __utils__*/
/*jshint strict:false*/
casper.start('tests/site/frames.html');

casper.withFrame('frame1', function() {
    this.test.assertTitle('CasperJS frame 1');
    this.test.assertExists("#f1");
    this.test.assertDoesntExist("#f2");
    this.test.assertEval(function() {
        return '__utils__' in window && 'getBinary' in __utils__;
    }, '__utils__ object is available in child frame');
    this.test.assertMatches(this.page.frameContent, /This is frame 1/);
    this.test.assertMatches(this.getHTML(), /This is frame 1/);
});

casper.withFrame('frame2', function() {
    this.test.assertTitle('CasperJS frame 2');
    this.test.assertExists("#f2");
    this.test.assertDoesntExist("#f1");
    this.test.assertEval(function() {
        return '__utils__' in window && 'getBinary' in __utils__;
    }, '__utils__ object is available in other child frame');
    this.clickLabel('frame 3');
});

casper.withFrame('frame2', function() {
    this.test.assertTitle('CasperJS frame 3');
});

casper.withFrame(0, function() {
    this.test.assertTitle('CasperJS frame 1');
    this.test.assertExists("#f1");
    this.test.assertDoesntExist("#f2");
});

casper.withFrame(1, function() {
    this.test.assertTitle('CasperJS frame 3');
});

casper.run(function() {
    this.test.assertTitle('CasperJS test frames');
    this.test.done(16);
});
