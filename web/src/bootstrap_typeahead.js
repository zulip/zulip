/* =============================================================
 * bootstrap-typeahead.js v2.1.0
 * http://twitter.github.com/bootstrap/javascript.html#typeahead
 * =============================================================
 * Copyright 2012 Twitter, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * ============================================================ */

/* =============================================================
 * Zulip's custom changes
 *
 * 1. Automated selection:
 *
 *   This adds support for automatically selecting a typeahead (on certain
 *   completions or queries). If `this.automated` returns true, we do not
 *   render the typeahead and directly trigger selection of the current
 *   choice.
 *
 *   Our custom changes include all mentions of this.automated.
 *   And also includes the blocks containing the is contenteditable condition.
 *
 * 2. Custom selection triggers:
 *
 *   This adds support for completing a typeahead on custom keyup input. By
 *   default, we only support Tab and Enter to complete a typeahead, but we
 *   have use cases where we want to complete using custom characters like: >.
 *
 *   If `this.trigger_selection` returns true, we complete the typeahead and
 *   pass the keyup event to the updater.
 *
 *   Our custom changes include all mentions of this.trigger_selection.
 *
 * 3. Header text:
 *
 *   This adds support for showing a custom header text like: "You are now
 *   completing a user mention". Provide the function `this.header_html` that
 *   returns a string containing the header text, or false.
 *
 *   Our custom changes include all mentions of this.header_html, some CSS changes
 *   in compose.css and splitting $container out of $menu so we can insert
 *   additional HTML before $menu.
 *
 * 4. Escape hooks:
 *
 *   You can set an on_escape hook to take extra actions when the user hits
 *   the `Esc` key.  We use this in our navbar code to close the navbar when
 *   a user hits escape while in the typeahead.
 *
 * 5. Help on empty strings:
 *
 *   This adds support for displaying the typeahead for an empty string.
 *   It is helpful when we want to render the typeahead, based on already
 *   entered data (in the form of contenteditable elements) every time the
 *   input block gains focus but is empty.
 *
 *   We also have logic so that there is an exception to this rule when this
 *   option is set as true. We prevent the lookup of the typeahead and hide it
 *   so that the `Backspace` key is free to interact with the other elements.
 *
 *   Our custom changes include all mentions of `helpOnEmptyStrings` and `hideOnEmpty`.
 *
 * 6. Prevent typeahead going off top of screen:
 *
 *   If typeahead would go off the top of the screen, we set its top to 0 instead.
 *   This patch should be replaced with something more flexible.
 *
 * 7. Ignore IME Enter events:
 *
 *   See #22062 for details. Enter keypress that are part of IME composing are
 *   treated as a separate/invalid -13 key, to prevent them from being incorrectly
 *   processed as a bonus Enter press.
 *
 * 8. Make the typeahead completions undo friendly:
 *
 *   We now use the undo supporting `insert` function from the
 *   `text-field-edit` module to update the text after autocompletion,
 *   instead of just resetting the value of the textarea / input, which was
 *   not undo-able.
 *
 *   So that the undo history seems sensible, we replace only the minimal
 *   diff between the text before and after autocompletion. This ensures that
 *   only this diff, and not the entire text, is highlighted when undoing,
 *   as would be ideal.
 *
 * 9. Re-render on window resize:
 *
 *   We add a new event handler, resizeHandler, for window.on('resize', ...)
 *   that calls this.show to re-render the typeahead in the correct position.
 *
 * 10. Allow typeahead to be located next to its input field in the DOM
 *
 *   We add a new `parentElement` option which the typeahead can
 *   append to, where before it could only be appended to `body`.
 *   Since it's in the right part of the DOM, we don't need to do
 *   the manual positioning in the show() function.
 *
 * 11. Add `openInputFieldOnKeyUp` option:
 *
 *   If the typeahead isn't shown yet, the `lookup` call in the keyup
 *   handler will open it. Here we make a callback to the input field
 *   before we open the lookahead in case it needs to make UI changes first
 *   (e.g. widening the search bar).
 *
 * 12. Add `closeInputFieldOnHide` option:
 *
 *   Some input fields like search have visual changes that need to happen
 *   when the typeahead hides. This callback function is called in `hide()`
 *   and allows those extra UI changes to happen.
 *
 *  13. Allow option to remove custom logic for tab keypresses:
 *
 *   Sometimes tab is treated similarly to the escape or enter key, with
 *   custom functionality, which also prevents propagation to default tab
 *   functionality. The `tabIsEnter` option (default true) lets this be
 *   turned off so that tab only does one thing while focus is in the
 *   typeahead -- move focus to the next element.
 *
 * 14. Don't act on blurs that change focus within the `parentElement`:
 *
 *   This allows us to have things like a close button, and be able
 *   to move focus there without the typeahead closing.
 * ============================================================ */

