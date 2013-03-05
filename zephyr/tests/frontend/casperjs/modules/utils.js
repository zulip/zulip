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

/**
 * Provides a better typeof operator equivalent, able to retrieve the array
 * type.
 *
 * CAVEAT: this function does not necessarilly map to classical js "type" names,
 * notably a `null` will map to "null" instead of "object".
 *
 * @param  mixed  input
 * @return String
 * @see    http://javascriptweblog.wordpress.com/2011/08/08/fixing-the-javascript-typeof-operator/
 */
function betterTypeOf(input) {
    "use strict";
    switch (input) {
        case undefined:
            return 'undefined';
        case null:
            return 'null';
        default:
        try {
            return Object.prototype.toString.call(input).match(/^\[object\s(.*)\]$/)[1].toLowerCase();
        } catch (e) {
            return typeof input;
        }
    }
}
exports.betterTypeOf = betterTypeOf;

/**
 * Cleans a passed URL if it lacks a slash at the end when a sole domain is used.
 *
 * @param  String  url An HTTP URL
 * @return String
 */
function cleanUrl(url) {
    "use strict";
    var parts = /(https?):\/\/(.*)/i.exec(url);
    if (!parts) {
        return url;
    }
    var protocol = parts[1];
    var subparts = parts[2].split('/');
    if (subparts.length === 1) {
        return format("%s://%s/", protocol, subparts[0]);
    }
    return url;
}
exports.cleanUrl = cleanUrl;

/**
 * Clones an object.
 *
 * @param  Mixed  o
 * @return Mixed
 */
function clone(o) {
    "use strict";
    return JSON.parse(JSON.stringify(o));
}
exports.clone = clone;

/**
 * Dumps a JSON representation of passed value to the console. Used for
 * debugging purpose only.
 *
 * @param  Mixed  value
 */
function dump(value) {
    "use strict";
    console.log(serialize(value, 4));
}
exports.dump = dump;

/**
 * Tests equality between the two passed arguments.
 *
 * @param  Mixed  v1
 * @param  Mixed  v2
 * @param  Boolean
 */
function equals(v1, v2) {
    "use strict";
    if (isFunction(v1)) {
        return v1.toString() === v2.toString();
    }
    if (v1 instanceof Object) {
        if (Object.keys(v1).length !== Object.keys(v2).length) {
            return false;
        }
        for (var k in v1) {
            if (!equals(v1[k], v2[k])) {
                return false;
            }
        }
        return true;
    }
    return v1 === v2;
}
exports.equals = equals;

/**
 * Returns the file extension in lower case.
 *
 * @param  String  file  File path
 * @return string
 */
function fileExt(file) {
    "use strict";
    try {
        return file.split('.').pop().toLowerCase().trim();
    } catch(e) {
        return '';
    }
}
exports.fileExt = fileExt;

/**
 * Takes a string and append blanks until the pad value is reached.
 *
 * @param  String  text
 * @param  Number  pad   Pad value (optional; default: 80)
 * @return String
 */
function fillBlanks(text, pad) {
    "use strict";
    pad = pad || 80;
    if (text.length < pad) {
        text += new Array(pad - text.length + 1).join(' ');
    }
    return text;
}
exports.fillBlanks = fillBlanks;

/**
 * Formats a string with passed parameters. Ported from nodejs `util.format()`.
 *
 * @return String
 */
function format(f) {
    "use strict";
    var i = 1;
    var args = arguments;
    var len = args.length;
    var str = String(f).replace(/%[sdj%]/g, function _replace(x) {
        if (i >= len) return x;
        switch (x) {
        case '%s':
            return String(args[i++]);
        case '%d':
            return Number(args[i++]);
        case '%j':
            return JSON.stringify(args[i++]);
        case '%%':
            return '%';
        default:
            return x;
        }
    });
    for (var x = args[i]; i < len; x = args[++i]) {
        if (x === null || typeof x !== 'object') {
            str += ' ' + x;
        } else {
            str += '[obj]';
        }
    }
    return str;
}
exports.format = format;

/**
 * Retrieves the value of an Object foreign property using a dot-separated
 * path string.
 *
 * Beware, this function doesn't handle object key names containing a dot.
 *
 * @param  Object  obj   The source object
 * @param  String  path  Dot separated path, eg. "x.y.z"
 */
function getPropertyPath(obj, path) {
    "use strict";
    if (!isObject(obj) || !isString(path)) {
        return undefined;
    }
    var value = obj;
    path.split('.').forEach(function(property) {
        if (typeof value === "object" && property in value) {
            value = value[property];
        } else {
            value = undefined;
        }
    });
    return value;
}
exports.getPropertyPath = getPropertyPath;

/**
 * Inherit the prototype methods from one constructor into another.
 *
 * @param {function} ctor Constructor function which needs to inherit the
 *     prototype.
 * @param {function} superCtor Constructor function to inherit prototype from.
 */
