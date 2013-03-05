/*!
 * Casper is a navigation utility for PhantomJS.
 *
 * Documentation: http://casperjs.org/
 * Repository:    http://github.com/n1k0/casperjs
 *
 * Copyright (c) 2011-2012 Nicolas Perriault
 *
 * Part of source code is Copyright Joyent, Inc. and other Node contributors.
 *
 * Permission is hereby granted, free of charge, to any person obtaining a
 * copy of this software and associated documentation files (the "Software"),
 * to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense,
 * and/or sell copies of the Software, and to permit persons to whom the
 * Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included
 * in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
 * OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
 * THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
 * FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
 * DEALINGS IN THE SOFTWARE.
 *
 */

/*global CasperError exports phantom require __utils__*/

var fs = require('fs');
var events = require('events');
var utils = require('utils');
var f = utils.format;

exports.create = function create(casper, options) {
    "use strict";
    return new Tester(casper, options);
};

/**
 * Casper tester: makes assertions, stores test results and display then.
 *
 * @param  Casper       casper   A valid Casper instance
 * @param  Object|null  options  Options object
 */
var Tester = function Tester(casper, options) {
    "use strict";
    /*jshint maxstatements:30*/

    if (!utils.isCasperObject(casper)) {
        throw new CasperError("Tester needs a Casper instance");
    }

    var self = this;

    this.casper = casper;

    this.SKIP_MESSAGE = '__termination__';

    this.aborted = false;
    this.executed = 0;
    this.currentTestFile = null;
    this.currentSuiteNum = 0;
    this.exporter = require('xunit').create();
    this.loadIncludes = {
        includes: [],
        pre:      [],
        post:     []
    };
    this.running = false;
    this.suites = [];
    this.options = utils.mergeObjects({
        failFast: false,  // terminates a suite as soon as a test fails?
        failText: "FAIL", // text to use for a successful test
        passText: "PASS", // text to use for a failed test
        pad:      80    , // maximum number of chars for a result line
        warnText: "WARN"  // text to use for a dubious test
    }, options);

    // properties
    this.testResults = {
        passed: 0,
        failed: 0,
        passes: [],
        failures: [],
        passesTime: [],
        failuresTime: []
    };

    // measuring test duration
    this.currentTestStartTime = new Date();
    this.lastAssertTime = 0;

    this.configure();

    this.on('success', function onSuccess(success) {
        this.testResults.passes.push(success);
        var timeElapsed = new Date() - this.currentTestStartTime;
        this.testResults.passesTime.push(timeElapsed - this.lastAssertTime);
        this.exporter.addSuccess(fs.absolute(success.file), success.message || success.standard, timeElapsed - this.lastAssertTime);
        this.lastAssertTime = timeElapsed;
    });

    this.on('fail', function onFail(failure) {
        // export
        var timeElapsed = new Date() - this.currentTestStartTime;
        this.testResults.failuresTime.push(timeElapsed - this.lastAssertTime);
        this.exporter.addFailure(
            fs.absolute(failure.file),
            failure.message  || failure.standard,
            failure.standard || "test failed",
            failure.type     || "unknown",
            (timeElapsed - this.lastAssertTime)
        );
        this.lastAssertTime = timeElapsed;
        this.testResults.failures.push(failure);

        // special printing
        if (failure.type) {
            this.comment('   type: ' + failure.type);
        }
        if (failure.values && Object.keys(failure.values).length > 0) {
            for (var name in failure.values) {
                var comment = '   ' + name + ': ';
                var value = failure.values[name];
                try {
                    comment += utils.serialize(failure.values[name]);
                } catch (e) {
                    try {
                        comment += utils.serialize(failure.values[name].toString());
                    } catch (e2) {
                        comment += '(unserializable value)';
                    }
                }
                this.comment(comment);
            }
        }
    });

    // casper events
    this.casper.on('error', function onCasperError(msg, backtrace) {
        if (!phantom.casperTest) {
            return;
        }
        if (msg === self.SKIP_MESSAGE) {
            this.warn(f('--fail-fast: aborted remaining tests in "%s"', self.currentTestFile));
            self.aborted = true;
            return self.done();
        }
        var line = 0;
        if (!utils.isString(msg)) {
            try {
                line = backtrace[0].line;
            } catch (e) {}
        }
        self.uncaughtError(msg, self.currentTestFile, line);
        self.done();
    });

    this.casper.on('step.error', function onStepError(e) {
        if (e.message !== self.SKIP_MESSAGE) {
            self.uncaughtError(e, self.currentTestFile);
        }
        self.done();
    });
};

