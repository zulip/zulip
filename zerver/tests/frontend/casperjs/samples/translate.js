/*jshint strict:false*/
/*global CasperError console phantom require*/

/**
 * Translation using the Google Translate Service.
 *
 * Usage:
 *
 *     $ casperjs translate.js --target=fr "hello world"
 *     bonjour tout le monde
 */
var system = require('system'),
    casper = require('casper').create(),
    format = require('utils').format,
    source = casper.cli.get('source') || 'auto',
    target = casper.cli.get('target'),
    text   = casper.cli.get(0),
    result;

if (!target) {
    casper.warn('The --target option is mandatory.').exit(1);
}

casper.start(format('http://translate.google.com/#%s/%s/%s', source, target, text), function() {
    this.fill('form#gt-form', {text: text});
}).waitForSelector('span.hps', function() {
    this.echo(this.fetchText("#result_box"));
});

casper.run();
