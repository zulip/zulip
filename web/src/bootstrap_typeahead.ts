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
import assert from "minimalistic-assert";
import {insertTextIntoField} from "text-field-edit";

import {get_string_diff} from "./util";

function get_pseudo_keycode(
    event: JQuery.KeyDownEvent | JQuery.KeyUpEvent | JQuery.KeyPressEvent,
): number {
    const isComposing = event.originalEvent?.isComposing ?? false;
    /* We treat IME compose enter keypresses as a separate -13 key. */
    if (event.keyCode === 13 && isComposing) {
        return -13;
    }
    return event.keyCode;
}

export function defaultSorter(items: string[], query: string): string[] {
    const beginswith = [];
    const caseSensitive = [];
    const caseInsensitive = [];
    let item;

    while ((item = items.shift())) {
        if (item.toLowerCase().startsWith(query.toLowerCase())) {
            beginswith.push(item);
        } else if (item.includes(query)) {
            caseSensitive.push(item);
        } else {
            caseInsensitive.push(item);
        }
    }

    return [...beginswith, ...caseSensitive, ...caseInsensitive];
}

/* TYPEAHEAD PUBLIC CLASS DEFINITION
 * ================================= */

const HEADER_ELEMENT_HTML =
    '<p class="typeahead-header"><span id="typeahead-header-text"></span></p>';
const CONTAINER_HTML = '<div class="typeahead dropdown-menu"></div>';
const MENU_HTML = '<ul class="typeahead-menu"></ul>';
const ITEM_HTML = "<li><a></a></li>";
const MIN_LENGTH = 1;

export type TypeaheadInputElement =
    | {
          $element: JQuery;
          type: "contenteditable";
      }
    | {
          $element: JQuery<HTMLInputElement>;
          type: "input";
      }
    | {
          $element: JQuery<HTMLTextAreaElement>;
          type: "textarea";
      };

export class Typeahead<ItemType extends string | object> {
    input_element: TypeaheadInputElement;
    items: number;
    matcher: (item: ItemType, query: string) => boolean;
    sorter: (items: ItemType[], query: string) => ItemType[];
    highlighter_html: (item: ItemType, query: string) => string | undefined;
    updater: (
        item: ItemType,
        query: string,
        input_element: TypeaheadInputElement,
        event?: JQuery.ClickEvent | JQuery.KeyUpEvent | JQuery.KeyDownEvent,
    ) => string | undefined;
    $container: JQuery;
    $menu: JQuery;
    $header: JQuery;
    source: (query: string, input_element: TypeaheadInputElement) => ItemType[];
    dropup: boolean;
    fixed: boolean;
    automated: () => boolean;
    trigger_selection: (event: JQuery.KeyDownEvent) => boolean;
    on_escape?: () => void;
    // returns a string to show in typeahead header or false.
    header_html: () => string | false;
    // returns a string to show in typeahead items or false.
    option_label: (matching_items: ItemType[], item: ItemType) => string | false;
    suppressKeyPressRepeat = false;
    query = "";
    mouse_moved_since_typeahead = false;
    shown = false;
    openInputFieldOnKeyUp?: () => void;
    closeInputFieldOnHide?: () => void;
    helpOnEmptyStrings: boolean;
    tabIsEnter: boolean;
    naturalSearch: boolean;
    stopAdvance: boolean;
    advanceKeyCodes: number[];
    parentElement?: string;
    values: WeakMap<HTMLElement, ItemType>;