function inherits(ctor, superCtor) {
    "use strict";
    ctor.super_ = ctor.__super__ = superCtor;
    ctor.prototype = Object.create(superCtor.prototype, {
        constructor: {
            value: ctor,
            enumerable: false,
            writable: true,
            configurable: true
        }
    });
}
exports.inherits = inherits;

/**
 * Checks if value is a javascript Array
 *
 * @param  mixed  value
 * @return Boolean
 */
function isArray(value) {
    "use strict";
    return Array.isArray(value) || isType(value, "array");
}
exports.isArray = isArray;

/**
 * Checks if passed argument is an instance of Capser object.
 *
 * @param  mixed  value
 * @return Boolean
 */
function isCasperObject(value) {
    "use strict";
    return value instanceof require('casper').Casper;
}
exports.isCasperObject = isCasperObject;

/**
 * Checks if value is a phantomjs clipRect-compatible object
 *
 * @param  mixed  value
 * @return Boolean
 */
function isClipRect(value) {
    "use strict";
    return isType(value, "cliprect") || (
        isObject(value) &&
        isNumber(value.top) && isNumber(value.left) &&
        isNumber(value.width) && isNumber(value.height)
    );
}
exports.isClipRect = isClipRect;

/**
 * Checks that the subject is falsy.
 *
 * @param  Mixed  subject  Test subject
 * @return Boolean
 */
function isFalsy(subject) {
    "use strict";
    /*jshint eqeqeq:false*/
    return !subject;
}
exports.isFalsy = isFalsy;
/**
 * Checks if value is a javascript Function
 *
 * @param  mixed  value
 * @return Boolean
 */
function isFunction(value) {
    "use strict";
    return isType(value, "function");
}
exports.isFunction = isFunction;

/**
 * Checks if passed resource involves an HTTP url.
 *
 * @param  Object  resource The PhantomJS HTTP resource object
 * @return Boolean
 */
function isHTTPResource(resource) {
    "use strict";
    return isObject(resource) && /^http/i.test(resource.url);
}
exports.isHTTPResource = isHTTPResource;

/**
 * Checks if a file is apparently javascript compatible (.js or .coffee).
 *
 * @param  String  file  Path to the file to test
 * @return Boolean
 */
function isJsFile(file) {
    "use strict";
    var ext = fileExt(file);
    return isString(ext, "string") && ['js', 'coffee'].indexOf(ext) !== -1;
}
exports.isJsFile = isJsFile;

/**
 * Checks if the provided value is null
 *
 * @return Boolean
 */
function isNull(value) {
    "use strict";
    return isType(value, "null");
}
exports.isNull = isNull;

/**
 * Checks if value is a javascript Number
 *
 * @param  mixed  value
 * @return Boolean
 */
function isNumber(value) {
    "use strict";
    return isType(value, "number");
}
exports.isNumber = isNumber;

/**
 * Checks if value is a javascript Object
 *
 * @param  mixed  value
 * @return Boolean
 */
function isObject(value) {
    "use strict";
    var objectTypes = ["array", "object", "qtruntimeobject"];
    return objectTypes.indexOf(betterTypeOf(value)) >= 0;
}
exports.isObject = isObject;

/**
 * Checks if value is a RegExp
 *
 * @param  mixed  value
 * @return Boolean
 */
function isRegExp(value) {
    "use strict";
    return isType(value, "regexp");
}
exports.isRegExp = isRegExp;

/**
 * Checks if value is a javascript String
 *
 * @param  mixed  value
 * @return Boolean
 */
function isString(value) {
    "use strict";
    return isType(value, "string");
}
exports.isString = isString;

/**
 * Checks that the subject is truthy.
 *
 * @param  Mixed  subject  Test subject
 * @return Boolean
 */
function isTruthy(subject) {
    "use strict";
    /*jshint eqeqeq:false*/
    return !!subject;
}
exports.isTruthy = isTruthy;

/**
 * Shorthands for checking if a value is of the given type. Can check for
 * arrays.
 *
 * @param  mixed   what      The value to check
 * @param  String  typeName  The type name ("string", "number", "function", etc.)
 * @return Boolean
 */
function isType(what, typeName) {
    "use strict";
    if (typeof typeName !== "string" || !typeName) {
        throw new CasperError("You must pass isType() a typeName string");
    }
    return betterTypeOf(what).toLowerCase() === typeName.toLowerCase();
}
exports.isType = isType;

/**
 * Checks if the provided value is undefined
 *
 * @return Boolean
 */
function isUndefined(value) {
    "use strict";
    return isType(value, "undefined");
}
exports.isUndefined = isUndefined;

/**
 * Checks if value is a valid selector Object.
 *
 * @param  mixed  value
 * @return Boolean
 */
