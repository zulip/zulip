/*global casper*/
/*jshint strict:false*/
casper.setFilter('page.prompt', function(message, value) {
    return 'Chuck ' + value;
});

casper.start('tests/site/prompt.html', function() {
    this.test.assertEquals(this.getGlobal('name'), 'Chuck Norris', 'prompted value has been received');
});

casper.run(function() {
    this.test.done(1);
});