// Tester class is an EventEmitter
utils.inherits(Tester, events.EventEmitter);
exports.Tester = Tester;

/**
 * Asserts that a condition strictly resolves to true. Also returns an
 * "assertion object" containing useful informations about the test case
 * results.
 *
 * This method is also used as the base one used for all other `assert*`
 * family methods; supplementary informations are then passed using the
 * `context` argument.
 *
 * @param  Boolean      subject  The condition to test
 * @param  String       message  Test description
 * @param  Object|null  context  Assertion context object (Optional)
 * @return Object                An assertion result object
 */
Tester.prototype.assert = Tester.prototype.assertTrue = function assert(subject, message, context) {
    "use strict";
    this.executed++;
    return this.processAssertionResult(utils.mergeObjects({
        success:  subject === true,
        type:     "assert",
        standard: "Subject is strictly true",
        message:  message,
        file:     this.currentTestFile,
        values:  {
            subject: utils.getPropertyPath(context, 'values.subject') || subject
        }
    }, context || {}));
};

/**
 * Asserts that two values are strictly equals.
 *
 * @param  Mixed   subject   The value to test
 * @param  Mixed   expected  The expected value
 * @param  String  message   Test description (Optional)
 * @return Object            An assertion result object
 */
Tester.prototype.assertEquals = Tester.prototype.assertEqual = function assertEquals(subject, expected, message) {
    "use strict";
    return this.assert(this.testEquals(subject, expected), message, {
        type:     "assertEquals",
        standard: "Subject equals the expected value",
        values:  {
            subject:  subject,
            expected: expected
        }
    });
};

/**
 * Asserts that two values are strictly not equals.
 *
 * @param  Mixed        subject   The value to test
 * @param  Mixed        expected  The unwanted value
 * @param  String|null  message   Test description (Optional)
 * @return Object                 An assertion result object
 */
Tester.prototype.assertNotEquals = function assertNotEquals(subject, shouldnt, message) {
    "use strict";
    return this.assert(!this.testEquals(subject, shouldnt), message, {
        type:    "assertNotEquals",
        standard: "Subject doesn't equal what it shouldn't be",
        values:  {
            subject:  subject,
            shouldnt: shouldnt
        }
    });
};

/**
 * Asserts that a code evaluation in remote DOM resolves to true.
 *
 * @param  Function  fn       A function to be evaluated in remote DOM
 * @param  String    message  Test description
 * @param  Object    params   Object/Array containing the parameters to inject into the function (optional)
 * @return Object             An assertion result object
 */
Tester.prototype.assertEval = Tester.prototype.assertEvaluate = function assertEval(fn, message, params) {
    "use strict";
    return this.assert(this.casper.evaluate(fn, params), message, {
        type:    "assertEval",
        standard: "Evaluated function returns true",
        values: {
            fn: fn,
            params: params
        }
    });
};

/**
 * Asserts that the result of a code evaluation in remote DOM equals
 * an expected value.
 *
 * @param  Function     fn        The function to be evaluated in remote DOM
 * @param  Boolean      expected  The expected value
 * @param  String|null  message   Test description
 * @param  Object|null  params    Object containing the parameters to inject into the function (optional)
 * @return Object                 An assertion result object
 */
Tester.prototype.assertEvalEquals = Tester.prototype.assertEvalEqual = function assertEvalEquals(fn, expected, message, params) {
    "use strict";
    var subject = this.casper.evaluate(fn, params);
    return this.assert(this.testEquals(subject, expected), message, {
        type:    "assertEvalEquals",
        standard: "Evaluated function returns the expected value",
        values:  {
            fn: fn,
            params: params,
            subject:  subject,
            expected: expected
        }
    });
};

/**
 * Asserts that a given input field has the provided value.
 *
 * @param  String   inputName  The name attribute of the input element
 * @param  String   expected   The expected value of the input element
 * @param  String   message    Test description
 * @return Object              An assertion result object
 */
