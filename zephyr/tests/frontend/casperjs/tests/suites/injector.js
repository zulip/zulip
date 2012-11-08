/*global casper*/
/*jshint strict:false*/
var t = casper.test;
var createInjector = function(fn, values) {
    return require('injector').create(fn, values);
};
var testFn = function(a, b) { return a + b; };
var injector = createInjector(testFn);
var extract = injector.extract(testFn);

t.comment('FunctionArgsInjector.extract()');
t.assertType(extract, "object", 'FunctionArgsInjector.extract() returns an object');
t.assertEquals(extract.name, null, 'FunctionArgsInjector.extract() process function name as expected');
t.assertEquals(extract.body, 'return a + b;', 'FunctionArgsInjector.extract() process function body as expected');
t.assertEquals(extract.args, ['a', 'b'], 'FunctionArgsInjector.extract() process function args as expected');

function Plop(foo, bar) {
    return 'foo: ' + foo +', bar: ' + bar;
}
function Plip() { return 'plop'; }
function foo_bar(boz) {}
var gni = function ($bubu_bibi, __popo__) {};
var gno = function    (  arg1,    /*plop*/ arg2  ) {    };
function issue129(term) {
    // see issue #129
    return term;
    // see issue #129
}
t.assertEquals(injector.extract(Plop), {
    name: 'Plop',
    args: ['foo', 'bar'],
    body: "return 'foo: ' + foo +', bar: ' + bar;"
}, 'FunctionArgsInjector.extract() handles named functions with arguments and body');
t.assertEquals(injector.extract(Plip), {
    name: 'Plip',
    args: [],
    body: "return 'plop';"
}, 'FunctionArgsInjector.extract() handles functions with no arguments');
t.assertEquals(injector.extract(foo_bar), {
    name: 'foo_bar',
    args: ['boz'],
    body: ""
}, 'FunctionArgsInjector.extract() handles functions with no body');
t.assertEquals(injector.extract(gni), {
    name: null,
    args: ['$bubu_bibi', '__popo__'],
    body: ""
}, 'FunctionArgsInjector.extract() handles anonymous functions with complex args passed');
t.assertEquals(injector.extract(gno), {
    name: null,
    args: ['arg1', 'arg2'],
    body: ""
}, 'FunctionArgsInjector.extract() handles can filter comments in function args');

t.comment('FunctionArgsInjector.process()');
var processed;
eval('processed = ' + injector.process({ a: 1, b: 2 }));

t.assertType(processed, "function", 'FunctionArgsInjector.process() processed a function');
t.assertEquals(processed(), 3, 'FunctionArgsInjector.process() processed the function correctly');

// Issue #129
var fnIssue129 = createInjector(issue129).process({term: 'fixed'});
t.assertEquals(fnIssue129('fixed'), 'fixed', 'FunctionArgsInjector.process() has issue #129 fixed');

t.done();
