/*global casper*/
/*jshint strict:false maxstatements:99*/
var fs = require('fs');
var t = casper.test;

casper.start();

t.comment('Tester.sortFiles()');
var testDirRoot = fs.pathJoin(phantom.casperPath, 'tests', 'testdir');
var files = t.findTestFiles(testDirRoot);
var expected = [
    "01_a/abc.js",
    "01_a/def.js",
    "02_b/abc.js",
    "03_a.js",
    "03_b.js",
    "04/01_init.js",
    "04/02_do.js"
].map(function(entry) {
    return fs.pathJoin.apply(fs, [testDirRoot].concat(entry.split('/')));
});
t.assertEquals(files, expected, 'findTestFiles() find test files and sort them');

casper.thenOpen('tests/site/index.html', function() {
    t.comment('Tester.assertTextExists()');
    t.assertTextExists('form', 'Tester.assertTextExists() checks that page body contains text');

    t.comment('Tester.assertTextExist()');
    t.assertTextExist('form', 'Tester.assertTextExist() checks that page body contains text [alias]');

    t.comment('Tester.assertTextDoesntExist()');
    t.assertTextDoesntExist('blah', "Tester.assertTextDoesntExist() checks that page body doesn't contain provided text");

    t.comment('Tester.assertSelectorHasText()');
    t.assertSelectorHasText('h1', 'Title', 'Tester.assertSelectorHasText() works as expected');

    t.comment('Tester.assertSelectorDoesntHaveText()');
    t.assertSelectorDoesntHaveText('h1', 'Subtitle', 'Tester.assertSelectorDoesntHaveText() works as expected');

    t.comment('Tester.assert()');
    t.assert(true, 'Tester.assert() works as expected');

    t.comment('Tester.assertTrue()');
    t.assertTrue(true, 'Tester.assertTrue() works as expected [alias]');

    t.comment('Tester.assertTruthy()');
    t.assertTruthy('1', 'Tester.assertTruthy() works as expected');

    t.comment('Tester.assertFalsy()');
    t.assertFalsy('', 'Tester.assertFalsy() works as expected');

    t.comment('Tester.assertNot()');
    t.assertNot(false, 'Tester.assertNot() works as expected');

    t.comment('Tester.assertEquals()');
    t.assertEquals(true, true, 'Tester.assertEquals() works as expected');

    t.comment('Tester.assertEqual()');
    t.assertEqual(true, true, 'Tester.assertEqual() works as expected [alias]');

    t.comment('Tester.assertNotEquals()');
    t.assertNotEquals(true, false, 'Tester.assertNotEquals() works as expected');

    t.comment('Tester.assertEval()');
    t.assertEval(function() {
        return true;
    }, 'Tester.assertEval() works as expected');

    t.comment('Tester.assertEvaluate()');
    t.assertEvaluate(function() {
        return true;
    }, 'Tester.assertEvaluate() works as expected [alias]');

    t.comment('Tester.assertEvalEquals()');
    t.assertEvalEquals(function() {
        return 42;
    }, 42, 'Tester.assertEvalEquals() works as expected');

    t.comment('Tester.assertEvalEqual()');
    t.assertEvalEqual(function() {
        return 42;
    }, 42, 'Tester.assertEvalEqual() works as expected [alias]');

    t.comment('Tester.assertExists()');
    t.assertExists('body', 'Tester.assertExists() works as expected');

    t.comment('Tester.assertExist()');
    t.assertExist('body', 'Tester.assertExist() works as expected [alias]');

    t.comment('Tester.assertSelectorExists()');
    t.assertSelectorExists('body', 'Tester.assertSelectorExists() works as expected [alias]');

    t.comment('Tester.assertSelectorExists()');
    t.assertSelectorExist('body', 'Tester.assertSelectorExist() works as expected [alias]');

    t.comment('Tester.assertDoesntExist()');
    t.assertDoesntExist('foobar', 'Tester.assertDoesntExist() works as expected');

    t.comment('Tester.assertNotExist()');
    t.assertDoesntExist('foobar', 'Tester.assertNotExist() works as expected [alias]');

    t.comment('Tester.assertHttpStatus()');
    // using file:// protocol, HTTP status is always null
    t.assertHttpStatus(200, 'Tester.assertHttpStatus() works as expected');

    t.comment('Tester.assertMatch()');
    t.assertMatch("the lazy dog", /lazy/, 'Tester.assertMatch() works as expected');

    t.comment('Tester.assertMatches()');
    t.assertMatches("the lazy dog", /lazy/, 'Tester.assertMatches() works as expected [alias]');

    t.comment('Tester.assertRaises()');
    t.assertRaises(function() {
        throw new Error('plop');
    }, [], 'Tester.assertRaises() works as expected');

    t.comment('Tester.assertRaise()');
    t.assertRaise(function() {
        throw new Error('plop');
    }, [], 'Tester.assertRaise() works as expected [alias]');

    t.comment('Tester.assertThrows()');
    t.assertThrows(function() {
        throw new Error('plop');
    }, [], 'Tester.assertThrows() works as expected [alias]');

    t.comment('Tester.assertResourceExists()');
    t.assertResourceExists(/index\.html/, 'Tester.assertResourceExists() works as expected');

    t.comment('Tester.assertResourceExist()');
    t.assertResourceExist(/index\.html/, 'Tester.assertResourceExist() works as expected [alias]');

    t.comment('Tester.assertTitle()');
    t.assertTitle('CasperJS test index', 'Tester.assertTitle() works as expected');

    t.comment('Tester.assertTitleMatch()');
    t.assertTitleMatch(/test index/, 'Tester.assertTitleMatch() works as expected');

    t.comment('Tester.assertTitleMatches()');
    t.assertTitleMatches(/test index/, 'Tester.assertTitleMatches() works as expected [alias]');

    t.comment('Tester.assertType()');
    t.assertType("plop", "string", "Tester.assertType() works as expected");

    t.comment('Tester.assertUrlMatch()');
    t.assertUrlMatch(/index\.html$/, "Tester.assertUrlMatch() works as expected");

    t.comment('Tester.assertUrlMatches()');
    t.assertUrlMatches(/index\.html$/, "Tester.assertUrlMatches() works as expected [alias]");

    t.comment('Tester.assertVisible()');
    t.assertVisible('img', 'Tester.assertVisible() works as expected');

    t.comment('Tester.assertNotVisible()');
    t.assertNotVisible('p#hidden', 'Tester.assertNotVisible() works as expected');

    t.comment('Tester.assertInvisible()');
    t.assertInvisible('p#hidden', 'Tester.assertInvisible() works as expected [alias]');
});