Tester.prototype.assertField = function assertField(inputName, expected,  message) {
    "use strict";
    var actual = this.casper.evaluate(function(inputName) {
        return __utils__.getFieldValue(inputName);
    }, inputName);
    return this.assert(this.testEquals(actual, expected),  message, {
        type: 'assertField',
        standard: f('"%s" input field has the value "%s"', inputName, expected),
        values:  {
            inputName: inputName,
            actual: actual,
            expected:  expected
         }
    });
};

/**
 * Asserts that an element matching the provided selector expression exists in
 * remote DOM.
 *
 * @param  String   selector  Selector expression
 * @param  String   message   Test description
 * @return Object             An assertion result object
 */
Tester.prototype.assertExists = Tester.prototype.assertExist = Tester.prototype.assertSelectorExists = Tester.prototype.assertSelectorExist = function assertExists(selector, message) {
    "use strict";
    return this.assert(this.casper.exists(selector), message, {
        type: "assertExists",
        standard: f("Found an element matching: %s", selector),
        values: {
            selector: selector
        }
    });
};

/**
 * Asserts that an element matching the provided selector expression does not
 * exists in remote DOM.
 *
 * @param  String   selector  Selector expression
 * @param  String   message   Test description
 * @return Object             An assertion result object
 */
Tester.prototype.assertDoesntExist = Tester.prototype.assertNotExists = function assertDoesntExist(selector, message) {
    "use strict";
    return this.assert(!this.casper.exists(selector), message, {
        type: "assertDoesntExist",
        standard: f("No element found matching selector: %s", selector),
        values: {
            selector: selector
        }
    });
};

/**
 * Asserts that current HTTP status is the one passed as argument.
 *
 * @param  Number  status   HTTP status code
 * @param  String  message  Test description
 * @return Object           An assertion result object
 */
Tester.prototype.assertHttpStatus = function assertHttpStatus(status, message) {
    "use strict";
    var currentHTTPStatus = this.casper.currentHTTPStatus;
    return this.assert(this.testEquals(this.casper.currentHTTPStatus, status), message, {
        type: "assertHttpStatus",
        standard: f("HTTP status code is: %s", status),
        values: {
            current: currentHTTPStatus,
            expected: status
        }
    });
};

/**
 * Asserts that a provided string matches a provided RegExp pattern.
 *
 * @param  String   subject  The string to test
 * @param  RegExp   pattern  A RegExp object instance
 * @param  String   message  Test description
 * @return Object            An assertion result object
 */
Tester.prototype.assertMatch = Tester.prototype.assertMatches = function assertMatch(subject, pattern, message) {
    "use strict";
    if (utils.betterTypeOf(pattern) !== "regexp") {
        throw new CasperError('Invalid regexp.');
    }
    return this.assert(pattern.test(subject), message, {
        type: "assertMatch",
        standard: "Subject matches the provided pattern",
        values:  {
            subject: subject,
            pattern: pattern.toString()
        }
    });
};

/**
 * Asserts a condition resolves to false.
 *
 * @param  Boolean  condition  The condition to test
 * @param  String   message    Test description
 * @return Object              An assertion result object
 */
Tester.prototype.assertNot = Tester.prototype.assertFalse = function assertNot(condition, message) {
    "use strict";
    return this.assert(!condition, message, {
        type: "assertNot",
        standard: "Subject is falsy",
        values: {
            condition: condition
        }
    });
};

/**
 * Asserts that a selector expression is not currently visible.
 *
 * @param  String  expected  selector expression
 * @param  String  message   Test description
 * @return Object            An assertion result object
 */
Tester.prototype.assertNotVisible = Tester.prototype.assertInvisible = function assertNotVisible(selector, message) {
    "use strict";
    return this.assert(!this.casper.visible(selector), message, {
        type: "assertVisible",
        standard: "Selector is not visible",
        values: {
            selector: selector
        }
    });
};

/**
 * Asserts that the provided function called with the given parameters
 * will raise an exception.
 *
 * @param  Function  fn       The function to test
 * @param  Array     args     The arguments to pass to the function
 * @param  String    message  Test description
 * @return Object             An assertion result object
 */
