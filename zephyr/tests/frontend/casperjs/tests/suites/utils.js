/*global casper*/
/*jshint strict:false maxstatements:99*/
var utils = require('utils'),
    t = casper.test,
    x = require('casper').selectXPath;

t.comment('betterTypeOf()');
(function() {
    var testCases = [
        {subject: 1, expected: 'number'},
        {subject: '1', expected: 'string'},
        {subject: {}, expected: 'object'},
        {subject: [], expected: 'array'},
        {subject: undefined, expected: 'undefined'},
        {subject: null, expected: 'null'},
        {subject: function(){}, expected: 'function'},
        {subject: window, expected: 'domwindow'},
        {subject: new Date(), expected: 'date'},
        {subject: new RegExp(), expected: 'regexp'}
    ];
    testCases.forEach(function(testCase) {
        t.assertEquals(utils.betterTypeOf(testCase.subject), testCase.expected,
            require('utils').format('betterTypeOf() detects expected type "%s"', testCase.subject));
    });
})();

t.comment('cleanUrl()');
(function() {
    var testCases = {
        'http://google.com/': 'http://google.com/',
        'http://google.com': 'http://google.com/',
        'http://www.google.com/': 'http://www.google.com/',
        'http://www.google.com/?plop=2': 'http://www.google.com/?plop=2',
        'https://google.com/': 'https://google.com/',
        'https://google.com': 'https://google.com/',
        'https://www.google.com/': 'https://www.google.com/',
        'https://www.google.com/?plop=2': 'https://www.google.com/?plop=2',
        'file:///Users/toto/toto.html': 'file:///Users/toto/toto.html',
        '/100': '/100'
    };
    for (var testCase in testCases) {
        t.assertEquals(utils.cleanUrl(testCase), testCases[testCase], 'cleanUrl() cleans an URL');
    }
})();

t.comment('clone()');
(function() {
    var a = {a: 1, b: 2, c: [1, 2]};
    t.assertEquals(utils.clone(a), a);
    var b = [1, 2, 3, a];
    t.assertEquals(utils.clone(b), b);
})();

t.comment('equals()');
(function() {
    t.assert(utils.equals(null, null), 'equals() null equality');
    t.assertNot(utils.equals(null, undefined), 'equals() null vs. undefined inequality');
    t.assert(utils.equals("hi", "hi"), 'equals() string equality');
    t.assertNot(utils.equals("hi", "ih"), 'equals() string inequality');
    t.assert(utils.equals(5, 5), 'equals() number equality');
    t.assertNot(utils.equals("5", 5), 'equals() number equality without implicit cast');
    t.assert(utils.equals(5, 5.0), 'equals() number equality with cast');
    t.assertNot(utils.equals(5, 10), 'equals() number inequality');
    t.assert(utils.equals([], []), 'equals() empty array equality');
    t.assert(utils.equals([1,2], [1,2]), 'equals() array equality');
    t.assert(utils.equals([1,2,[1,2,function(){}]], [1,2,[1,2,function(){}]]), 'equals() complex array equality');
    t.assertNot(utils.equals([1,2,[1,2,function(a){}]], [1,2,[1,2,function(b){}]]), 'equals() complex array inequality');
    t.assertNot(utils.equals([1,2], [2,1]), 'equals() shuffled array inequality');
    t.assertNot(utils.equals([1,2], [1,2,3]), 'equals() array length inequality');
    t.assert(utils.equals({}, {}), 'equals() empty object equality');
    t.assert(utils.equals({a:1,b:2}, {a:1,b:2}), 'equals() object length equality');
    t.assert(utils.equals({a:1,b:2}, {b:2,a:1}), 'equals() shuffled object keys equality');
    t.assertNot(utils.equals({a:1,b:2}, {a:1,b:3}), 'equals() object inequality');
    t.assert(utils.equals({1:{name:"bob",age:28}, 2:{name:"john",age:26}}, {1:{name:"bob",age:28}, 2:{name:"john",age:26}}), 'equals() complex object equality');
    t.assertNot(utils.equals({1:{name:"bob",age:28}, 2:{name:"john",age:26}}, {1:{name:"bob",age:28}, 2:{name:"john",age:27}}), 'equals() complex object inequality');
    t.assert(utils.equals(function(x){return x;}, function(x){return x;}), 'equals() function equality');
    t.assertNot(utils.equals(function(x){return x;}, function(y){return y+2;}), 'equals() function inequality');
    t.assert(utils.equals([{a:1, b:2}, {c:3, d:4}], [{a:1, b:2}, {c:3, d:4}]), 'equals() arrays of objects');
})();