    constructor(input_element: TypeaheadInputElement, options: TypeaheadOptions<ItemType>) {
        this.input_element = input_element;
        if (this.input_element.type === "contenteditable") {
            assert(this.input_element.$element.is("[contenteditable]"));
        } else {
            assert(!this.input_element.$element.is("[contenteditable]"));
        }
        this.items = options.items ?? 8;
        this.matcher = options.matcher ?? ((item, query) => this.defaultMatcher(item, query));
        this.sorter = options.sorter;
        this.highlighter_html = options.highlighter_html;
        this.updater = options.updater ?? ((items) => this.defaultUpdater(items));
        this.$container = $(CONTAINER_HTML).appendTo($(options.parentElement ?? "body"));
        this.$menu = $(MENU_HTML).appendTo(this.$container);
        this.$header = $(HEADER_ELEMENT_HTML).appendTo(this.$container);
        this.source = options.source;
        this.dropup = options.dropup ?? false;
        this.fixed = options.fixed ?? false;
        this.automated = options.automated ?? (() => false);
        this.trigger_selection = options.trigger_selection ?? (() => false);
        this.on_escape = options.on_escape;
        // return a string to show in typeahead header or false.
        this.header_html = options.header_html ?? (() => false);
        // return a string to show in typeahead items or false.
        this.option_label = options.option_label ?? (() => false);
        this.stopAdvance = options.stopAdvance ?? false;
        this.advanceKeyCodes = options.advanceKeyCodes ?? [];
        this.openInputFieldOnKeyUp = options.openInputFieldOnKeyUp;
        this.closeInputFieldOnHide = options.closeInputFieldOnHide;
        this.tabIsEnter = options.tabIsEnter ?? true;
        this.helpOnEmptyStrings = options.helpOnEmptyStrings ?? false;
        this.naturalSearch = options.naturalSearch ?? false;
        this.parentElement = options.parentElement;
        this.values = new WeakMap();

        if (this.fixed) {
            this.$container.css("position", "fixed");
        }
        // The naturalSearch option causes arrow keys to immediately
        // update the search box with the underlying values from the
        // search suggestions.
        this.listen();
    }

    select(e?: JQuery.ClickEvent | JQuery.KeyUpEvent | JQuery.KeyDownEvent): this {
        const val = this.values.get(this.$menu.find(".active")[0]);
        assert(val !== undefined);
        if (this.input_element.type === "contenteditable") {
            this.input_element.$element
                .text(this.updater(val, this.query, this.input_element, e) ?? "")
                .trigger("change");
            // Empty text after the change event handler
            // converts the input text to html elements.
            this.input_element.$element.text("");
        } else {
            const after_text = this.updater(val, this.query, this.input_element, e) ?? "";
            const element_val = this.input_element.$element.val();
            assert(element_val !== undefined);
            const [from, to_before, to_after] = get_string_diff(element_val, after_text);
            const replacement = after_text.slice(from, to_after);
            // select / highlight the minimal text to be replaced
            this.input_element.$element[0].setSelectionRange(from, to_before);
            insertTextIntoField(this.input_element.$element[0], replacement);
            this.input_element.$element.trigger("change");
        }

        return this.hide();
    }

    set_value(): void {
        const val = this.values.get(this.$menu.find(".active")[0]);
        assert(typeof val === "string");
        if (this.input_element.type === "contenteditable") {
            this.input_element.$element.text(val);
        } else {
            this.input_element.$element.val(val);
        }
    }

    defaultUpdater(item: ItemType): string {
        assert(typeof item === "string");
        return item;
    }