Tester.prototype.assertRaises = Tester.prototype.assertRaise = Tester.prototype.assertThrows = function assertRaises(fn, args, message) {
    "use strict";
    var context = {
        type: "assertRaises",
        standard: "Function raises an error"
    };
    try {
        fn.apply(null, args);
        this.assert(false, message, context);
    } catch (error) {
        this.assert(true, message, utils.mergeObjects(context, {
            values: {
                error: error
            }
        }));
    }
};

/**
 * Asserts that the current page has a resource that matches the provided test
 *
 * @param  Function/String  test     A test function that is called with every response
 * @param  String           message  Test description
 * @return Object                    An assertion result object
 */
Tester.prototype.assertResourceExists = Tester.prototype.assertResourceExist = function assertResourceExists(test, message) {
    "use strict";
    return this.assert(this.casper.resourceExists(test), message, {
        type: "assertResourceExists",
        standard: "Expected resource has been found",
        values: {
            test: test
        }
    });
};

/**
 * Asserts that given text doesn't exist in the document body.
 *
 * @param  String  text     Text not to be found
 * @param  String  message  Test description
 * @return Object           An assertion result object
 */
Tester.prototype.assertTextDoesntExist = Tester.prototype.assertTextDoesntExist = function assertTextDoesntExist(text, message) {
    "use strict";
    var textFound = (this.casper.evaluate(function _evaluate() {
        return document.body.textContent || document.body.innerText;
    }).indexOf(text) === -1);
    return this.assert(textFound, message, {
        type: "assertTextDoesntExists",
        standard: "Text doesn't exist within the document body",
        values: {
            text: text
        }
    });
};

/**
 * Asserts that given text exists in the document body.
 *
 * @param  String  text     Text to be found
 * @param  String  message  Test description
 * @return Object           An assertion result object
 */
Tester.prototype.assertTextExists = Tester.prototype.assertTextExist = function assertTextExists(text, message) {
    "use strict";
    var textFound = (this.casper.evaluate(function _evaluate() {
        return document.body.textContent || document.body.innerText;
    }).indexOf(text) !== -1);
    return this.assert(textFound, message, {
        type: "assertTextExists",
        standard: "Found expected text within the document body",
        values: {
            text: text
        }
    });
};

/**
 * Asserts a subject is truthy.
 *
 * @param  Mixed   subject  Test subject
 * @param  String  message  Test description
 * @return Object           An assertion result object
 */
Tester.prototype.assertTruthy = function assertTruthy(subject, message) {
    "use strict";
    /*jshint eqeqeq:false*/
    return this.assert(utils.isTruthy(subject), message, {
        type:     "assertTruthy",
        standard: "Subject is truthy",
        values:  {
            subject: subject
        }
    });
};

/**
 * Asserts a subject is falsy.
 *
 * @param  Mixed   subject  Test subject
 * @param  String  message  Test description
 * @return Object           An assertion result object
 */
Tester.prototype.assertFalsy = function assertFalsy(subject, message) {
    "use strict";
    /*jshint eqeqeq:false*/
    return this.assert(utils.isFalsy(subject), message, {
        type:     "assertFalsy",
        standard: "Subject is falsy",
        values:  {
            subject: subject
        }
    });
};

/**
 * Asserts that given text exists in the provided selector.
 *
 * @param  String   selector  Selector expression
 * @param  String   text      Text to be found
 * @param  String   message   Test description
 * @return Object             An assertion result object
 */
Tester.prototype.assertSelectorHasText = Tester.prototype.assertSelectorContains = function assertSelectorHasText(selector, text, message) {
    "use strict";
    var textFound = this.casper.fetchText(selector).indexOf(text) !== -1;
    return this.assert(textFound, message, {
        type: "assertSelectorHasText",
        standard: f('Found "%s" within the selector "%s"', text, selector),
        values: {
            selector: selector,
            text: text
        }
    });
};

/**
 * Asserts that given text does not exist in the provided selector.
 *
 * @param  String   selector  Selector expression
 * @param  String   text      Text not to be found
 * @param  String   message   Test description
 * @return Object             An assertion result object
 */
