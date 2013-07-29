/*global casper*/
/*jshint strict:false*/
var waitStart;

casper.start('tests/site/index.html', function() {
    waitStart = new Date().getTime();
});

casper.wait(1000, function() {
    this.test.comment('Casper.wait()');
    this.test.assert(new Date().getTime() - waitStart > 1000, 'Casper.wait() can wait for a given amount of time');
});

casper.thenOpen('tests/site/waitFor.html', function() {
    this.test.comment('Casper.waitFor()');
    this.waitFor(function() {
        return this.evaluate(function() {
            return document.querySelectorAll('li').length === 4;
        });
    }, function() {
        this.test.pass('Casper.waitFor() can wait for something to happen');
    }, function() {
        this.test.fail('Casper.waitFor() can wait for something to happen');
    });
});

casper.thenOpen('tests/site/waitFor.html').waitForText('<li>four</li>', function() {
    this.test.comment('Casper.waitForText()');
    this.test.pass('Casper.waitForText() can wait for text');
}, function() {
    this.test.comment('Casper.waitForText()');
    this.test.fail('Casper.waitForText() can wait for text');
});

casper.thenOpen('tests/site/waitFor.html').waitForText(/four/i, function() {
    this.test.comment('Casper.waitForText()');
    this.test.pass('Casper.waitForText() can wait for regexp');
}, function() {
    this.test.comment('Casper.waitForText()');
    this.test.fail('Casper.waitForText() can wait for regexp');
});

casper.run(function() {
    this.test.done(4);
});