    show(): this {
        const header_text_html = this.header_html();
        if (header_text_html) {
            this.$header.find("span#typeahead-header-text").html(header_text_html);
            this.$header.show();
        } else {
            this.$header.hide();
        }

        // If a parent element was specified, we shouldn't manually
        // position the element, since it's already in the right place.
        if (this.parentElement === undefined) {
            let pos;

            if (this.fixed) {
                // Relative to screen instead of to page
                pos = this.input_element.$element[0].getBoundingClientRect();
            } else {
                pos = this.input_element.$element.offset();
            }

            pos = $.extend({}, pos, {
                height: this.input_element.$element[0].offsetHeight,
                // Zulip patch: Workaround for iOS safari problems
                top: this.input_element.$element.get_offset_to_window().top,
            });

            let top_pos = pos.top + pos.height;
            if (this.dropup) {
                top_pos = pos.top - this.$container.outerHeight()!;
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
    }

    hide(): this {
        this.$container.hide();
        this.shown = false;
        if (this.closeInputFieldOnHide !== undefined) {
            this.closeInputFieldOnHide();
        }
        return this;
    }

    lookup(hideOnEmpty: boolean): this {
        this.query =
            this.input_element.type === "contenteditable"
                ? this.input_element.$element.text()
                : this.input_element.$element.val() ?? "";

        if (
            (!this.helpOnEmptyStrings || hideOnEmpty) &&
            (!this.query || this.query.length < MIN_LENGTH)
        ) {
            return this.shown ? this.hide() : this;
        }

        const items = this.source(this.query, this.input_element);

        if (!items && this.shown) {
            this.hide();
        }
        return items ? this.process(items) : this;
    }

    process(items: ItemType[]): this {
        const matching_items = $.grep(items, (item) => this.matcher(item, this.query));

        const final_items = this.sorter(matching_items, this.query);

        if (!final_items.length) {
            return this.shown ? this.hide() : this;
        }
        if (this.automated()) {
            this.select();
            return this;
        }
        return this.render(final_items.slice(0, this.items), matching_items).show();
    }

    defaultMatcher(item: ItemType, query: string): boolean {
        assert(typeof item === "string");
        return item.toLowerCase().includes(query.toLowerCase());
    }

    render(final_items: ItemType[], matching_items: ItemType[]): this {
        const $items: JQuery[] = final_items.map((item) => {
            const $i = $(ITEM_HTML);
            this.values.set($i[0], item);
            const item_html = this.highlighter_html(item, this.query) ?? "";
            const $item_html = $i.find("a").html(item_html);

            const option_label_html = this.option_label(matching_items, item);

            if (option_label_html) {
                $item_html.append($(option_label_html)).addClass("typeahead-option-label");
            }
            return $i;
        });

        $items[0].addClass("active");
        this.$menu.empty().append($items);
        return this;
    }

    next(): void {
        const $active = this.$menu.find(".active").removeClass("active");
        let $next = $active.next();

        if (!$next.length) {
            $next = $(this.$menu.find("li")[0]);
        }

        $next.addClass("active");

        if (this.naturalSearch) {
            this.set_value();
        }
    }

    prev(): void {
        const $active = this.$menu.find(".active").removeClass("active");
        let $prev = $active.prev();

        if (!$prev.length) {
            $prev = this.$menu.find("li").last();
        }

        $prev.addClass("active");

        if (this.naturalSearch) {
            this.set_value();
        }
    }

    listen(): void {
        $(this.input_element.$element)
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
    }

    unlisten(): void {
        this.$container.remove();
        const events = ["blur", "keydown", "keyup", "keypress", "mousemove"];
        for (const event_ of events) {
            $(this.input_element.$element).off(event_);
        }
    }

    resizeHandler(): void {
        if (this.shown) {
            this.show();
        }
    }

    maybeStopAdvance(e: JQuery.KeyPressEvent | JQuery.KeyUpEvent | JQuery.KeyDownEvent): void {
        const pseudo_keycode = get_pseudo_keycode(e);
        if (
            (this.stopAdvance || (pseudo_keycode !== 9 && pseudo_keycode !== 13)) &&
            !this.advanceKeyCodes.includes(e.keyCode)
        ) {
            e.stopPropagation();
        }
    }

    move(e: JQuery.KeyDownEvent | JQuery.KeyPressEvent): void {
        if (!this.shown) {
            return;
        }
        const pseudo_keycode = get_pseudo_keycode(e);

        switch (pseudo_keycode) {
            case 9: // tab
                if (!this.tabIsEnter) {
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
    }

    mousemove(e: JQuery.MouseMoveEvent): void {
        if (!this.mouse_moved_since_typeahead) {
            /* Undo cursor disabling in mouseenter handler. */
            $(e.currentTarget).find("a").css("cursor", "");
            this.mouse_moved_since_typeahead = true;
            this.mouseenter(e);
        }
    }

    keydown(e: JQuery.KeyDownEvent): void {
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
    }

    keypress(e: JQuery.KeyPressEvent): void {
        if (!this.suppressKeyPressRepeat) {
            this.move(e);
            return;
        }
        this.maybeStopAdvance(e);
    }

    keyup(e: JQuery.KeyUpEvent): void {
        const pseudo_keycode = get_pseudo_keycode(e);

        switch (pseudo_keycode) {
            case 40: // down arrow
            case 38: // up arrow
                break;

            case 9: // tab
                // If the typeahead is not shown or tabIsEnter option is not set, do nothing and return
                if (!this.tabIsEnter || !this.shown) {
                    return;
                }

                this.select(e);

                if (this.input_element.$element[0].id === "stream_message_recipient_topic") {
                    assert(this.input_element.type === "input");
                    // Move the cursor to the end of the topic
                    const topic_length = this.input_element.$element.val()!.length;
                    this.input_element.$element[0].selectionStart = topic_length;
                    this.input_element.$element[0].selectionEnd = topic_length;
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
                    this.input_element.$element[0].id === "stream_message_recipient_topic"
                ) {
                    return;
                }
                if (this.openInputFieldOnKeyUp !== undefined && !this.shown) {
                    // If the typeahead isn't shown yet, the `lookup` call will open it.
                    // Here we make a callback to the input field before we open the
                    // lookahead in case it needs to make UI changes first (e.g. widening
                    // the search bar).
                    this.openInputFieldOnKeyUp();
                }
                this.lookup(false);
        }

        this.maybeStopAdvance(e);

        e.preventDefault();
    }

    blur(e: JQuery.BlurEvent): void {
        // Blurs that move focus to elsewhere within the parent element shouldn't
        // hide the typeahead.
        if (
            this.parentElement !== undefined &&
            e.relatedTarget &&
            $(e.relatedTarget).parents(this.parentElement).length > 0
        ) {
            return;
        }
        setTimeout(() => {
            if (!this.$container.is(":hover") && !this.input_element.$element.is(":focus")) {
                // We do not hide the typeahead in case it is being hovered over,
                // or if the focus is immediately back in the input field (likely
                // when using compose formatting buttons).
                this.hide();
            } else if (this.shown) {
                // refocus the input if the user clicked on the typeahead
                // so that clicking elsewhere registers as a blur and hides
                // the typeahead.
                this.input_element.$element.trigger("focus");
            }
        }, 150);
    }

    element_click(): void {
        // update / hide the typeahead menu if the user clicks anywhere
        // inside the typing area, to avoid misplaced typeahead insertion.
        this.lookup(false);
    }

    click(e: JQuery.ClickEvent): void {
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
    }

    mouseenter(e: JQuery.MouseEnterEvent | JQuery.ClickEvent | JQuery.MouseMoveEvent): void {
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
    }
}

/* TYPEAHEAD PLUGIN DEFINITION
 * =========================== */

type TypeaheadOptions<ItemType> = {
    highlighter_html: (item: ItemType, query: string) => string | undefined;
    items: number;
    source: (query: string, input_element: TypeaheadInputElement) => ItemType[];
    // optional options
    advanceKeyCodes?: number[];
    automated?: () => boolean;
    closeInputFieldOnHide?: () => void;
    dropup?: boolean;
    fixed?: boolean;
    header_html?: () => string | false;
    helpOnEmptyStrings?: boolean;
    matcher?: (item: ItemType, query: string) => boolean;
    naturalSearch?: boolean;
    on_escape?: () => void;
    openInputFieldOnKeyUp?: () => void;
    option_label?: (matching_items: ItemType[], item: ItemType) => string | false;
    parentElement?: string;
    sorter: (items: ItemType[], query: string) => ItemType[];
    stopAdvance?: boolean;
    tabIsEnter?: boolean;
    trigger_selection?: (event: JQuery.KeyDownEvent) => boolean;
    updater?: (
        item: ItemType,
        query: string,
        input_element: TypeaheadInputElement,
        event?: JQuery.ClickEvent | JQuery.KeyUpEvent | JQuery.KeyDownEvent,
    ) => string | undefined;
};