Tester.prototype.assertSelectorDoesntHaveText = Tester.prototype.assertSelectorDoesntContain = function assertSelectorDoesntHaveText(selector, text, message) {
    "use strict";
    var textFound = this.casper.fetchText(selector).indexOf(text) === -1;
    return this.assert(textFound, message, {
        type: "assertSelectorDoesntHaveText",
        standard: f('Did not find "%s" within the selector "%s"', text, selector),
        values: {
            selector: selector,
            text: text
        }
    });
};

/**
 * Asserts that title of the remote page equals to the expected one.
 *
 * @param  String  expected  The expected title string
 * @param  String  message   Test description
 * @return Object            An assertion result object
 */
Tester.prototype.assertTitle = function assertTitle(expected, message) {
    "use strict";
    var currentTitle = this.casper.getTitle();
    return this.assert(this.testEquals(currentTitle, expected), message, {
        type: "assertTitle",
        standard: f('Page title is: "%s"', expected),
        values: {
            subject: currentTitle,
            expected: expected
        }
    });
};

/**
 * Asserts that title of the remote page matched the provided pattern.
 *
 * @param  RegExp  pattern  The pattern to test the title against
 * @param  String  message  Test description
 * @return Object           An assertion result object
 */
Tester.prototype.assertTitleMatch = Tester.prototype.assertTitleMatches = function assertTitleMatch(pattern, message) {
    "use strict";
    if (utils.betterTypeOf(pattern) !== "regexp") {
        throw new CasperError('Invalid regexp.');
    }
    var currentTitle = this.casper.getTitle();
    return this.assert(pattern.test(currentTitle), message, {
        type: "assertTitle",
        details: "Page title does not match the provided pattern",
        values: {
            subject: currentTitle,
            pattern: pattern.toString()
        }
    });
};

/**
 * Asserts that the provided subject is of the given type.
 *
 * @param  mixed   subject  The value to test
 * @param  String  type     The javascript type name
 * @param  String  message  Test description
 * @return Object           An assertion result object
 */
Tester.prototype.assertType = function assertType(subject, type, message) {
    "use strict";
    var actual = utils.betterTypeOf(subject);
    return this.assert(this.testEquals(actual, type), message, {
        type: "assertType",
        standard: f('Subject type is: "%s"', type),
        values: {
            subject: subject,
            type: type,
            actual: actual
        }
    });
};

/**
 * Asserts that a the current page url matches a given pattern. A pattern may be
 * either a RegExp object or a String. The method will test if the URL matches
 * the pattern or contains the String.
 *
 * @param  RegExp|String  pattern  The test pattern
 * @param  String         message  Test description
 * @return Object                  An assertion result object
 */
Tester.prototype.assertUrlMatch = Tester.prototype.assertUrlMatches = function assertUrlMatch(pattern, message) {
    "use strict";
    var currentUrl = this.casper.getCurrentUrl(),
        patternType = utils.betterTypeOf(pattern),
        result;
    if (patternType === "regexp") {
        result = pattern.test(currentUrl);
    } else if (patternType === "string") {
        result = currentUrl.indexOf(pattern) !== -1;
    } else {
        throw new CasperError("assertUrlMatch() only accepts strings or regexps");
    }
    return this.assert(result, message, {
        type: "assertUrlMatch",
        standard: "Current url matches the provided pattern",
        values: {
            currentUrl: currentUrl,
            pattern: pattern.toString()
        }
    });
};

/**
 * Asserts that a selector expression is currently visible.
 *
 * @param  String  expected  selector expression
 * @param  String  message   Test description
 * @return Object            An assertion result object
 */
Tester.prototype.assertVisible = function assertVisible(selector, message) {
    "use strict";
    return this.assert(this.casper.visible(selector), message, {
        type: "assertVisible",
        standard: "Selector is visible",
        values: {
            selector: selector
        }
    });
};

/**
 * Prints out a colored bar onto the console.
 *
 */
Tester.prototype.bar = function bar(text, style) {
    "use strict";
    this.casper.echo(text, style, this.options.pad);
};

/**
 * Retrieves the sum of all durations of the tests which were
 * executed in the current suite
 *
 * @return Number duration of all tests executed until now (in the current suite)
 */
