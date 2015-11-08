/*global casper*/
/*jshint strict:false maxstatements: 99*/
var utils = require('utils');

casper.start('tests/site/index.html', function() {
    this.click('a[href="test.html"]');
});

casper.then(function() {
    this.test.comment('Casper.click()');
    this.test.assertTitle('CasperJS test target', 'Casper.click() can click on a link');
}).thenClick('a', function() {
    this.test.comment('Casper.thenClick()');
    this.test.assertTitle('CasperJS test form', 'Casper.thenClick() can click on a link');
});

// onclick variants tests
casper.thenOpen('tests/site/click.html', function() {
    this.test.comment('Casper.click()');
    this.test.assert(this.click('#test1'), 'Casper.click() can click an `href="javascript:` link');
    this.test.assert(this.click('#test2'), 'Casper.click() can click an `href="#"` link');
    this.test.assert(this.click('#test3'), 'Casper.click() can click an `onclick=".*; return false"` link');
    this.test.assert(this.click('#test4'), 'Casper.click() can click an unobstrusive js handled link');
    var results = this.getGlobal('results');
    this.test.assert(results.test1, 'Casper.click() has clicked an `href="javascript:` link');
    this.test.assert(results.test2, 'Casper.click() has clicked an `href="#"` link');
    this.test.assert(results.test3, 'Casper.click() has clicked an `onclick=".*; return false"` link');
    this.test.assert(results.test4, 'Casper.click() has clicked an unobstrusive js handled link');
});

// clickLabel tests
casper.thenOpen('tests/site/click.html', function() {
    this.test.comment('Casper.clickLabel()');
    this.test.assert(this.clickLabel('test1'), 'Casper.clickLabel() can click an `href="javascript:` link');
    this.test.assert(this.clickLabel('test2'), 'Casper.clickLabel() can click an `href="#"` link');
    this.test.assert(this.clickLabel('test3'), 'Casper.clickLabel() can click an `onclick=".*; return false"` link');
    this.test.assert(this.clickLabel('test4'), 'Casper.clickLabel() can click an unobstrusive js handled link');
    var results = this.getGlobal('results');
    this.test.assert(results.test1, 'Casper.clickLabel() has clicked an `href="javascript:` link');
    this.test.assert(results.test2, 'Casper.clickLabel() has clicked an `href="#"` link');
    this.test.assert(results.test3, 'Casper.clickLabel() has clicked an `onclick=".*; return false"` link');
    this.test.assert(results.test4, 'Casper.clickLabel() has clicked an unobstrusive js handled link');
});

// casper.mouse
casper.then(function() {
    this.test.comment('Mouse.down()');
    this.mouse.down(200, 100);
    var results = this.getGlobal('results');
    this.test.assertEquals(results.testdown, [200, 100], 'Mouse.down() has pressed button to the specified position');

    this.test.comment('Mouse.up()');
    this.mouse.up(200, 100);
    results = this.getGlobal('results');
    this.test.assertEquals(results.testup, [200, 100], 'Mouse.up() has released button to the specified position');

    this.test.comment('Mouse.move()');
    this.mouse.move(200, 100);
    results = this.getGlobal('results');
    this.test.assertEquals(results.testmove, [200, 100], 'Mouse.move() has moved to the specified position');

    if (utils.gteVersion(phantom.version, '1.8.0')) {
        this.test.comment('Mouse.doubleclick()');
        this.mouse.doubleclick(200, 100);
        results = this.getGlobal('results');
        this.test.assertEquals(results.testdoubleclick, [200, 100],
            'Mouse.doubleclick() double-clicked the specified position');
    } else {
        this.test.pass("Mouse.doubleclick() requires PhantomJS >= 1.8");
    }
});

// element focus on click
casper.then(function() {
    this.page.content = '<form><input type="text" name="foo"></form>'
    this.click('form input[name=foo]')
    this.page.sendEvent('keypress', 'bar');
    this.test.assertEquals(this.getFormValues('form')['foo'], 'bar', 'Casper.click() sets the focus on clicked element');
});

casper.run(function() {
    this.test.done(23);
});
