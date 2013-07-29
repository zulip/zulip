/*global casper*/
/*jshint strict:false*/
var fs = require('fs');
var x = require('casper').selectXPath;

function fakeDocument(html) {
    window.document.body.innerHTML = html;
}

(function(casper) {
    casper.test.comment('ClientUtils.encode()');
    var clientutils = require('clientutils').create();
    var testCases = {
        'an empty string': '',
        'a word':          'plop',
        'a null char':     'a\u0000',
        'an utf8 string':  'ÀÁÃÄÅÇÈÉÊËÌÍÎÏÒÓÔÕÖÙÚÛÜÝàáâãäåçèéêëìíîïðòóôõöùúûüýÿ',
        'song lyrics':     ("Voilà l'été, j'aperçois le soleil\n" +
                            "Les nuages filent et le ciel s'éclaircit\n" +
                            "Et dans ma tête qui bourdonnent?\n" +
                            "Les abeilles!"),
        'a file contents': fs.read(phantom.casperPath + '/tests/site/alert.html')
    };
    for (var what in testCases) {
        var source = testCases[what];
        var encoded = clientutils.encode(source);
        casper.test.assertEquals(clientutils.decode(encoded), source, 'ClientUtils.encode() encodes and decodes ' + what);
    }
})(casper);

(function(casper) {
    casper.test.comment('ClientUtils.exists()');
    var clientutils = require('clientutils').create();
    fakeDocument('<ul class="foo"><li>bar</li><li>baz</li></ul>');
    casper.test.assert(clientutils.exists('ul'), 'ClientUtils.exists() checks that an element exist');
    casper.test.assertNot(clientutils.exists('ol'), 'ClientUtils.exists() checks that an element exist');
    casper.test.assert(clientutils.exists('ul.foo li'), 'ClientUtils.exists() checks that an element exist');
    // xpath
    casper.test.assert(clientutils.exists(x('//ul')), 'ClientUtils.exists() checks that an element exist using XPath');
    casper.test.assertNot(clientutils.exists(x('//ol')), 'ClientUtils.exists() checks that an element exist using XPath');
    fakeDocument(null);
})(casper);

(function(casper) {
    casper.test.comment('ClientUtils.findAll()');
    var clientutils = require('clientutils').create();
    fakeDocument('<ul class="foo"><li>bar</li><li>baz</li></ul>');
    casper.test.assertType(clientutils.findAll('li'), 'nodelist', 'ClientUtils.findAll() can find matching DOM elements');
    casper.test.assertEquals(clientutils.findAll('li').length, 2, 'ClientUtils.findAll() can find matching DOM elements');
    casper.test.assertType(clientutils.findAll('ol'), 'nodelist', 'ClientUtils.findAll() can find matching DOM elements');
    casper.test.assertEquals(clientutils.findAll('ol').length, 0, 'ClientUtils.findAll() can find matching DOM elements');
    // scoped
    var scope = clientutils.findOne('ul');
    casper.test.assertType(clientutils.findAll('li', scope), 'nodelist', 'ClientUtils.findAll() can find matching DOM elements within a given scope');
    casper.test.assertEquals(clientutils.findAll('li', scope).length, 2, 'ClientUtils.findAll() can find matching DOM elements within a given scope');
    casper.test.assertType(clientutils.findAll(x('//li'), scope), 'array', 'ClientUtils.findAll() can find matching DOM elements using XPath within a given scope');
    fakeDocument(null);
})(casper);

(function(casper) {
    casper.test.comment('ClientUtils.findOne()');
    var clientutils = require('clientutils').create();
    fakeDocument('<ul class="foo"><li>bar</li><li>baz</li></ul>');
    casper.test.assertType(clientutils.findOne('ul'), 'htmlulistelement', 'ClientUtils.findOne() can find a matching DOM element');
    casper.test.assertNot(clientutils.findOne('ol'), 'ClientUtils.findOne() can find a matching DOM element');
    // scoped
    var scope = clientutils.findOne('ul');
    casper.test.assertType(clientutils.findOne('li', scope), 'htmllielement', 'ClientUtils.findOne() can find a matching DOM element within a given scope');
    casper.test.assertType(clientutils.findOne(x('//li'), scope), 'htmllielement', 'ClientUtils.findOne() can find a matching DOM element using XPath within a given scope');
    fakeDocument(null);
})(casper);