Tester.prototype.calculateSuiteDuration = function calculateSuiteDuration() {
    "use strict";
    return this.testResults.passesTime.concat(this.testResults.failuresTime).reduce(function add(a, b) {
        return a + b;
    }, 0);
};

/**
 * Render a colorized output. Basically a proxy method for
 * Casper.Colorizer#colorize()
 */
Tester.prototype.colorize = function colorize(message, style) {
    "use strict";
    return this.casper.getColorizer().colorize(message, style);
};

/**
 * Writes a comment-style formatted message to stdout.
 *
 * @param  String  message
 */
Tester.prototype.comment = function comment(message) {
    "use strict";
    this.casper.echo('# ' + message, 'COMMENT');
};

/**
 * Configure casper callbacks for testing purpose.
 *
 */
Tester.prototype.configure = function configure() {
    "use strict";
    var tester = this;

    // Do not hook casper if we're not testing
    if (!phantom.casperTest) {
        return;
    }

    // specific timeout callbacks
    this.casper.options.onStepTimeout = function test_onStepTimeout(timeout, step) {
        tester.fail(f("Step timeout occured at step %s (%dms)", step, timeout));
    };

    this.casper.options.onTimeout = function test_onTimeout(timeout) {
        tester.fail(f("Timeout occured (%dms)", timeout));
    };

    this.casper.options.onWaitTimeout = function test_onWaitTimeout(timeout) {
        tester.fail(f("Wait timeout occured (%dms)", timeout));
    };
};

/**
 * Declares the current test suite done.
 *
 * @param  Number  planned  Number of planned tests
 */
Tester.prototype.done = function done(planned) {
    "use strict";
    if (planned > 0 && planned !== this.executed) {
        this.fail(f('%s: %d tests planned, %d tests executed',
            this.currentTestFile, planned, this.executed));
    }
    this.emit('test.done');
    this.running = false;
};

/**
 * Writes an error-style formatted message to stdout.
 *
 * @param  String  message
 */
Tester.prototype.error = function error(message) {
    "use strict";
    this.casper.echo(message, 'ERROR');
};

/**
 * Executes a file, wraping and evaluating its code in an isolated
 * environment where only the current `casper` instance is passed.
 *
 * @param  String  file  Absolute path to some js/coffee file
 */
Tester.prototype.exec = function exec(file) {
    "use strict";
    file = this.filter('exec.file', file) || file;
    if (!fs.isFile(file) || !utils.isJsFile(file)) {
        var e = new CasperError(f("Cannot exec %s: can only exec() files with .js or .coffee extensions", file));
        e.fileName = file;
        throw e;
    }
    this.currentTestFile = file;
    phantom.injectJs(file);
};

/**
 * Adds a failed test entry to the stack.
 *
 * @param  String  message
 */
Tester.prototype.fail = function fail(message) {
    "use strict";
    return this.assert(false, message, {
        type:    "fail",
        standard: "explicit call to fail()"
    });
};

/**
 * Recursively finds all test files contained in a given directory.
 *
 * @param  String  dir  Path to some directory to scan
 */
Tester.prototype.findTestFiles = function findTestFiles(dir) {
    "use strict";
    var self = this;
    if (!fs.isDirectory(dir)) {
        return [];
    }
    var entries = fs.list(dir).filter(function _filter(entry) {
        return entry !== '.' && entry !== '..';
    }).map(function _map(entry) {
        return fs.absolute(fs.pathJoin(dir, entry));
    });
    entries.forEach(function _forEach(entry) {
        if (fs.isDirectory(entry)) {
            entries = entries.concat(self.findTestFiles(entry));
        }
    });
    return entries.filter(function _filter(entry) {
        return utils.isJsFile(fs.absolute(fs.pathJoin(dir, entry)));
    }).sort();
};

/**
 * Formats a message to highlight some parts of it.
 *
 * @param  String  message
 * @param  String  style
 */
Tester.prototype.formatMessage = function formatMessage(message, style) {
    "use strict";
    var parts = /^([a-z0-9_\.]+\(\))(.*)/i.exec(message);
    if (!parts) {
        return message;
    }
    return this.colorize(parts[1], 'PARAMETER') + this.colorize(parts[2], style);
};

