/*global casper*/
/*jshint strict:false*/
casper.start('tests/site/visible.html', function() {
    this.test.comment('Casper.visible()');
    this.test.assert(this.visible('#img1'), 'Casper.visible() can detect if an element is visible');
    this.test.assert(!this.visible('#img2'), 'Casper.visible() can detect if an element is invisible');
    this.test.assert(!this.visible('#img3'), 'Casper.visible() can detect if an element is invisible');
    this.waitWhileVisible('#img1', function() {
        this.test.comment('Casper.waitWhileVisible()');
        this.test.pass('Casper.waitWhileVisible() can wait while an element is visible');
    }, function() {
        this.test.comment('Casper.waitWhileVisible()');
        this.test.fail('Casper.waitWhileVisible() can wait while an element is visible');
    }, 2000);
});

casper.run(function() {
    this.test.done(4);
});