t.comment('fileExt()');
(function() {
    var testCases = {
        'foo.ext':    'ext',
        'FOO.EXT':    'ext',
        'a.ext':      'ext',
        '.ext':       'ext',
        'toto.':      '',
        ' plop.ext ': 'ext'
    };

    for (var testCase in testCases) {
        t.assertEquals(utils.fileExt(testCase), testCases[testCase], 'fileExt() extract file extension');
    }
})();

t.comment('fillBlanks()');
(function() {
    var testCases = {
        'foo':         'foo       ',
        '  foo bar ':  '  foo bar ',
        '  foo bar  ': '  foo bar  '
    };

    for (var testCase in testCases) {
        t.assertEquals(utils.fillBlanks(testCase, 10), testCases[testCase], 'fillBlanks() fills blanks');
    }
})();

t.comment('getPropertyPath()');
(function() {
    var testCases = [
        {
            input:  utils.getPropertyPath({}, 'a.b.c'),
            output: undefined
        },
        {
            input:  utils.getPropertyPath([1, 2, 3], 'a.b.c'),
            output: undefined
        },
        {
            input:  utils.getPropertyPath({ a: { b: { c: 1 } }, c: 2 }, 'a.b.c'),
            output: 1
        },
        {
            input:  utils.getPropertyPath({ a: { b: { c: 1 } }, c: 2 }, 'a.b.x'),
            output: undefined
        },
        {
            input:  utils.getPropertyPath({ a: { b: { c: 1 } }, c: 2 }, 'a.b'),
            output: { c: 1 }
        },
        {
            input:  utils.getPropertyPath({ 'a-b': { 'c-d': 1} }, 'a-b.c-d'),
            output: 1
        },
        {
            input:  utils.getPropertyPath({ 'a.b': { 'c.d': 1} }, 'a.b.c.d'),
            output: undefined
        }
    ];
    testCases.forEach(function(testCase) {
        t.assertEquals(testCase.input, testCase.output, 'getPropertyPath() gets a property using a path');
    });
})();

t.comment('isArray()');
(function() {
    t.assertEquals(utils.isArray([]), true, 'isArray() checks for an Array');
    t.assertEquals(utils.isArray({}), false, 'isArray() checks for an Array');
    t.assertEquals(utils.isArray("foo"), false, 'isArray() checks for an Array');
})();

t.comment('isClipRect()');
(function() {
    var testCases = [
        [{},                                              false],
        [{top: 2},                                        false],
        [{top: 2, left: 2, width: 2, height: 2},          true],
        [{top: 2, left: 2, height: 2, width: 2},          true],
        [{top: 2, left: 2, width: 2, height: new Date()}, false]
    ];

    testCases.forEach(function(testCase) {
        t.assertEquals(utils.isClipRect(testCase[0]), testCase[1], 'isClipRect() checks for a ClipRect');
    });
})();

t.comment('isHTTPResource()');
(function() {
    var testCases = [
        [{},                              false],
        [{url: 'file:///var/www/i.html'}, false],
        [{url: 'mailto:plop@plop.com'},   false],
        [{url: 'ftp://ftp.plop.com'},     false],
        [{url: 'HTTP://plop.com/'},       true],
        [{url: 'https://plop.com/'},      true]
    ];

    testCases.forEach(function(testCase) {
        t.assertEquals(utils.isHTTPResource(testCase[0]), testCase[1], 'isHTTPResource() checks for an HTTP resource');
    });
})();