(function(casper) {
    casper.test.comment('ClientUtils.processSelector()');
    var clientutils = require('clientutils').create();
    // CSS3 selector
    var cssSelector = clientutils.processSelector('html body > ul.foo li');
    casper.test.assertType(cssSelector, 'object', 'ClientUtils.processSelector() can process a CSS3 selector');
    casper.test.assertEquals(cssSelector.type, 'css', 'ClientUtils.processSelector() can process a CSS3 selector');
    casper.test.assertEquals(cssSelector.path, 'html body > ul.foo li', 'ClientUtils.processSelector() can process a CSS3 selector');
    // XPath selector
    var xpathSelector = clientutils.processSelector(x('//li[text()="blah"]'));
    casper.test.assertType(xpathSelector, 'object', 'ClientUtils.processSelector() can process a XPath selector');
    casper.test.assertEquals(xpathSelector.type, 'xpath', 'ClientUtils.processSelector() can process a XPath selector');
    casper.test.assertEquals(xpathSelector.path, '//li[text()="blah"]', 'ClientUtils.processSelector() can process a XPath selector');
})(casper);

(function(casper) {
    casper.start();
    // getElementBounds
    casper.then(function() {
        this.page.content = '<div id="b1" style="position:fixed;top:10px;left:11px;width:50px;height:60px"></div>';
        this.test.assertEquals(this.getElementBounds('#b1'),
            { top: 10, left: 11, width: 50, height: 60 },
            'ClientUtils.getElementBounds() retrieves element boundaries');
    });
    // getElementsBounds
    casper.start();
    casper.then(function() {
        this.test.comment('Casper.getElementsBounds()');
        var html  = '<div id="boxes">';
            html += '  <div style="position:fixed;top:10px;left:11px;width:50px;height:60px"></div>';
            html += '  <div style="position:fixed;top:20px;left:21px;width:70px;height:80px"></div>';
            html += '</div>';
        this.page.content = html;
        var bounds = this.getElementsBounds('#boxes div');
        this.test.assertEquals(bounds[0], { top: 10, left: 11, width: 50, height: 60 },
            'ClientUtils.getElementsBounds() retrieves multiple elements boundaries');
        this.test.assertEquals(bounds[1], { top: 20, left: 21, width: 70, height: 80 },
            'ClientUtils.getElementsBounds() retrieves multiple elements boundaries');
    });
})(casper);

(function(casper) {
    // element information
    casper.test.comment('ClientUtils.getElementInfo()');
    casper.page.content = '<a href="plop" class="plip plup"><i>paf</i></a>';
    var info = casper.getElementInfo('a.plip');
    casper.test.assertEquals(info.nodeName, 'a', 'ClientUtils.getElementInfo() retrieves element name');
    casper.test.assertEquals(info.attributes, {
        'href': 'plop',
        'class': 'plip plup'
    }, 'ClientUtils.getElementInfo() retrieves element attributes');
    casper.test.assertEquals(info.html, '<i>paf</i>', 'ClientUtils.getElementInfo() retrieves element html content');
    casper.test.assertEquals(info.text, 'paf', 'ClientUtils.getElementInfo() retrieves element text');
    casper.test.assert(info.x > 0, 'ClientUtils.getElementInfo() retrieves element x pos');
    casper.test.assert(info.y > 0, 'ClientUtils.getElementInfo() retrieves element y pos');
    casper.test.assert(info.width > 0, 'ClientUtils.getElementInfo() retrieves element width');
    casper.test.assert(info.height > 0, 'ClientUtils.getElementInfo() retrieves element height');
    casper.test.assert(info.visible, 'ClientUtils.getElementInfo() retrieves element visibility');
    casper.test.assertEquals(info.tag, '<a href="plop" class="plip plup"><i>paf</i></a>',
        'ClientUtils.getElementInfo() retrieves element whole tag contents');

})(casper);

casper.run(function() {
    this.test.done(40);
});
