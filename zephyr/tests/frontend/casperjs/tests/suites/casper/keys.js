/*jshint strict:false*/
/*global CasperError casper console phantom require*/
casper.start('tests/site/form.html', function() {
    this.sendKeys('input[name="email"]', 'duke@nuk.em');
    this.sendKeys('textarea', "Damn, I’m looking good.");
    var values = this.getFormValues('form');
    this.test.assertEquals(values['email'], 'duke@nuk.em',
        'Casper.sendKeys() sends keys to given input');
    this.test.assertEquals(values['content'], "Damn, I’m looking good.",
        'Casper.sendKeys() sends keys to given textarea');
});

casper.run(function() {
    this.test.done(2);
});
