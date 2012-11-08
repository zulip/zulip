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

/*global CasperError console encodeURIComponent escape exports require*/

// WARNING: this module is deprecated since CasperJS 1.0.0-RC3

var utils = require('utils');

exports.create = function create(fn) {
    "use strict";
    return new FunctionArgsInjector(fn);
};

/**
 * Function argument injector.
 *
 * FIXME: use new Function() instead of eval()
 */
var FunctionArgsInjector = function FunctionArgsInjector(fn) {
    "use strict";
    console.error('Warning: the injector module has been deprecated.');

    if (!utils.isFunction(fn)) {
        throw new CasperError("FunctionArgsInjector() can only process functions");
    }
    this.fn = fn;

    this.extract = function extract(fn) {
        var match = /^function\s?(\w+)?\s?\((.*)\)\s?\{([\s\S]*)\}/i.exec(fn.toString().trim());
        if (match && match.length > 1) {
            var args = match[2].split(',').map(function _map(arg) {
                return arg.replace(new RegExp(/\/\*+.*\*\//ig), "").trim();
            }).filter(function _filter(arg) {
                return arg;
            }) || [];
            return {
                name: match[1] ? match[1].trim() : null,
                args: args,
                body: match[3] ? match[3].trim() : ''
            };
        }
    };

    this.process = function process(values) {
        var fnObj = this.extract(this.fn);
        if (!utils.isObject(fnObj)) {
            throw new CasperError("Unable to process function " + this.fn.toString());
        }
        var inject = this.getArgsInjectionString(fnObj.args, values);
        var newFn = new Function([inject, fnObj.body].join('\n'));
        newFn.name = fnObj.name || '';
        return newFn;
    };

    this.getArgsInjectionString = function getArgsInjectionString(args, values) {
        values = typeof values === "object" ? values : {};
        var jsonValues = escape(encodeURIComponent(JSON.stringify(values)));
        var inject = [
            'var __casper_params__ = JSON.parse(decodeURIComponent(unescape(\'' + jsonValues + '\')));'
        ];
        args.forEach(function _forEach(arg) {
            if (arg in values) {
                inject.push('var ' + arg + '=__casper_params__["' + arg + '"];');
            }
        });
        return inject.join('\n') + '\n';
    };
};
exports.FunctionArgsInjector = FunctionArgsInjector;