import $ from "jquery";
import {insertTextIntoField} from "text-field-edit";

import {get_string_diff} from "./util";

function get_pseudo_keycode(event) {
    const isComposing = (event.originalEvent && event.originalEvent.isComposing) || false;
    /* We treat IME compose enter keypresses as a separate -13 key. */
    if (event.keyCode === 13 && isComposing) {
        return -13;
    }
    return event.keyCode;
}

/* TYPEAHEAD PUBLIC CLASS DEFINITION
 * ================================= */

const header_element_html =
    '<p class="typeahead-header"><span id="typeahead-header-text"></span></p>';

const defaults = {
    source: [],
    items: 8,
    container: '<div class="typeahead dropdown-menu"></div>',
    menu: '<ul class="typeahead-menu"></ul>',
    item: "<li><a></a></li>",
    minLength: 1,
    stopAdvance: false,
    dropup: false,
    advanceKeyCodes: [],
    tabIsEnter: true,
};

const Typeahead = function (element, options) {
    this.$element = $(element);
    this.options = {
        ...defaults,
        ...options,
    };
    this.matcher = this.options.matcher ?? this.matcher;
    this.sorter = this.options.sorter ?? this.sorter;
    this.highlighter_html = this.options.highlighter_html;
    this.updater = this.options.updater ?? this.updater;
    this.$container = $(this.options.container).appendTo(this.options.parentElement ?? "body");
    this.$menu = $(this.options.menu).appendTo(this.$container);
    this.$header = $(header_element_html).appendTo(this.$container);
    this.source = this.options.source;
    this.shown = false;
    this.mouse_moved_since_typeahead = false;
    this.dropup = this.options.dropup;
    this.fixed = this.options.fixed ?? false;
    this.automated = this.options.automated ?? (() => false);
    this.trigger_selection = this.options.trigger_selection ?? (() => false);
    this.on_escape = this.options.on_escape;
    // return a string to show in typeahead header or false.
    this.header_html = this.options.header_html ?? (() => false);
    // return a string to show in typeahead items or false.
    this.option_label = this.options.option_label ?? (() => false);

    if (this.fixed) {
        this.$container.css("position", "fixed");
    }
    // The naturalSearch option causes arrow keys to immediately
    // update the search box with the underlying values from the
    // search suggestions.
    this.listen();
};

