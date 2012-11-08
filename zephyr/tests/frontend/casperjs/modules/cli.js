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

var system = require('system');
var utils = require('utils');

/**
 * Extracts, normalize ad organize PhantomJS CLI arguments in a dedicated
 * Object.
 *
 * @param  array  phantomArgs  system.args value
 * @return Object
 */
exports.parse = function parse(phantomArgs) {
    "use strict";
    var extract = {
        args: [],
        options: {},
        raw: {
            args: [],
            options: {}
        },
        drop: function drop(what) {
            if (utils.isNumber(what)) {
                // deleting an arg by its position
                this.args = this.args.filter(function _filter(arg, index) {
                    return index !== what;
                });
            } else if (utils.isString(what)) {
                // deleting an arg by its value
                this.args = this.args.filter(function _filter(arg) {
                    return arg !== what;
                });
                // deleting an option by its name (key)
                var self = this;
                Object.keys(this.options).forEach(function _forEach(option) {
                    if (option === what) {
                        delete self.options[what];
                    }
                });
            } else {
                throw new CasperError("cannot drop argument of type " + typeof what);
            }
        },
        has: function has(what) {
            if (utils.isNumber(what)) {
                return what in this.args;
            } else if (utils.isString(what)) {
                return what in this.options;
            } else {
                throw new CasperError("Unsupported cli arg tester " + typeof what);
            }
        },
        get: function get(what) {
            if (utils.isNumber(what)) {
                return this.args[what];
            } else if (utils.isString(what)) {
                return this.options[what];
            } else {
                throw new CasperError("Unsupported cli arg getter " + typeof what);
            }
        }
    };
    phantomArgs.forEach(function _forEach(arg) {
        if (arg.indexOf('--') === 0) {
            // named option
            var optionMatch = arg.match(/^--(.*?)=(.*)/i);
            if (optionMatch) {
                extract.options[optionMatch[1]] = castArgument(optionMatch[2]);
                extract.raw.options[optionMatch[1]] = optionMatch[2];
            } else {
                // flag
                var flagMatch = arg.match(/^--(.*)/);
                if (flagMatch) {
                    extract.options[flagMatch[1]] = extract.raw.options[flagMatch[1]] = true;
                }
            }
        } else {
            // positional arg
            extract.args.push(castArgument(arg));
            extract.raw.args.push(castArgument(arg));
        }
    });
    extract.raw = utils.mergeObjects(extract.raw, {
        drop: extract.drop,
        has: extract.has,
        get: extract.get
    });
    return extract;
};

/**
 * Cast a string argument to its typed equivalent.
 *
 * @param  String  arg
 * @return Mixed
 */
function castArgument(arg) {
    "use strict";
    if (arg.match(/^-?\d+$/)) {
        return parseInt(arg, 10);
    } else if (arg.match(/^-?\d+\.\d+$/)) {
        return parseFloat(arg);
    } else if (arg.match(/^(true|false)$/i)) {
        return arg.trim().toLowerCase() === "true" ? true : false;
    } else {
        return arg;
    }
}