t.comment('isObject()');
(function() {
    t.assertEquals(utils.isObject({}), true, 'isObject() checks for an Object');
    t.assertEquals(utils.isObject([]), true, 'isObject() checks for an Object');
    t.assertEquals(utils.isObject(1), false, 'isObject() checks for an Object');
    t.assertEquals(utils.isObject("1"), false, 'isObject() checks for an Object');
    t.assertEquals(utils.isObject(function(){}), false, 'isObject() checks for an Object');
    t.assertEquals(utils.isObject(new Function('return {};')()), true, 'isObject() checks for an Object');
    t.assertEquals(utils.isObject(require('webpage').create()), true, 'isObject() checks for an Object');
    t.assertEquals(utils.isObject(null), false, 'isObject() checks for an Object');
})();

t.comment('isValidSelector()');
(function() {
    t.assertEquals(utils.isValidSelector({}), false, 'isValidSelector() checks for a valid selector');
    t.assertEquals(utils.isValidSelector(""), false, 'isValidSelector() checks for a valid selector');
    t.assertEquals(utils.isValidSelector("a"), true, 'isValidSelector() checks for a valid selector');
    t.assertEquals(utils.isValidSelector('div#plop form[name="form"] input[type="submit"]'), true, 'isValidSelector() checks for a valid selector');
    t.assertEquals(utils.isValidSelector(x('//a')), true, 'isValidSelector() checks for a valid selector');
    t.assertEquals(utils.isValidSelector({
        type: "css",
        path: 'div#plop form[name="form"] input[type="submit"]'
    }), true, 'isValidSelector() checks for a valid selector');
    t.assertEquals(utils.isValidSelector({
        type: "xpath",
        path: '//a'
    }), true, 'isValidSelector() checks for a valid selector');
    t.assertEquals(utils.isValidSelector({
        type: "css"
    }), false, 'isValidSelector() checks for a valid selector');
    t.assertEquals(utils.isValidSelector({
        type: "xpath"
    }), false, 'isValidSelector() checks for a valid selector');
    t.assertEquals(utils.isValidSelector({
        type: "css3",
        path: "a"
    }), false, 'isValidSelector() checks for a valid selector');
})();

t.comment('isWebPage()');
(function() {
    var pageModule = require('webpage');
    t.assertEquals(utils.isWebPage(pageModule), false, 'isWebPage() checks for a WebPage instance');
    t.assertEquals(utils.isWebPage(pageModule.create()), true, 'isWebPage() checks for a WebPage instance');
    t.assertEquals(utils.isWebPage(null), false, 'isWebPage() checks for a WebPage instance');
})();

t.comment('isJsFile()');
(function() {
    var testCases = {
        '':             false,
        'toto.png':     false,
        'plop':         false,
        'gniii.coffee': true,
        'script.js':    true
    };

    for (var testCase in testCases) {
        t.assertEquals(utils.isJsFile(testCase), testCases[testCase], 'isJsFile() checks for js file');
    }
})();

t.comment('mergeObjects()');
(function() {
    var testCases = [
        {
            obj1: {a: 1}, obj2: {b: 2}, merged: {a: 1, b: 2}
        },
        {
            obj1: {}, obj2: {a: 1}, merged: {a: 1}
        },
        {
            obj1: {}, obj2: {a: {b: 2}}, merged: {a: {b: 2}}
        },
        {
            obj1: {a: 1}, obj2: {}, merged: {a: 1}
        },
        {
            obj1: {a: 1}, obj2: {a: 2}, merged: {a: 2}
        },
        {
            obj1:   {x: 0, double: function(){return this.x*2;}},
            obj2:   {triple: function(){return this.x*3;}},
            merged: {
                x: 0,
                double: function(){return this.x*2;},
                triple: function(){return this.x*3;}
            }
        }
    ];

    testCases.forEach(function(testCase) {
        t.assertEquals(utils.mergeObjects(testCase.obj1, testCase.obj2), testCase.merged, 'mergeObjects() can merge objects');
    });
    var obj = {x: 1};
    var merged1 = utils.mergeObjects({}, {a: obj});
    var merged2 = utils.mergeObjects({a: {}}, {a: obj});
    merged1.a.x = 2;
    merged2.a.x = 2;
    t.assertEquals(obj.x, 1, 'mergeObjects() creates deep clones');
})();

