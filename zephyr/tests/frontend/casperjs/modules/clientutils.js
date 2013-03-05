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

/*global console escape exports NodeList window*/

(function(exports) {
    "use strict";

    exports.create = function create(options) {
        return new this.ClientUtils(options);
    };

    /**
     * Casper client-side helpers.
     */
    exports.ClientUtils = function ClientUtils(options) {
        /*jshint maxstatements:40*/
        // private members
        var BASE64_ENCODE_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
        var BASE64_DECODE_CHARS = new Array(
            -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 62, -1, -1, -1, 63,
            52, 53, 54, 55, 56, 57, 58, 59, 60, 61, -1, -1, -1, -1, -1, -1,
            -1,  0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14,
            15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, -1, -1, -1, -1, -1,
            -1, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40,
            41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, -1, -1, -1, -1, -1
        );
        var SUPPORTED_SELECTOR_TYPES = ['css', 'xpath'];

        // public members
        this.options = options || {};
        this.options.scope = this.options.scope || document;
        /**
         * Clicks on the DOM element behind the provided selector.
         *
         * @param  String  selector  A CSS3 selector to the element to click
         * @return Boolean
         */
        this.click = function click(selector) {
            return this.mouseEvent('click', selector);
        };

        /**
         * Decodes a base64 encoded string. Succeeds where window.atob() fails.
         *
         * @param  String  str  The base64 encoded contents
         * @return string
         */
        this.decode = function decode(str) {
            /*jshint maxstatements:30 maxcomplexity:30 */
            var c1, c2, c3, c4, i = 0, len = str.length, out = "";
            while (i < len) {
                do {
                    c1 = BASE64_DECODE_CHARS[str.charCodeAt(i++) & 0xff];
                } while (i < len && c1 === -1);
                if (c1 === -1) {
                    break;
                }
                do {
                    c2 = BASE64_DECODE_CHARS[str.charCodeAt(i++) & 0xff];
                } while (i < len && c2 === -1);
                if (c2 === -1) {
                    break;
                }
                out += String.fromCharCode((c1 << 2) | ((c2 & 0x30) >> 4));
                do {
                    c3 = str.charCodeAt(i++) & 0xff;
                    if (c3 === 61)
                    return out;
                    c3 = BASE64_DECODE_CHARS[c3];
                } while (i < len && c3 === -1);
                if (c3 === -1) {
                    break;
                }
                out += String.fromCharCode(((c2 & 0XF) << 4) | ((c3 & 0x3C) >> 2));
                do {
                    c4 = str.charCodeAt(i++) & 0xff;
                    if (c4 === 61) {
                        return out;
                    }
                    c4 = BASE64_DECODE_CHARS[c4];
                } while (i < len && c4 === -1);
                if (c4 === -1) {
                    break;
                }
                out += String.fromCharCode(((c3 & 0x03) << 6) | c4);
            }
            return out;
        };

        /**
         * Echoes something to casper console.
         *
         * @param  String  message
         * @return
         */
        this.echo = function echo(message) {
            console.log("[casper.echo] " + message);
        };

        /**
         * Base64 encodes a string, even binary ones. Succeeds where
         * window.btoa() fails.
         *
         * @param  String  str  The string content to encode
         * @return string
         */
        this.encode = function encode(str) {
            /*jshint maxstatements:30 */
            var out = "", i = 0, len = str.length, c1, c2, c3;
            while (i < len) {
                c1 = str.charCodeAt(i++) & 0xff;
                if (i === len) {
                    out += BASE64_ENCODE_CHARS.charAt(c1 >> 2);
                    out += BASE64_ENCODE_CHARS.charAt((c1 & 0x3) << 4);
                    out += "==";
                    break;
                }
                c2 = str.charCodeAt(i++);
                if (i === len) {
                    out += BASE64_ENCODE_CHARS.charAt(c1 >> 2);
                    out += BASE64_ENCODE_CHARS.charAt(((c1 & 0x3)<< 4) | ((c2 & 0xF0) >> 4));
                    out += BASE64_ENCODE_CHARS.charAt((c2 & 0xF) << 2);
                    out += "=";
                    break;
                }
                c3 = str.charCodeAt(i++);
                out += BASE64_ENCODE_CHARS.charAt(c1 >> 2);
                out += BASE64_ENCODE_CHARS.charAt(((c1 & 0x3) << 4) | ((c2 & 0xF0) >> 4));
                out += BASE64_ENCODE_CHARS.charAt(((c2 & 0xF) << 2) | ((c3 & 0xC0) >> 6));
                out += BASE64_ENCODE_CHARS.charAt(c3 & 0x3F);
            }
            return out;
        };

        /**
         * Checks if a given DOM element exists in remote page.
         *
         * @param  String  selector  CSS3 selector
         * @return Boolean
         */
        this.exists = function exists(selector) {
            try {
                return this.findAll(selector).length > 0;
            } catch (e) {
                return false;
            }
        };

        /**
         * Fetches innerText within the element(s) matching a given CSS3
         * selector.
         *
         * @param  String  selector  A CSS3 selector
         * @return String
         */
        this.fetchText = function fetchText(selector) {
            var text = '', elements = this.findAll(selector);
            if (elements && elements.length) {
                Array.prototype.forEach.call(elements, function _forEach(element) {
                    text += element.textContent || element.innerText;
                });
            }
            return text;
        };

        /**
         * Fills a form with provided field values, and optionnaly submits it.
         *
         * @param  HTMLElement|String  form  A form element, or a CSS3 selector to a form element
         * @param  Object              vals  Field values
         * @return Object                    An object containing setting result for each field, including file uploads
         */
        this.fill = function fill(form, vals) {
            /*jshint maxcomplexity:8*/
            var out = {
                errors: [],
                fields: [],
                files:  []
            };
            if (!(form instanceof HTMLElement) || typeof form === "string") {
                this.log("attempting to fetch form element from selector: '" + form + "'", "info");
                try {
                    form = this.findOne(form);
                } catch (e) {
                    if (e.name === "SYNTAX_ERR") {
                        out.errors.push("invalid form selector provided: '" + form + "'");
                        return out;
                    }
                }
            }
            if (!form) {
                out.errors.push("form not found");
                return out;
            }
            for (var name in vals) {
                if (!vals.hasOwnProperty(name)) {
                    continue;
                }
                var field = this.findAll('[name="' + name + '"]', form);
                var value = vals[name];
                if (!field || field.length === 0) {
                    out.errors.push('no field named "' + name + '" in form');
                    continue;
                }
                try {
                    out.fields[name] = this.setField(field, value);
                } catch (err) {
                    if (err.name === "FileUploadError") {
                        out.files.push({
                            name: name,
                            path: err.path
                        });
                    } else if(err.name === "FieldNotFound") {
                        out.errors.push('Form field named "' + name + '" was not found.');
                    } else {
                        out.errors.push(err.toString());
                    }
                }
            }
            return out;
        };

        /**
         * Finds all DOM elements matching by the provided selector.
         *
         * @param  String            selector  CSS3 selector
         * @param  HTMLElement|null  scope     Element to search child elements within
         * @return NodeList|undefined
         */
        this.findAll = function findAll(selector, scope) {
            scope = scope || this.options.scope;
            try {
                var pSelector = this.processSelector(selector);
                if (pSelector.type === 'xpath') {
                    return this.getElementsByXPath(pSelector.path, scope);
                } else {
                    return scope.querySelectorAll(pSelector.path);
                }
            } catch (e) {
                this.log('findAll(): invalid selector provided "' + selector + '":' + e, "error");
            }
        };

        /**
         * Finds a DOM element by the provided selector.
         *
         * @param  String            selector  CSS3 selector
         * @param  HTMLElement|null  scope     Element to search child elements within
         * @return HTMLElement|undefined
         */
        this.findOne = function findOne(selector, scope) {
            scope = scope || this.options.scope;
            try {
                var pSelector = this.processSelector(selector);
                if (pSelector.type === 'xpath') {
                    return this.getElementByXPath(pSelector.path, scope);
                } else {
                    return scope.querySelector(pSelector.path);
                }
            } catch (e) {
                this.log('findOne(): invalid selector provided "' + selector + '":' + e, "error");
            }
        };

        /**
         * Downloads a resource behind an url and returns its base64-encoded
         * contents.
         *
         * @param  String  url     The resource url
         * @param  String  method  The request method, optional (default: GET)
         * @param  Object  data    The request data, optional
         * @return String          Base64 contents string
         */
        this.getBase64 = function getBase64(url, method, data) {
            return this.encode(this.getBinary(url, method, data));
        };

        /**
         * Retrieves string contents from a binary file behind an url. Silently
         * fails but log errors.
         *
         * @param   String   url     Url.
         * @param   String   method  HTTP method.
         * @param   Object   data    Request parameters.
         * @return  String
         */
        this.getBinary = function getBinary(url, method, data) {
            try {
                return this.sendAJAX(url, method, data, false);
            } catch (e) {
                if (e.name === "NETWORK_ERR" && e.code === 101) {
                    this.log("getBinary(): Unfortunately, casperjs cannot make cross domain ajax requests", "warning");
                }
                this.log("getBinary(): Error while fetching " + url + ": " + e, "error");
                return "";
            }
        };

        /**
         * Retrieves total document height.
         * http://james.padolsey.com/javascript/get-document-height-cross-browser/
         *
         * @return {Number}
         */
        this.getDocumentHeight = function getDocumentHeight() {
            return Math.max(
                Math.max(document.body.scrollHeight, document.documentElement.scrollHeight),
                Math.max(document.body.offsetHeight, document.documentElement.offsetHeight),
                Math.max(document.body.clientHeight, document.documentElement.clientHeight)
            );
        };

        /**
         * Retrieves bounding rect coordinates of the HTML element matching the
         * provided CSS3 selector in the following form:
         *
         * {top: y, left: x, width: w, height:, h}
         *
         * @param  String  selector
         * @return Object or null
         */
        this.getElementBounds = function getElementBounds(selector) {
            try {
                var clipRect = this.findOne(selector).getBoundingClientRect();
                return {
                    top:    clipRect.top,
                    left:   clipRect.left,
                    width:  clipRect.width,
                    height: clipRect.height
                };
            } catch (e) {
                this.log("Unable to fetch bounds for element " + selector, "warning");
            }
        };

        /**
         * Retrieves the list of bounding rect coordinates for all the HTML elements matching the
         * provided CSS3 selector, in the following form:
         *
         * [{top: y, left: x, width: w, height:, h},
         *  {top: y, left: x, width: w, height:, h},
         *  ...]
         *
         * @param  String  selector
         * @return Array
         */
        this.getElementsBounds = function getElementsBounds(selector) {
            var elements = this.findAll(selector);
            var self = this;
            try {
                return Array.prototype.map.call(elements, function(element) {
                    var clipRect = element.getBoundingClientRect();
                    return {
                        top:    clipRect.top,
                        left:   clipRect.left,
                        width:  clipRect.width,
                        height: clipRect.height
                    };
                });
            } catch (e) {
                this.log("Unable to fetch bounds for elements matching " + selector, "warning");
            }
        };

        /**
         * Retrieves information about the node matching the provided selector.
         *
         * @param  String|Object  selector  CSS3/XPath selector
         * @return Object
         */
        this.getElementInfo = function getElementInfo(selector) {
            var element = this.findOne(selector);
            var bounds = this.getElementBounds(selector);
            var attributes = {};
            [].forEach.call(element.attributes, function(attr) {
                attributes[attr.name.toLowerCase()] = attr.value;
            });
            return {
                nodeName: element.nodeName.toLowerCase(),
                attributes: attributes,
                tag: element.outerHTML,
                html: element.innerHTML,
                text: element.innerText,
                x: bounds.left,
                y: bounds.top,
                width: bounds.width,
                height: bounds.height,
                visible: this.visible(selector)
            };
        };

        /**
         * Retrieves a single DOM element matching a given XPath expression.
         *
         * @param  String            expression  The XPath expression
         * @param  HTMLElement|null  scope       Element to search child elements within
         * @return HTMLElement or null
         */
        this.getElementByXPath = function getElementByXPath(expression, scope) {
            scope = scope || this.options.scope;
            var a = document.evaluate(expression, scope, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
            if (a.snapshotLength > 0) {
                return a.snapshotItem(0);
            }
        };

        /**
         * Retrieves all DOM elements matching a given XPath expression.
         *
         * @param  String            expression  The XPath expression
         * @param  HTMLElement|null  scope       Element to search child elements within
         * @return Array
         */
        this.getElementsByXPath = function getElementsByXPath(expression, scope) {
            scope = scope || this.options.scope;
            var nodes = [];
            var a = document.evaluate(expression, scope, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
            for (var i = 0; i < a.snapshotLength; i++) {
                nodes.push(a.snapshotItem(i));
            }
            return nodes;
        };

        /**
         * Retrieves the value of a form field.
         *
         * @param  String  inputName  The for input name attr value
         * @return Mixed
         */
        this.getFieldValue = function getFieldValue(inputName) {
            function getSingleValue(input) {
                try {
                    type = input.getAttribute('type').toLowerCase();
                } catch (e) {
                    type = 'other';
                }
                if (['checkbox', 'radio'].indexOf(type) === -1) {
                    return input.value;
                }
                // single checkbox or… radio button (weird, I know)
                if (input.hasAttribute('value')) {
                    return input.checked ? input.getAttribute('value') : undefined;
                }
                return input.checked;
            }
            function getMultipleValues(inputs) {
                type = inputs[0].getAttribute('type').toLowerCase();
                if (type === 'radio') {
                    var value;
                    [].forEach.call(inputs, function(radio) {
                        value = radio.checked ? radio.value : value;
                    });
                    return value;
                } else if (type === 'checkbox') {
                    var values = [];
                    [].forEach.call(inputs, function(checkbox) {
                        if (checkbox.checked) {
                            values.push(checkbox.value);
                        }
                    });
                    return values;
                }
            }
            var inputs = this.findAll('[name="' + inputName + '"]'), type;
            switch (inputs.length) {
                case 0:  return null;
                case 1:  return getSingleValue(inputs[0]);
                default: return getMultipleValues(inputs);
            }
        };

        /**
         * Retrieves a given form all of its field values.
         *
         * @param  String  selector  A DOM CSS3/XPath selector
         * @return Object
         */
        this.getFormValues = function getFormValues(selector) {
            var form = this.findOne(selector);
            var values = {};
            var self = this;
            [].forEach.call(form.elements, function(element) {
                var name = element.getAttribute('name');
                if (name && !values[name]) {
                    values[name] = self.getFieldValue(name);
                }
            });
            return values;
        };

        /**
         * Logs a message. Will format the message a way CasperJS will be able
         * to log phantomjs side.
         *
         * @param  String  message  The message to log
         * @param  String  level    The log level
         */
        this.log = function log(message, level) {
            console.log("[casper:" + (level || "debug") + "] " + message);
        };

        /**
         * Dispatches a mouse event to the DOM element behind the provided selector.
         *
         * @param  String   type     Type of event to dispatch
         * @param  String  selector  A CSS3 selector to the element to click
         * @return Boolean
         */
        this.mouseEvent = function mouseEvent(type, selector) {
            var elem = this.findOne(selector);
            if (!elem) {
                this.log("mouseEvent(): Couldn't find any element matching '" + selector + "' selector", "error");
                return false;
            }
            try {
                var evt = document.createEvent("MouseEvents");
                var center_x = 1, center_y = 1;
                try {
                    var pos = elem.getBoundingClientRect();
                    center_x = Math.floor((pos.left + pos.right) / 2),
                    center_y = Math.floor((pos.top + pos.bottom) / 2);
                } catch(e) {}
                evt.initMouseEvent(type, true, true, window, 1, 1, 1, center_x, center_y, false, false, false, false, 0, elem);
                // dispatchEvent return value is false if at least one of the event
                // handlers which handled this event called preventDefault;
                // so we cannot returns this results as it cannot accurately informs on the status
                // of the operation
                // let's assume the event has been sent ok it didn't raise any error
                elem.dispatchEvent(evt);
                return true;
            } catch (e) {
                this.log("Failed dispatching " + type + "mouse event on " + selector + ": " + e, "error");
                return false;
            }
        };

        /**
         * Processes a selector input, either as a string or an object.
         *
         * If passed an object, if must be of the form:
         *
         *     selectorObject = {
         *         type: <'css' or 'xpath'>,
         *         path: <a string>
         *     }
         *
         * @param  String|Object  selector  The selector string or object
         *
         * @return an object containing 'type' and 'path' keys
         */
        this.processSelector = function processSelector(selector) {
            var selectorObject = {
                toString: function toString() {
                    return this.type + ' selector: ' + this.path;
                }
            };
            if (typeof selector === "string") {
                // defaults to CSS selector
                selectorObject.type = "css";
                selectorObject.path = selector;
                return selectorObject;
            } else if (typeof selector === "object") {
                // validation
                if (!selector.hasOwnProperty('type') || !selector.hasOwnProperty('path')) {
                    throw new Error("Incomplete selector object");
                } else if (SUPPORTED_SELECTOR_TYPES.indexOf(selector.type) === -1) {
                    throw new Error("Unsupported selector type: " + selector.type);
                }
                if (!selector.hasOwnProperty('toString')) {
                    selector.toString = selectorObject.toString;
                }
                return selector;
            }
            throw new Error("Unsupported selector type: " + typeof selector);
        };

        /**
         * Removes all DOM elements matching a given XPath expression.
         *
         * @param  String  expression  The XPath expression
         * @return Array
         */
        this.removeElementsByXPath = function removeElementsByXPath(expression) {
            var a = document.evaluate(expression, document, null, XPathResult.UNORDERED_NODE_SNAPSHOT_TYPE, null);
            for (var i = 0; i < a.snapshotLength; i++) {
                a.snapshotItem(i).parentNode.removeChild(a.snapshotItem(i));
            }
        };

        /**
         * Performs an AJAX request.
         *
         * @param   String   url     Url.
         * @param   String   method  HTTP method (default: GET).
         * @param   Object   data    Request parameters.
         * @param   Boolean  async   Asynchroneous request? (default: false)
         * @return  String           Response text.
         */
        this.sendAJAX = function sendAJAX(url, method, data, async) {
            var xhr = new XMLHttpRequest(),
                dataString = "",
                dataList = [];
            method = method && method.toUpperCase() || "GET";
            xhr.open(method, url, !!async);
            this.log("sendAJAX(): Using HTTP method: '" + method + "'", "debug");
            xhr.overrideMimeType("text/plain; charset=x-user-defined");
            if (method === "POST") {
                if (typeof data === "object") {
                    for (var k in data) {
                        dataList.push(encodeURIComponent(k) + "=" + encodeURIComponent(data[k].toString()));
                    }
                    dataString = dataList.join('&');
                    this.log("sendAJAX(): Using request data: '" + dataString + "'", "debug");
                } else if (typeof data === "string") {
                    dataString = data;
                }
                xhr.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");
            }
            xhr.send(method === "POST" ? dataString : null);
            return xhr.responseText;
        };

        /**
         * Sets a field (or a set of fields) value. Fails silently, but log
         * error messages.
         *
         * @param  HTMLElement|NodeList  field  One or more element defining a field
         * @param  mixed                 value  The field value to set
         */
        this.setField = function setField(field, value) {
            /*jshint maxcomplexity:99 */
            var logValue, fields, out;
            value = logValue = (value || "");
            if (field instanceof NodeList) {
                fields = field;
                field = fields[0];
            }
            if (!(field instanceof HTMLElement)) {
                var error = new Error('Invalid field type; only HTMLElement and NodeList are supported');
                error.name = 'FieldNotFound';
                throw error;
            }
            if (this.options && this.options.safeLogs && field.getAttribute('type') === "password") {
                // obfuscate password value
                logValue = new Array(value.length + 1).join("*");
            }
            this.log('Set "' + field.getAttribute('name') + '" field value to ' + logValue, "debug");
            try {
                field.focus();
            } catch (e) {
                this.log("Unable to focus() input field " + field.getAttribute('name') + ": " + e, "warning");
            }
            var nodeName = field.nodeName.toLowerCase();
            switch (nodeName) {
                case "input":
                    var type = field.getAttribute('type') || "text";
                    switch (type.toLowerCase()) {
                        case "color":
                        case "date":
                        case "datetime":
                        case "datetime-local":
                        case "email":
                        case "hidden":
                        case "month":
                        case "number":
                        case "password":
                        case "range":
                        case "search":
                        case "tel":
                        case "text":
                        case "time":
                        case "url":
                        case "week":
                            field.value = value;
                            break;
                        case "checkbox":
                            if (fields.length > 1) {
                                var values = value;
                                if (!Array.isArray(values)) {
                                    values = [values];
                                }
                                Array.prototype.forEach.call(fields, function _forEach(f) {
                                    f.checked = values.indexOf(f.value) !== -1 ? true : false;
                                });
                            } else {
                                field.checked = value ? true : false;
                            }
                            break;
                        case "file":
                            throw {
                                name:    "FileUploadError",
                                message: "File field must be filled using page.uploadFile",
                                path:    value
                            };
                        case "radio":
                            if (fields) {
                                Array.prototype.forEach.call(fields, function _forEach(e) {
                                    e.checked = (e.value === value);
                                });
                            } else {
                                out = 'Provided radio elements are empty';
                            }
                            break;
                        default:
                            out = "Unsupported input field type: " + type;
                            break;
                    }
                    break;
                case "select":
                case "textarea":
                    field.value = value;
                    break;
                default:
                    out = 'Unsupported field type: ' + nodeName;
                    break;
            }

            // firing the `change` and `input` events
            ['change', 'input'].forEach(function(name) {
                var event = document.createEvent("HTMLEvents");
                event.initEvent(name, true, true);
                field.dispatchEvent(event);
            });

            // blur the field
            try {
                field.blur();
            } catch (err) {
                this.log("Unable to blur() input field " + field.getAttribute('name') + ": " + err, "warning");
            }
            return out;
        };

        /**
         * Checks if a given DOM element is visible in remote page.
         *
         * @param  String  selector  CSS3 selector
         * @return Boolean
         */
        this.visible = function visible(selector) {
            try {
                var comp,
                    el = this.findOne(selector);

                if (el) {
                    comp = window.getComputedStyle(el, null);
                    return comp.visibility !== 'hidden' && comp.display !== 'none' && el.offsetHeight > 0 && el.offsetWidth > 0;
                }
                return false;
            } catch (e) {
                return false;
            }
        };
    };
})(typeof exports === "object" ? exports : window);
