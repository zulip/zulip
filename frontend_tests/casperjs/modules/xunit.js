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

/*global CasperError console exports phantom require*/

var utils = require('utils');
var fs = require('fs');

/**
 * Generates a value for 'classname' attribute of the JUnit XML report.
 *
 * Uses the (relative) file name of the current casper script without file
 * extension as classname.
 *
 * @param  String  classname
 * @return String
 */
function generateClassName(classname) {
    "use strict";
    classname = classname.replace(phantom.casperPath, "").trim();
    var script = classname || phantom.casperScript || "";
    if (script.indexOf(fs.workingDirectory) === 0) {
        script = script.substring(fs.workingDirectory.length + 1);
    }
    if (script.indexOf('/') === 0) {
        script = script.substring(1, script.length);
    }
    if (~script.indexOf('.')) {
        script = script.substring(0, script.lastIndexOf('.'));
    }

    // If we have trimmed our string down to nothing, default to script name
    if (!script && phantom.casperScript) {
      script = phantom.casperScript;
    }

    return script || "unknown";
}

/**
 * Creates a XUnit instance
 *
 * @return XUnit
 */
exports.create = function create() {
    "use strict";
    return new XUnitExporter();
};

/**
 * JUnit XML (xUnit) exporter for test results.
 *
 */
function XUnitExporter() {
    "use strict";
    this._xml = utils.node('testsuite');
    this._xml.toString = function toString() {
        return this.outerHTML; // ouch
    };
}
exports.XUnitExporter = XUnitExporter;

/**
 * Adds a successful test result.
 *
 * @param  String  classname
 * @param  String  name
 * @param  Number  duration  Test duration in milliseconds
 */
XUnitExporter.prototype.addSuccess = function addSuccess(classname, name, duration) {
    "use strict";
    var snode = utils.node('testcase', {
        classname: generateClassName(classname),
        name: name
    });
    if (duration !== undefined) {
        snode.setAttribute('time', utils.ms2seconds(duration));
    }
    this._xml.appendChild(snode);
};

/**
 * Adds a failed test result.
 *
 * @param  String  classname
 * @param  String  name
 * @param  String  message
 * @param  String  type
 * @param  Number  duration  Test duration in milliseconds
 */
XUnitExporter.prototype.addFailure = function addFailure(classname, name, message, type, duration) {
    "use strict";
    var fnode = utils.node('testcase', {
        classname: generateClassName(classname),
        name:      name
    });
    if (duration !== undefined) {
        fnode.setAttribute('time', utils.ms2seconds(duration));
    }
    var failure = utils.node('failure', {
        type: type || "unknown"
    });
    failure.appendChild(document.createTextNode(message || "no message left"));
    fnode.appendChild(failure);
    this._xml.appendChild(fnode);
};

/**
 * Adds test suite duration
 *
 * @param  Number  duration  Test duration in milliseconds
 */
XUnitExporter.prototype.setSuiteDuration = function setSuiteDuration(duration) {
    "use strict";
    if (!isNaN(duration)) {
        this._xml.setAttribute("time", utils.ms2seconds(duration));
    }
};

/**
 * Retrieves generated XML object - actually an HTMLElement.
 *
 * @return HTMLElement
 */
XUnitExporter.prototype.getXML = function getXML() {
    "use strict";
    return this._xml;
};