casper.thenOpen('tests/site/form.html', function() {
    t.comment('Tester.assertField()');
    t.comment('1. Fill inputs');
    var fpath = phantom.libraryPath + '/README.md';
    this.fill('form[action="result.html"]', {
        'email':       'chuck@norris.com',
        'content':     'Am watching thou',
        'check':       true,
        'choice':      'no',
        'topic':       'bar',
        'file':        fpath,
        'checklist[]': ['1', '3']
    });
    t.assertField('email', 'chuck@norris.com', 'Tester.assertField() works as expected with inputs');
    t.assertField('content', 'Am watching thou', 'Tester.assertField() works as expected with textarea');
    t.assertField('check', true, 'Tester.assertField() works as expected with checkboxes');
    t.assertField('choice', 'no', 'Tester.assertField() works as expected with radios');
    t.assertField('topic', 'bar', 'Tester.assertField() works as expected with selects');
    t.assertField('file', 'C:\\fakepath\\README.md', 'Tester.assertField() works as expected with file inputs');
    t.assertField('checklist[]', ['1', '3'], 'Tester.assertField() works as expected with check lists');
});

casper.reload(function() {
    t.comment('2. Unfill inputs');
    this.fill('form[action="result.html"]', {
        'email':       '',
        'content':     '',
        'check':       false,
        'choice':      '',
        'topic':       '',
        'file':        '',
        'checklist[]': []
    });
    t.assertField('email', '', 'Tester.assertField() works as expected with inputs');
    t.assertField('content', '', 'Tester.assertField() works as expected with textarea');
    t.assertField('check', false, 'Tester.assertField() works as expected with checkboxes');
    t.assertField('choice', null, 'Tester.assertField() works as expected with radios');
    t.assertField('topic', 'foo', 'Tester.assertField() works as expected with selects');
    t.assertField('file', '', 'Tester.assertField() works as expected with file inputs');
    t.assertField('checklist[]', [], 'Tester.assertField() works as expected with check lists');
});

casper.then(function() {
    t.comment('Tester.getFailures()');
    t.assertEquals(typeof t.getFailures().length, "number", "Tester.getFailures() works as expected");

    var passCount = t.getPasses().length;
    t.comment('Tester.getPasses()');
    t.assertEquals(1, 1, "Rogue assertEquals pass case");
    t.assertEquals(t.getPasses().length, passCount + 1, "Tester.getPasses() works as expected");
});

casper.then(function() {
    t.comment('Tester.calculateSuiteDuration()');
    function add(a, b) {
        return a + b;
    }
    var passedTime = t.getPassesTime().reduce(add, 0),
        failedTime = t.getFailuresTime().reduce(add, 0),
        calculatedSum = t.calculateSuiteDuration();
    t.assertEquals(calculatedSum, passedTime + failedTime, "Tester.calculateSuiteDuration() works as expected")
});

casper.run(function() {
    t.done(59);
});
