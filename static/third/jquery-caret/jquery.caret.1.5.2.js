/*! jQuery Caret Plugin - v1.5.2 - 2014-03-25
 * https://github.com/acdvorak/jquery.caret
 * Copyright (c) 2012-2014 Andrew C. Dvorak; Licensed MIT */
(function($, undefined) {

    var _input = document.createElement('input');

    var _support = {
        setSelectionRange: ('setSelectionRange' in _input) || ('selectionStart' in _input),
        createTextRange: ('createTextRange' in _input) || ('selection' in document)
    };

    var _rNewlineIE = /\r\n/g,
        _rCarriageReturn = /\r/g;

    var _getValue = function(input) {
        if (typeof(input.value) !== 'undefined') {
            return input.value;
        }
        return $(input).text();
    };

    var _setValue = function(input, value) {
        if (typeof(input.value) !== 'undefined') {
            input.value = value;
        } else {
            $(input).text(value);
        }
    };

    var _getIndex = function(input, pos) {
        var norm = _getValue(input).replace(_rCarriageReturn, '');
        var len = norm.length;

        if (typeof(pos) === 'undefined') {
            pos = len;
        }

        pos = Math.floor(pos);

        // Negative index counts backward from the end of the input/textarea's value
        if (pos < 0) {
            pos = len + pos;
        }

        // Enforce boundaries
        if (pos < 0) { pos = 0; }
        if (pos > len) { pos = len; }

        return pos;
    };

    var _hasAttr = function(input, attrName) {
        return input.hasAttribute ? input.hasAttribute(attrName) : (typeof(input[attrName]) !== 'undefined');
    };

    /**
     * @class
     * @constructor
     */
    var Range = function(start, end, length, text) {
        this.start = start || 0;
        this.end = end || 0;
        this.length = length || 0;
        this.text = text || '';
    };

    Range.prototype.toString = function() {
        return JSON.stringify(this, null, '    ');
    };

    var _getCaretW3 = function(input) {
        return input.selectionStart;
    };

    /**
     * @see http://stackoverflow.com/q/6943000/467582
     */
    var _getCaretIE = function(input) {
        var caret, range, textInputRange, rawValue, len, endRange;

        // Yeah, you have to focus twice for IE 7 and 8.  *cries*
        input.focus();
        input.focus();

        range = document.selection.createRange();

        if (range && range.parentElement() === input) {
            rawValue = _getValue(input);

            len = rawValue.length;

            // Create a working TextRange that lives only in the input
            textInputRange = input.createTextRange();
            textInputRange.moveToBookmark(range.getBookmark());

            // Check if the start and end of the selection are at the very end
            // of the input, since moveStart/moveEnd doesn't return what we want
            // in those cases
            endRange = input.createTextRange();
            endRange.collapse(false);

            if (textInputRange.compareEndPoints("StartToEnd", endRange) > -1) {
                caret = rawValue.replace(_rNewlineIE, '\n').length;
            } else {
                caret = -textInputRange.moveStart("character", -len);
            }

            return caret;
        }

        // NOTE: This occurs when you highlight part of a textarea and then click in the middle of the highlighted portion in IE 6-10.
        //       There doesn't appear to be anything we can do about it.
//        alert("Your browser is incredibly stupid.  I don't know what else to say.");
//        alert(range + '\n\n' + range.parentElement().tagName + '#' + range.parentElement().id);

        return 0;
    };

    /**
     * Gets the position of the caret in the given input.
     * @param {HTMLInputElement|HTMLTextAreaElement} input input or textarea element
     * @returns {Number}
     * @see http://stackoverflow.com/questions/263743/how-to-get-cursor-position-in-textarea/263796#263796
     */
    var _getCaret = function(input) {
        if (!input) {
            return undefined;
        }

        // Mozilla, et al.
        if (_support.setSelectionRange) {
            return _getCaretW3(input);
        }
        // IE
        else if (_support.createTextRange) {
            return _getCaretIE(input);
        }

        return undefined;
    };

    var _setCaretW3 = function(input, pos) {
        input.setSelectionRange(pos, pos);
    };

    var _setCaretIE = function(input, pos) {
        var range = input.createTextRange();
        range.move('character', pos);
        range.select();
    };

    /**
     * Sets the position of the caret in the given input.
     * @param {HTMLInputElement|HTMLTextAreaElement} input input or textarea element
     * @param {Number} pos
     * @see http://parentnode.org/javascript/working-with-the-cursor-position/
     */
    var _setCaret = function(input, pos) {
        input.focus();

        pos = _getIndex(input, pos);

        // Mozilla, et al.
        if (_support.setSelectionRange) {
            _setCaretW3(input, pos);
        }
        // IE
        else if (_support.createTextRange) {
            _setCaretIE(input, pos);
        }
    };

    /**
     * Inserts the specified text at the current caret position in the given input.
     * @param {HTMLInputElement|HTMLTextAreaElement} input input or textarea element
     * @param {String} text
     * @see http://parentnode.org/javascript/working-with-the-cursor-position/
     */
    var _insertAtCaret = function(input, text) {
        var curPos = _getCaret(input);

        var oldValueNorm = _getValue(input).replace(_rCarriageReturn, '');

        var newLength = +(curPos + text.length + (oldValueNorm.length - curPos));
        var maxLength = +input.getAttribute('maxlength');

        if(_hasAttr(input, 'maxlength') && newLength > maxLength) {
            var delta = text.length - (newLength - maxLength);
            text = text.substr(0, delta);
        }

        _setValue(input, oldValueNorm.substr(0, curPos) + text + oldValueNorm.substr(curPos));

        _setCaret(input, curPos + text.length);
    };

    var _getInputRangeW3 = function(input) {
        var range = new Range();

        range.start = input.selectionStart;
        range.end = input.selectionEnd;

        var min = Math.min(range.start, range.end);
        var max = Math.max(range.start, range.end);

        range.length = max - min;
        range.text = _getValue(input).substring(min, max);

        return range;
    };

    /** @see http://stackoverflow.com/a/3648244/467582 */
    var _getInputRangeIE = function(input) {
        var range = new Range();

        input.focus();

        var selection = document.selection.createRange();

        if (selection && selection.parentElement() === input) {
            var len, normalizedValue, textInputRange, endRange, start = 0, end = 0;
            var rawValue = _getValue(input);

            len = rawValue.length;
            normalizedValue = rawValue.replace(/\r\n/g, "\n");

            // Create a working TextRange that lives only in the input
            textInputRange = input.createTextRange();
            textInputRange.moveToBookmark(selection.getBookmark());

            // Check if the start and end of the selection are at the very end
            // of the input, since moveStart/moveEnd doesn't return what we want
            // in those cases
            endRange = input.createTextRange();
            endRange.collapse(false);

            if (textInputRange.compareEndPoints("StartToEnd", endRange) > -1) {
                start = end = len;
            } else {
                start = -textInputRange.moveStart("character", -len);
                start += normalizedValue.slice(0, start).split("\n").length - 1;

                if (textInputRange.compareEndPoints("EndToEnd", endRange) > -1) {
                    end = len;
                } else {
                    end = -textInputRange.moveEnd("character", -len);
                    end += normalizedValue.slice(0, end).split("\n").length - 1;
                }
            }

            /// normalize newlines
            start -= (rawValue.substring(0, start).split('\r\n').length - 1);
            end -= (rawValue.substring(0, end).split('\r\n').length - 1);
            /// normalize newlines

            range.start = start;
            range.end = end;
            range.length = range.end - range.start;
            range.text = normalizedValue.substr(range.start, range.length);
        }

        return range;
    };

    /**
     * Gets the selected text range of the given input.
     * @param {HTMLInputElement|HTMLTextAreaElement} input input or textarea element
     * @returns {Range}
     * @see http://stackoverflow.com/a/263796/467582
     * @see http://stackoverflow.com/a/2966703/467582
     */
    var _getInputRange = function(input) {
        if (!input) {
            return undefined;
        }

        // Mozilla, et al.
        if (_support.setSelectionRange) {
            return _getInputRangeW3(input);
        }
        // IE
        else if (_support.createTextRange) {
            return _getInputRangeIE(input);
        }

        return undefined;
    };

    var _setInputRangeW3 = function(input, startPos, endPos) {
        input.setSelectionRange(startPos, endPos);
    };

    var _setInputRangeIE = function(input, startPos, endPos) {
        var tr = input.createTextRange();
        tr.moveEnd('textedit', -1);
        tr.moveStart('character', startPos);
        tr.moveEnd('character', endPos - startPos);
        tr.select();
    };

    /**
     * Sets the selected text range of (i.e., highlights text in) the given input.
     * @param {HTMLInputElement|HTMLTextAreaElement} input input or textarea element
     * @param {Number} startPos Zero-based index
     * @param {Number} endPos Zero-based index
     * @see http://parentnode.org/javascript/working-with-the-cursor-position/
     * @see http://stackoverflow.com/a/2966703/467582
     */
    var _setInputRange = function(input, startPos, endPos) {
        startPos = _getIndex(input, startPos);
        endPos = _getIndex(input, endPos);

        // Mozilla, et al.
        if (_support.setSelectionRange) {
            _setInputRangeW3(input, startPos, endPos);
        }
        // IE
        else if (_support.createTextRange) {
            _setInputRangeIE(input, startPos, endPos);
        }
    };

    /**
     * Replaces the currently selected text with the given string.
     * @param {HTMLInputElement|HTMLTextAreaElement} input input or textarea element
     * @param {String} text New text that will replace the currently selected text.
     * @see http://parentnode.org/javascript/working-with-the-cursor-position/
     */
    var _replaceInputRange = function(input, text) {
        var $input = $(input);

        var oldValue = $input.val();
        var selection = _getInputRange(input);

        var newLength = +(selection.start + text.length + (oldValue.length - selection.end));
        var maxLength = +$input.attr('maxlength');

        if($input.is('[maxlength]') && newLength > maxLength) {
            var delta = text.length - (newLength - maxLength);
            text = text.substr(0, delta);
        }

        // Now that we know what the user selected, we can replace it
        var startText = oldValue.substr(0, selection.start);
        var endText = oldValue.substr(selection.end);

        $input.val(startText + text + endText);

        // Reset the selection
        var startPos = selection.start;
        var endPos = startPos + text.length;

        _setInputRange(input, selection.length ? startPos : endPos, endPos);
    };

    var _selectAllW3 = function(elem) {
        var selection = window.getSelection();
        var range = document.createRange();
        range.selectNodeContents(elem);
        selection.removeAllRanges();
        selection.addRange(range);
    };

    var _selectAllIE = function(elem) {
        var range = document.body.createTextRange();
        range.moveToElementText(elem);
        range.select();
    };

    /**
     * Select all text in the given element.
     * @param {HTMLElement} elem Any block or inline element other than a form element.
     */
    var _selectAll = function(elem) {
        var $elem = $(elem);
        if ($elem.is('input, textarea') || elem.select) {
            $elem.select();
            return;
        }

        // Mozilla, et al.
        if (_support.setSelectionRange) {
            _selectAllW3(elem);
        }
        // IE
        else if (_support.createTextRange) {
            _selectAllIE(elem);
        }
    };

    var _deselectAll = function() {
        if (document.selection) {
            document.selection.empty();
        }
        else if (window.getSelection) {
            window.getSelection().removeAllRanges();
        }
    };

    $.extend($.fn, {

        /**
         * Gets or sets the position of the caret or inserts text at the current caret position in an input or textarea element.
         * @returns {Number|jQuery} The current caret position if invoked as a getter (with no arguments)
         * or this jQuery object if invoked as a setter or inserter.
         * @see http://web.archive.org/web/20080704185920/http://parentnode.org/javascript/working-with-the-cursor-position/
         * @since 1.0.0
         * @example
         * <pre>
         *    // Get position
         *    var pos = $('input:first').caret();
         * </pre>
         * @example
         * <pre>
         *    // Set position
         *    $('input:first').caret(15);
         *    $('input:first').caret(-3);
         * </pre>
         * @example
         * <pre>
         *    // Insert text at current position
         *    $('input:first').caret('Some text');
         * </pre>
         */
        caret: function() {
            var $inputs = this.filter('input, textarea');

            // getCaret()
            if (arguments.length === 0) {
                var input = $inputs.get(0);
                return _getCaret(input);
            }
            // setCaret(position)
            else if (typeof arguments[0] === 'number') {
                var pos = arguments[0];
                $inputs.each(function(_i, input) {
                    _setCaret(input, pos);
                });
            }
            // insertAtCaret(text)
            else {
                var text = arguments[0];
                $inputs.each(function(_i, input) {
                    _insertAtCaret(input, text);
                });
            }

            return this;
        },

        /**
         * Gets or sets the selection range or replaces the currently selected text in an input or textarea element.
         * @returns {Range|jQuery} The current selection range if invoked as a getter (with no arguments)
         * or this jQuery object if invoked as a setter or replacer.
         * @see http://stackoverflow.com/a/2966703/467582
         * @since 1.0.0
         * @example
         * <pre>
         *    // Get selection range
         *    var range = $('input:first').range();
         * </pre>
         * @example
         * <pre>
         *    // Set selection range
         *    $('input:first').range(15);
         *    $('input:first').range(15, 20);
         *    $('input:first').range(-3);
         *    $('input:first').range(-8, -3);
         * </pre>
         * @example
         * <pre>
         *    // Replace the currently selected text
         *    $('input:first').range('Replacement text');
         * </pre>
         */
        range: function() {
            var $inputs = this.filter('input, textarea');

            // getRange() = { start: pos, end: pos }
            if (arguments.length === 0) {
                var input = $inputs.get(0);
                return _getInputRange(input);
            }
            // setRange(startPos, endPos)
            else if (typeof arguments[0] === 'number') {
                var startPos = arguments[0];
                var endPos = arguments[1];
                $inputs.each(function(_i, input) {
                    _setInputRange(input, startPos, endPos);
                });
            }
            // replaceRange(text)
            else {
                var text = arguments[0];
                $inputs.each(function(_i, input) {
                    _replaceInputRange(input, text);
                });
            }

            return this;
        },

        /**
         * Selects all text in each element of this jQuery object.
         * @returns {jQuery} This jQuery object
         * @see http://stackoverflow.com/a/11128179/467582
         * @since 1.5.0
         * @example
         * <pre>
         *     // Select the contents of span elements when clicked
         *     $('span').on('click', function() { $(this).highlight(); });
         * </pre>
         */
        selectAll: function() {
            return this.each(function(_i, elem) {
                _selectAll(elem);
            });
        }

    });

    $.extend($, {
        /**
         * Deselects all text on the page.
         * @returns {jQuery} The jQuery function
         * @since 1.5.0
         * @example
         * <pre>
         *     // Select some text
         *     $('span').selectAll();
         *
         *     // Deselect the text
         *     $.deselectAll();
         * </pre>
         */
        deselectAll: function() {
            _deselectAll();
            return this;
        }
    });

}(window.jQuery || window.Zepto || window.$));