t.comment('objectValues()');
(function() {
    t.assertEquals(utils.objectValues({}), [], 'objectValues() can extract object values');
    t.assertEquals(utils.objectValues({a: 1, b: 2}), [1, 2], 'objectValues() can extract object values');
})();

t.comment('unique()');
(function() {
    var testCases = [
        {
            input:  [1,2,3],
            output: [1,2,3]
        },
        {
            input:  [1,2,3,2,1],
            output: [1,2,3]
        },
        {
            input:  ["foo", "bar", "foo"],
            output: ["foo", "bar"]
        },
        {
            input:  [],
            output: []
        }
    ];
    testCases.forEach(function(testCase) {
        t.assertEquals(utils.unique(testCase.input), testCase.output, 'unique() computes unique values of an array');
    });
})();

t.comment('cmpVersion() tests');
(function() {
    t.assertEquals(utils.cmpVersion('1.0.0', '2.0.0'), -1,
        'cmpVersion() can compare version strings');
    t.assertEquals(utils.cmpVersion('1.0.0-DEV', '2.0.0-BOOM'), -1,
        'cmpVersion() can compare version strings');
    t.assertEquals(utils.cmpVersion('1.0.0', '1.1.0'), -1,
        'cmpVersion() can compare version strings');
    t.assertEquals(utils.cmpVersion('1.1.0', '1.0.0'), 1,
        'cmpVersion() can compare version strings');
    t.assertEquals(utils.cmpVersion('0.0.3', '0.0.4'), -1,
        'cmpVersion() can compare version strings');
    t.assertEquals(utils.cmpVersion('0.0.3', '1.0.3'), -1,
        'cmpVersion() can compare version strings');
    t.assertEquals(utils.cmpVersion('0.1', '1.0.3.8'), -1,
        'cmpVersion() can compare version strings');
    t.assertEquals(utils.cmpVersion({major: 1, minor: 2, patch: 3},
                                       {major: 1, minor: 2, patch: 4}), -1,
        'cmpVersion() can compare version objects');
    t.assertEquals(utils.cmpVersion({major: 2, minor: 0, patch: 3},
                                       {major: 1, minor: 0, patch: 4}), 1,
        'cmpVersion() can compare version objects');
    t.assertEquals(utils.cmpVersion({major: 0, minor: 0, patch: 3},
                                       {major: 1, minor: 0, patch: 3}), -1,
        'cmpVersion() can compare version objects');
    t.done();
})();

t.comment('gteVersion() tests');
(function() {
    t.assert(utils.gteVersion('1.1.0', '1.0.0'),
        'gteVersion() checks for a greater or equal version');
    t.assertNot(utils.gteVersion('1.0.0', '1.1.0'),
        'gteVersion() checks for a greater or equal version');
    t.assert(utils.gteVersion({major: 1, minor: 1, patch: 0},
                                 {major: 1, minor: 0, patch: 0}),
        'gteVersion() checks for a greater or equal version');
    t.assertNot(utils.gteVersion({major: 1, minor: 0, patch: 0},
                                    {major: 1, minor: 1, patch: 0}),
        'gteVersion() checks for a greater or equal version');
    t.done();
})();

t.comment('ltVersion() tests');
(function() {
    t.assert(utils.ltVersion('1.0.0', '1.1.0'),
        'ltVersion() checks for a lesser version');
    t.assertNot(utils.ltVersion('1.1.0', '1.0.0'),
        'ltVersion() checks for a lesser version');
    t.assert(utils.ltVersion({major: 1, minor: 0, patch: 0},
                                {major: 1, minor: 1, patch: 0}),
        'ltVersion() checks for a lesser version');
    t.assertNot(utils.ltVersion({major: 1, minor: 1, patch: 0},
                                   {major: 1, minor: 0, patch: 0}),
        'ltVersion() checks for a lesser version');
    t.done();
})();


t.done(132);