Typeahead.prototype = {
    constructor: Typeahead,

    select(e) {
        const val = this.$menu.find(".active").data("typeahead-value");
        if (this.$element.is("[contenteditable]")) {
            this.$element.text(this.updater(val, e)).trigger("change");
            // Empty text after the change event handler
            // converts the input text to html elements.
            this.$element.text("");
        } else {
            const after_text = this.updater(val, e);
            const [from, to_before, to_after] = get_string_diff(this.$element.val(), after_text);
            const replacement = after_text.slice(from, to_after);
            // select / highlight the minimal text to be replaced
            this.$element[0].setSelectionRange(from, to_before);
            insertTextIntoField(this.$element[0], replacement);
            this.$element.trigger("change");
        }

        return this.hide();
    },

    set_value() {
        const val = this.$menu.find(".active").data("typeahead-value");
        if (this.$element.is("[contenteditable]")) {
            this.$element.text(val);
        } else {
            this.$element.val(val);
        }
    },

    updater(item) {
        return item;
    },

    show() {
        const header_text_html = this.header_html();
        if (header_text_html) {
            this.$header.find("span#typeahead-header-text").html(header_text_html);
            this.$header.show();
        } else {
            this.$header.hide();
        }

        // If a parent element was specified, we shouldn't manually
        // position the element, since it's already in the right place.
        if (!this.options.parentElement) {
            let pos;

            if (this.fixed) {
                // Relative to screen instead of to page
                pos = this.$element[0].getBoundingClientRect();
            } else {
                pos = this.$element.offset();
            }

            pos = $.extend({}, pos, {
                height: this.$element[0].offsetHeight,
            });

            // Zulip patch: Workaround for iOS safari problems
            pos.top = this.$element.get_offset_to_window().top;

            let top_pos = pos.top + pos.height;
            if (this.dropup) {
                top_pos = pos.top - this.$container.outerHeight();
            }

            // Zulip patch: Avoid typeahead going off top of screen.
            if (top_pos < 0) {
                top_pos = 0;
            }

            this.$container.css({
                top: top_pos,
                left: pos.left,
            });
        }

        this.$container.show();
        this.shown = true;
        this.mouse_moved_since_typeahead = false;
        return this;
    },

    hide() {
        this.$container.hide();
        this.shown = false;
        if (this.options.closeInputFieldOnHide !== undefined) {
            this.options.closeInputFieldOnHide();
        }
        return this;
    },

    lookup(hideOnEmpty) {
        this.query = this.$element.is("[contenteditable]")
            ? this.$element.text()
            : this.$element.val();

        if (
            (!this.options.helpOnEmptyStrings || hideOnEmpty) &&
            (!this.query || this.query.length < this.options.minLength)
        ) {
            return this.shown ? this.hide() : this;
        }

        const items =
            typeof this.source === "function"
                ? this.source(this.query, this.process.bind(this))
                : this.source;

        if (!items && this.shown) {
            this.hide();
        }
        return items ? this.process(items) : this;
    },

    process(items) {
        const matching_items = $.grep(items, (item) => this.matcher(item));

        const final_items = this.sorter(matching_items);

        if (!final_items.length) {
            return this.shown ? this.hide() : this;
        }
        if (this.automated()) {
            this.select();
            return this;
        }
        return this.render(final_items.slice(0, this.options.items), matching_items).show();
    },

    matcher(item) {
        return item.toLowerCase().includes(this.query.toLowerCase());
    },

    sorter(items) {
        const beginswith = [];
        const caseSensitive = [];
        const caseInsensitive = [];
        let item;

        while ((item = items.shift())) {
            if (item.toLowerCase().startsWith(this.query.toLowerCase())) {
                beginswith.push(item);
            } else if (item.includes(this.query)) {
                caseSensitive.push(item);
            } else {
                caseInsensitive.push(item);
            }
        }

        return [...beginswith, ...caseSensitive, ...caseInsensitive];
    },

    render(final_items, matching_items) {
        const $items = $(final_items).map((_index, item) => {
            const $i = $(this.options.item).data("typeahead-value", item);
            const item_html = this.highlighter_html(item);
            const $item_html = $i.find("a").html(item_html);

            const option_label_html = this.option_label(matching_items, item);

            if (option_label_html) {
                $item_html.append(option_label_html).addClass("typeahead-option-label");
            }
            return $i[0];
        });

        $items.first().addClass("active");
        this.$menu.empty().append($items);
        return this;
    },

    next() {
        const $active = this.$menu.find(".active").removeClass("active");
        let $next = $active.next();

        if (!$next.length) {
            $next = $(this.$menu.find("li")[0]);
        }

        $next.addClass("active");

        if (this.options.naturalSearch) {
            this.set_value();
        }
    },

    prev() {
        const $active = this.$menu.find(".active").removeClass("active");
        let $prev = $active.prev();

        if (!$prev.length) {
            $prev = this.$menu.find("li").last();
        }

        $prev.addClass("active");

        if (this.options.naturalSearch) {
            this.set_value();
        }
    },

    listen() {
        this.$element
            .on("blur", this.blur.bind(this))
            .on("keypress", this.keypress.bind(this))
            .on("keyup", this.keyup.bind(this))
            .on("click", this.element_click.bind(this))
            .on("keydown", this.keydown.bind(this));

        this.$menu
            .on("click", "li", this.click.bind(this))
            .on("mouseenter", "li", this.mouseenter.bind(this))
            .on("mousemove", "li", this.mousemove.bind(this));

        $(window).on("resize", this.resizeHandler.bind(this));
    },

    unlisten() {
        this.$container.remove();
        const events = ["blur", "keydown", "keyup", "keypress", "mousemove"];
        for (const event_ of events) {
            this.$element.off(event_);
        }
        this.$element.removeData("typeahead");
    },

    resizeHandler() {
        if (this.shown) {
            this.show();
        }
    },

    maybeStopAdvance(e) {
        const pseudo_keycode = get_pseudo_keycode(e);
        if (
            (this.options.stopAdvance || (pseudo_keycode !== 9 && pseudo_keycode !== 13)) &&
            !this.options.advanceKeyCodes.includes(e.keyCode)
        ) {
            e.stopPropagation();
        }
    },

    move(e) {
        if (!this.shown) {
            return;
        }
        const pseudo_keycode = get_pseudo_keycode(e);

        switch (pseudo_keycode) {
            case 9: // tab
                if (!this.options.tabIsEnter) {
                    return;
                }
                e.preventDefault();
                break;

            case 13: // enter
            case 27: // escape
                e.preventDefault();
                break;

            case 38: // up arrow
                e.preventDefault();
                this.prev();
                break;

            case 40: // down arrow
                e.preventDefault();
                this.next();
                break;
        }

        this.maybeStopAdvance(e);
    },

    mousemove(e) {
        if (!this.mouse_moved_since_typeahead) {
            /* Undo cursor disabling in mouseenter handler. */
            $(e.currentTarget).find("a").css("cursor", "");
            this.mouse_moved_since_typeahead = true;
            this.mouseenter(e);
        }
    },

    keydown(e) {
        const pseudo_keycode = get_pseudo_keycode(e);
        if (this.trigger_selection(e)) {
            if (!this.shown) {
                return;
            }
            e.preventDefault();
            this.select(e);
        }
        this.suppressKeyPressRepeat = ![40, 38, 9, 13, 27].includes(pseudo_keycode);
        this.move(e);
    },

    keypress(e) {
        if (!this.suppressKeyPressRepeat) {
            this.move(e);
            return;
        }
        this.maybeStopAdvance(e);
    },

    keyup(e) {
        const pseudo_keycode = get_pseudo_keycode(e);

        switch (pseudo_keycode) {
            case 40: // down arrow
            case 38: // up arrow
                break;

            case 9: // tab
                // If the typeahead is not shown or tabIsEnter option is not set, do nothing and return
                if (!this.options.tabIsEnter || !this.shown) {
                    return;
                }

                this.select(e);

                if (e.currentTarget.id === "stream_message_recipient_topic") {
                    // Move the cursor to the end of the topic
                    const topic_length = this.$element.val().length;
                    this.$element[0].selectionStart = topic_length;
                    this.$element[0].selectionEnd = topic_length;
                }

                break;

            case 13: // enter
                if (!this.shown) {
                    return;
                }
                this.select(e);
                break;

            case 27: // escape
                if (!this.shown) {
                    return;
                }
                this.hide();
                if (this.on_escape) {
                    this.on_escape();
                }
                break;

            default:
                // to stop typeahead from showing up momentarily
                // when shift (keycode 16) + tabbing to the topic field
                if (
                    pseudo_keycode === 16 &&
                    e.currentTarget.id === "stream_message_recipient_topic"
                ) {
                    return;
                }
                if (this.options.openInputFieldOnKeyUp !== undefined && !this.shown) {
                    // If the typeahead isn't shown yet, the `lookup` call will open it.
                    // Here we make a callback to the input field before we open the
                    // lookahead in case it needs to make UI changes first (e.g. widening
                    // the search bar).
                    this.options.openInputFieldOnKeyUp();
                }
                this.lookup(false);
        }

        this.maybeStopAdvance(e);

        e.preventDefault();
    },

    blur(e) {
        // Blurs that move focus to elsewhere within the parent element shouldn't
        // hide the typeahead.
        if (
            this.options.parentElement &&
            $(e.relatedTarget).parents(this.options.parentElement).length > 0
        ) {
            return;
        }
        setTimeout(() => {
            if (!this.$container.is(":hover")) {
                this.hide();
            } else if (this.shown) {
                // refocus the input if the user clicked on the typeahead
                // so that clicking elsewhere registers as a blur and hides
                // the typeahead.
                this.$element.trigger("focus");
            }
        }, 150);
    },

    element_click() {
        // update / hide the typeahead menu if the user clicks anywhere
        // inside the typing area, to avoid misplaced typeahead insertion.
        this.lookup(false);
    },

    click(e) {
        e.stopPropagation();
        e.preventDefault();
        // The original bootstrap code expected `mouseenter` to be called
        // to set the active element before `select()`.
        // Since select() selects the element with the active class, if
        // we trigger a click from JavaScript (or with a mobile touchscreen),
        // this won't work. So we need to set the active element ourselves,
        // and the simplest way to do that is to just call the `mouseenter`
        // handler here.
        this.mouseenter(e);
        this.select(e);
    },

    mouseenter(e) {
        if (!this.mouse_moved_since_typeahead) {
            // Prevent the annoying interaction where your mouse happens
            // to be in the space where typeahead will open.  (This would
            // result in the mouse taking priority over the keyboard for
            // what you selected). If the mouse has not been moved since
            // the appearance of the typeahead menu, we disable the
            // cursor, which in turn prevents the currently hovered
            // element from being selected.  The mousemove handler
            // overrides this logic.
            $(e.currentTarget).find("a").css("cursor", "none");
            return;
        }
        this.$menu.find(".active").removeClass("active");
        $(e.currentTarget).addClass("active");
    },
};

/* TYPEAHEAD PLUGIN DEFINITION
 * =========================== */

export function create($element, options) {
    $element.data("typeahead", new Typeahead($element, options));
}

export function lookup($element) {
    const typeahead = $element.data("typeahead");
    typeahead.lookup();
}
