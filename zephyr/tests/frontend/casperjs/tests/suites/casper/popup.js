/*jshint strict:false*/
/*global CasperError casper console phantom require*/
var utils = require('utils');
var x = require('casper').selectXPath;

casper.on('popup.created', function(popup) {
    this.test.pass('"popup.created" event is fired');
    this.test.assert(utils.isWebPage(popup),
        '"popup.created" event callback get a popup page instance');
});

casper.on('popup.loaded', function(popup) {
    this.test.pass('"popup.loaded" event is fired');
    this.test.assertEquals(popup.evaluate(function() {
        return document.title;
    }), 'CasperJS test index',
        '"popup.loaded" is triggered when popup content is actually loaded');
});

casper.on('popup.closed', function(popup) {
    this.test.assertEquals(this.popups.length, 0, '"popup.closed" event is fired');
});

casper.start('tests/site/popup.html');

casper.waitForPopup('index.html', function() {
    this.test.pass('Casper.waitForPopup() waits for a popup being created');
    this.test.assertEquals(this.popups.length, 1, 'A popup has been added');
    this.test.assert(utils.isWebPage(this.popups[0]), 'A popup is a WebPage');
});

casper.withPopup('index.html', function() {
    this.test.assertUrlMatches(/index\.html$/,
        'Casper.withPopup() switched to popup as current active one');
    this.test.assertEval(function() {
        return '__utils__' in window;
    }, 'Casper.withPopup() has client utils injected');
    this.test.assertExists('h1',
        'Casper.withPopup() can perform assertions on the DOM');
    this.test.assertExists(x('//h1'),
        'Casper.withPopup() can perform assertions on the DOM using XPath');
});

casper.then(function() {
    this.test.assertUrlMatches(/popup\.html$/,
        'Casper.withPopup() has reverted to main page after using the popup');
});

casper.thenClick('.close', function() {
    this.test.assertEquals(this.popups.length, 0, 'Popup is removed when closed');
});

casper.thenOpen('tests/site/popup.html');

casper.waitForPopup(/index\.html$/, function() {
    this.test.pass('Casper.waitForPopup() waits for a popup being created');
});

casper.withPopup(/index\.html$/, function() {
    this.test.assertTitle('CasperJS test index',
        'Casper.withPopup() can use a regexp to identify popup');
});

casper.thenClick('.close', function() {
    this.test.assertUrlMatches(/popup\.html$/,
        'Casper.withPopup() has reverted to main page after using the popup');
    this.test.assertEquals(this.popups.length, 0, 'Popup is removed when closed');
    this.removeAllListeners('popup.created');
    this.removeAllListeners('popup.loaded');
    this.removeAllListeners('popup.closed');
});

casper.thenClick('a[target="_blank"]');

casper.waitForPopup('form.html', function() {
    this.test.pass('Casper.waitForPopup() waits when clicked on a link with target=_blank');
});

casper.withPopup('form.html', function() {
    this.test.assertTitle('CasperJS test form');
});

casper.run(function() {
    // removes event listeners as they've now been tested already
    this.test.done(25);
});