function isValidSelector(value) {
    "use strict";
    if (isString(value)) {
        try {
            // phantomjs env has a working document object, let's use it
            document.querySelector(value);
        } catch(e) {
            if ('name' in e && e.name === 'SYNTAX_ERR') {
                return false;
            }
        }
        return true;
    } else if (isObject(value)) {
        if (!value.hasOwnProperty('type')) {
            return false;
        }
        if (!value.hasOwnProperty('path')) {
            return false;
        }
        if (['css', 'xpath'].indexOf(value.type) === -1) {
            return false;
        }
        return true;
    }
    return false;
}
exports.isValidSelector = isValidSelector;

/**
 * Checks if the provided var is a WebPage instance
 *
 * @param  mixed  what
 * @return Boolean
 */
function isWebPage(what) {
    "use strict";
    return betterTypeOf(what) === "qtruntimeobject" && what.objectName === 'WebPage';
}
exports.isWebPage = isWebPage;

/**
 * Object recursive merging utility.
 *
 * @param  Object  origin  the origin object
 * @param  Object  add     the object to merge data into origin
 * @return Object
 */
function mergeObjects(origin, add) {
    "use strict";
    for (var p in add) {
        if (add[p] && add[p].constructor === Object) {
            if (origin[p] && origin[p].constructor === Object) {
                origin[p] = mergeObjects(origin[p], add[p]);
            } else {
                origin[p] = clone(add[p]);
            }
        } else {
            origin[p] = add[p];
        }
    }
    return origin;
}
exports.mergeObjects = mergeObjects;

/**
 * Converts milliseconds to seconds and rounds the results to 3 digits accuracy.
 *
 * @param  Number  milliseconds
 * @return Number  seconds
 */
function ms2seconds(milliseconds) {
    "use strict";
    return Math.round(milliseconds / 1000 * 1000) / 1000;
}
exports.ms2seconds = ms2seconds;

/**
 * Creates an (SG|X)ML node element.
 *
 * @param  String  name        The node name
 * @param  Object  attributes  Optional attributes
 * @return HTMLElement
 */
function node(name, attributes) {
    "use strict";
    var _node   = document.createElement(name);
    for (var attrName in attributes) {
        var value = attributes[attrName];
        if (attributes.hasOwnProperty(attrName) && isString(attrName)) {
            _node.setAttribute(attrName, value);
        }
    }
    return _node;
}
exports.node = node;

/**
 * Maps an object to an array made from its values.
 *
 * @param  Object  obj
 * @return Array
 */
function objectValues(obj) {
    "use strict";
    return Object.keys(obj).map(function(arg) {
        return obj[arg];
    });
}
exports.objectValues = objectValues;

/**
 * Serializes a value using JSON.
 *
 * @param  Mixed  value
 * @return String
 */
function serialize(value, indent) {
    "use strict";
    if (isArray(value)) {
        value = value.map(function _map(prop) {
            return isFunction(prop) ? prop.toString().replace(/\s{2,}/, '') : prop;
        });
    }
    return JSON.stringify(value, null, indent);
}
exports.serialize = serialize;

/**
 * Returns unique values from an array.
 *
 * Note: ugly code is ugly, but efficient: http://jsperf.com/array-unique2/8
 *
 * @param  Array  array
 * @return Array
 */
function unique(array) {
    "use strict";
    var o = {},
        r = [];
    for (var i = 0, len = array.length; i !== len; i++) {
        var d = array[i];
        if (o[d] !== 1) {
            o[d] = 1;
            r[r.length] = d;
        }
    }
    return r;
}
exports.unique = unique;

/**
 * Compare two version numbers represented as strings.
 *
 * @param  String  a  Version a
 * @param  String  b  Version b
 * @return Number
 */
function cmpVersion(a, b) {
    "use strict";
    var i, cmp, len, re = /(\.0)+[^\.]*$/;
    function versionToString(version) {
        if (isObject(version)) {
            try {
                return [version.major, version.minor, version.patch].join('.');
            } catch (e) {}
        }
        return version;
    }
    a = versionToString(a);
    b = versionToString(b);
    a = (a + '').replace(re, '').split('.');
    b = (b + '').replace(re, '').split('.');
    len = Math.min(a.length, b.length);
    for (i = 0; i < len; i++) {
        cmp = parseInt(a[i], 10) - parseInt(b[i], 10);
        if (cmp !== 0) {
            return cmp;
        }
    }
    return a.length - b.length;
}
exports.cmpVersion = cmpVersion;

/**
 * Checks if a version number string is greater or equals another.
 *
 * @param  String  a  Version a
 * @param  String  b  Version b
 * @return Boolean
 */
function gteVersion(a, b) {
    "use strict";
    return cmpVersion(a, b) >= 0;
}
exports.gteVersion = gteVersion;

/**
 * Checks if a version number string is less than another.
 *
 * @param  String  a  Version a
 * @param  String  b  Version b
 * @return Boolean
 */
function ltVersion(a, b) {
    "use strict";
    return cmpVersion(a, b) < 0;
}
exports.ltVersion = ltVersion;
