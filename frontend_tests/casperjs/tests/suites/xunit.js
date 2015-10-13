/*global casper*/
/*jshint strict:false*/
casper.test.comment('phantom.Casper.XUnitExporter');

var xunit = require('xunit').create();
xunit.addSuccess('foo', 'bar');
casper.test.assertMatch(xunit.getXML(),
    /<testcase classname="foo" name="bar"/,
    'XUnitExporter.addSuccess() adds a successful testcase');
xunit.addFailure('bar', 'baz', 'wrong', 'chucknorriz');
casper.test.assertMatch(xunit.getXML(),
    /<testcase classname="bar" name="baz"><failure type="chucknorriz">wrong/,
    'XUnitExporter.addFailure() adds a failed testcase');

// named classname
xunit = require('xunit').create();
xunit.addSuccess(require('fs').workingDirectory + '/plop.js', 'It worked');
casper.test.assertMatch(xunit.getXML(),
    /<testcase classname="(.*)plop" name="It worked"/,
    'XUnitExporter.addSuccess() handles class name');
xunit.addSuccess(require('fs').workingDirectory + '/plip.js', 'Failure');
casper.test.assertMatch(xunit.getXML(),
    /<testcase classname="(.*)plip" name="Failure"/,
    'XUnitExporter.addFailure() handles class name');

// named with time
xunit = require('xunit').create();
xunit.addSuccess('foo', 'It worked', 1024);
casper.test.assertMatch(xunit.getXML(),
    /<testcase classname="foo" name="It worked" time="(.*)"/,
    'XUnitExporter.addSuccess() writes duration of test');
xunit.addFailure('bar', 'baz', 'wrong', 'chucknorriz', 1024);
casper.test.assertMatch(xunit.getXML(),
    /<testcase classname="bar" name="baz" time="(.*)"><failure type="chucknorriz">wrong/,
    'XUnitExporter.addFailure() adds a failed testcase with duration');

// named with time
xunit = require('xunit').create();
casper.test.assertMatch(xunit.getXML(),
    /<testsuite>/,
    'XUnitExporter.create() created <testsuite> without time');
xunit.setSuiteDuration(1024);
casper.test.assertMatch(xunit.getXML(),
    /<testsuite time="1.024">/,
    'XUnitExporter.setSuiteDuration() sets time in seconds');

casper.test.done(8);
