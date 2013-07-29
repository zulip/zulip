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

var utils = require('utils');

/*
 * Building an Array subclass
 */
function responseHeaders(){}
responseHeaders.prototype = [];

/**
 * Retrieves a given header based on its name
 *
 * @param   String  name    A case-insensitive response header name
 * @return  mixed   A header string or `null` if not found
 */
responseHeaders.prototype.get = function get(name){
    "use strict";
    var headerValue = null;
    name = name.toLowerCase();
    this.some(function(header){
        if (header.name.toLowerCase() === name){
            headerValue = header.value;
            return true;
        }
    });
    return headerValue;
};

/**
 * Augment the response with proper prototypes
 *
 * @param mixed response    Phantom response or undefined (generally with local files)
 */
exports.augmentResponse = function(response) {
    "use strict";
    /*jshint proto:true*/
    if (!utils.isHTTPResource(response)) {
        return;
    }
    response.headers.__proto__ = responseHeaders.prototype;
};