/**
 * Retrieves current failure data and all failed cases.
 *
 * @return Object casedata An object containg information about cases
 * @return Number casedata.length The number of failed cases
 * @return Array  casedata.cases An array of all the failed case objects
 */
Tester.prototype.getFailures = function getFailures() {
    "use strict";
    return {
        length: this.testResults.failed,
        cases: this.testResults.failures
    };
};

/**
 * Retrieves current passed data and all passed cases.
 *
 * @return Object casedata An object containg information about cases
 * @return Number casedata.length The number of passed cases
 * @return Array  casedata.cases An array of all the passed case objects
 */
Tester.prototype.getPasses = function getPasses() {
    "use strict";
    return {
        length: this.testResults.passed,
        cases: this.testResults.passes
    };
};

/**
 * Retrieves the array where all the durations of failed tests are stored
 *
 * @return Array durations of failed tests
 */
Tester.prototype.getFailuresTime = function getFailuresTime() {
    "use strict";
    return this.testResults.failuresTime;
}

/**
 * Retrieves the array where all the durations of passed tests are stored
 *
 * @return Array durations of passed tests
 */
Tester.prototype.getPassesTime = function getPassesTime() {
    "use strict";
    return this.testResults.passesTime;
}


/**
 * Writes an info-style formatted message to stdout.
 *
 * @param  String  message
 */
Tester.prototype.info = function info(message) {
    "use strict";
    this.casper.echo(message, 'PARAMETER');
};

/**
 * Adds a successful test entry to the stack.
 *
 * @param  String  message
 */
Tester.prototype.pass = function pass(message) {
    "use strict";
    return this.assert(true, message, {
        type:    "pass",
        standard: "explicit call to pass()"
    });
};

/**
 * Processes an assertion result by emitting the appropriate event and
 * printing result onto the console.
 *
 * @param  Object  result  An assertion result object
 * @return Object  The passed assertion result Object
 */
Tester.prototype.processAssertionResult = function processAssertionResult(result) {
    "use strict";
    var eventName= 'success',
        message = result.message || result.standard,
        style = 'INFO',
        status = this.options.passText;
    if (!result.success) {
        eventName = 'fail';
        style = 'RED_BAR';
        status = this.options.failText;
        this.testResults.failed++;
    } else {
        this.testResults.passed++;
    }
    this.casper.echo([this.colorize(status, style), this.formatMessage(message)].join(' '));
    this.emit(eventName, result);
    if (this.options.failFast && !result.success) {
        throw this.SKIP_MESSAGE;
    }
    return result;
};

/**
 * Renders a detailed report for each failed test.
 *
 * @param  Array  failures
 */
Tester.prototype.renderFailureDetails = function renderFailureDetails(failures) {
    "use strict";
    if (failures.length === 0) {
        return;
    }
    this.casper.echo(f("\nDetails for the %d failed test%s:\n", failures.length, failures.length > 1 ? "s" : ""), "PARAMETER");
    failures.forEach(function _forEach(failure) {
        var type, message, line;
        type = failure.type || "unknown";
        line = ~~failure.line;
        message = failure.message;
        this.casper.echo(f('In %s:%s', failure.file, line));
        this.casper.echo(f('   %s: %s', type, message || failure.standard || "(no message was entered)"), "COMMENT");
    }.bind(this));
};

/**
 * Render tests results, an optionally exit phantomjs.
 *
 * @param  Boolean  exit
 */
Tester.prototype.renderResults = function renderResults(exit, status, save) {
    "use strict";
    /*jshint maxstatements:20*/
    save = save || this.options.save;
    var total = this.testResults.passed + this.testResults.failed, statusText, style, result;
    var exitStatus = ~~(status || (this.testResults.failed > 0 ? 1 : 0));
    if (total === 0) {
        statusText = this.options.warnText;
        style = 'WARN_BAR';
        result = f("%s Looks like you didn't run any test.", statusText);
    } else {
        if (this.testResults.failed > 0) {
            statusText = this.options.failText;
            style = 'RED_BAR';
        } else {
            statusText = this.options.passText;
            style = 'GREEN_BAR';
        }
        result = f('%s %s tests executed in %ss, %d passed, %d failed.',
                   statusText, total, utils.ms2seconds(this.calculateSuiteDuration()),
                   this.testResults.passed, this.testResults.failed);
    }
    this.casper.echo(result, style, this.options.pad);
    if (this.testResults.failed > 0) {
        this.renderFailureDetails(this.testResults.failures);
    }
    if (save) {
        this.saveResults(save);
    }
    if (exit === true) {
        this.casper.exit(exitStatus);
    }
};

