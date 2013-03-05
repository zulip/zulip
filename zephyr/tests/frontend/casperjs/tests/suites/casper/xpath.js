/*global casper __utils__*/
/*jshint strict:false*/
var x = require('casper').selectXPath;

casper.test.comment('XPath');

casper.start('tests/site/index.html', function() {
    this.test.assertExists({
        type: 'xpath',
        path: '/html/body/ul/li[2]'
    }, 'XPath selector can find an element');
    this.test.assertDoesntExist({
        type: 'xpath',
        path: '/html/body/ol/li[2]'
    }, 'XPath selector does not retrieve an unexistent element');
    this.test.assertExists(x('/html/body/ul/li[2]'), 'selectXPath() shortcut can find an element as well');
    this.test.assertEvalEquals(function() {
        return __utils__.findAll({type: 'xpath', path: '/html/body/ul/li'}).length;
    }, 3, 'Correct number of elements are found');
});

casper.thenClick(x('/html/body/a[2]'), function() {
    this.test.assertTitle('CasperJS test form', 'Clicking XPath works as expected');
    this.fill(x('/html/body/form'), {
        email: 'chuck@norris.com'
    });
    this.test.assertEvalEquals(function() {
        return document.querySelector('input[name="email"]').value;
    }, 'chuck@norris.com', 'Casper.fill() can fill an input[type=text] form field');
});

casper.run(function() {
    this.test.done(6);
});
