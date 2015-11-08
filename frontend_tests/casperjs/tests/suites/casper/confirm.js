/*global casper*/
/*jshint strict:false*/
var received;

casper.setFilter('page.confirm', function(message) {
    received = message;
    return true;
});

casper.start('tests/site/confirm.html', function() {
    this.test.assert(this.getGlobal('confirmed'), 'confirmation dialog accepted');
});

casper.then(function() {
    //remove the page.confirm event filter so we can add a new one
    casper.removeAllFilters('page.confirm')
    casper.setFilter('page.confirm', function(message) {
        return false;
    });
});

casper.thenOpen('/tests/site/confirm.html', function() {
    this.test.assertNot(this.getGlobal('confirmed'), 'confirmation dialog canceled');
});

casper.run(function() {
    this.test.assertEquals(received, 'are you sure?', 'confirmation message is ok');
    this.test.done(3);
});