/**
 * Runs al suites contained in the paths passed as arguments.
 *
 */
Tester.prototype.runSuites = function runSuites() {
    "use strict";
    var testFiles = [], self = this;
    if (arguments.length === 0) {
        throw new CasperError("runSuites() needs at least one path argument");
    }
    this.loadIncludes.includes.forEach(function _forEachInclude(include) {
        phantom.injectJs(include);
    });

    this.loadIncludes.pre.forEach(function _forEachPreTest(preTestFile) {
        testFiles = testFiles.concat(preTestFile);
    });

    Array.prototype.forEach.call(arguments, function _forEachArgument(path) {
        if (!fs.exists(path)) {
            self.bar(f("Path %s doesn't exist", path), "RED_BAR");
        }
        if (fs.isDirectory(path)) {
            testFiles = testFiles.concat(self.findTestFiles(path));
        } else if (fs.isFile(path)) {
            testFiles.push(path);
        }
    });

    this.loadIncludes.post.forEach(function _forEachPostTest(postTestFile) {
        testFiles = testFiles.concat(postTestFile);
    });

    if (testFiles.length === 0) {
        this.bar(f("No test file found in %s, aborting.", Array.prototype.slice.call(arguments)), "RED_BAR");
        this.casper.exit(1);
    }
    self.currentSuiteNum = 0;
    self.currentTestStartTime = new Date();
    self.lastAssertTime = 0;
    var interval = setInterval(function _check(self) {
        if (self.running) {
            return;
        }
        if (self.currentSuiteNum === testFiles.length || self.aborted) {
            self.emit('tests.complete');
            clearInterval(interval);
            self.exporter.setSuiteDuration(self.calculateSuiteDuration());
            self.aborted = false;
        } else {
            self.runTest(testFiles[self.currentSuiteNum]);
            self.exporter.setSuiteDuration(self.calculateSuiteDuration());
            self.currentSuiteNum++;
            self.passesTime = [];
            self.failuresTime = [];
        }
    }, 100, this);
};

/**
 * Runs a test file
 *
 */
Tester.prototype.runTest = function runTest(testFile) {
    "use strict";
    this.bar(f('Test file: %s', testFile), 'INFO_BAR');
    this.running = true; // this.running is set back to false with done()
    this.executed = 0;
    this.exec(testFile);
};

/**
 * Saves results to file.
 *
 * @param   String  filename  Target file path.
 */
Tester.prototype.saveResults = function saveResults(filepath) {
    "use strict";
    // FIXME: looks like phantomjs has a pb with fs.isWritable https://groups.google.com/forum/#!topic/casperjs/hcUdwgGZOrU
    // if (!fs.isWritable(filepath)) {
    //     throw new CasperError(f('Path %s is not writable.', filepath));
    // }
    try {
        fs.write(filepath, this.exporter.getXML(), 'w');
        this.casper.echo(f('Result log stored in %s', filepath), 'INFO', 80);
    } catch (e) {
        this.casper.echo(f('Unable to write results to %s: %s', filepath, e), 'ERROR', 80);
    }
};

/**
 * Tests equality between the two passed arguments.
 *
 * @param  Mixed  v1
 * @param  Mixed  v2
 * @param  Boolean
 */
Tester.prototype.testEquals = Tester.prototype.testEqual = function testEquals(v1, v2) {
    "use strict";
    return utils.equals(v1, v2);
};

/**
 * Processes an error caught while running tests contained in a given test
 * file.
 *
 * @param  Error|String  error      The error
 * @param  String        file       Test file where the error occurred
 * @param  Number        line       Line number (optional)
 */
Tester.prototype.uncaughtError = function uncaughtError(error, file, line) {
    "use strict";
    return this.processAssertionResult({
        success: false,
        type: "uncaughtError",
        file: file,
        line: ~~line || "unknown",
        message: utils.isObject(error) ? error.message : error,
        values: {
            error: error
        }
    });
};
