/*jshint strict:false*/
/*global CasperError casper console phantom require*/
var pagestack = require('pagestack');
var utils = require('utils');
var webpage = require('webpage');
var t = casper.test;
var stack = pagestack.create();


var page1 = webpage.create();
page1.url = 'page1.html';
stack.push(page1);
t.assertEquals(stack.length, 1);
t.assert(utils.isWebPage(stack[0]));
t.assertEquals(stack[0], page1);
t.assertEquals(stack.list().length, 1);
t.assertEquals(stack.list()[0], page1.url);

var page2 = webpage.create();
page2.url = 'page2.html';
stack.push(page2);
t.assertEquals(stack.length, 2);
t.assert(utils.isWebPage(stack[1]));
t.assertEquals(stack[1], page2);
t.assertEquals(stack.list().length, 2);
t.assertEquals(stack.list()[1], page2.url);

t.assertEquals(stack.clean(page1), 1);
t.assertEquals(stack[0], page2);
t.assertEquals(stack.list().length, 1);
t.assertEquals(stack.list()[0], page2.url);

casper.test.done();
