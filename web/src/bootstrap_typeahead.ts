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
 * 3. Footer text:
 *
 *   This adds support for showing a custom footer text like: "You are now
 *   completing a user mention". Provide the function `this.footer_html` that
 *   returns a string containing the footer text, or false.
 *
 *   Our custom changes include all mentions of this.footer_html, some CSS changes
 *   in compose.css and splitting $container out of $menu so we can insert
 *   additional HTML after $menu.
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
 *   We add a new `non_tippy_parent_element` option which the typeahead can
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
 * 14. Don't act on blurs that change focus within the `non_tippy_parent_element`:
 *
 *   This allows us to have things like a close button, and be able
 *   to move focus there without the typeahead closing.
 *
 * 15. To position typeaheads, we use Tippyjs except for typeaheads that are
 *    appended to a `non_tippy_parent_element`.
 *
 * 16. Add `requireHighlight` and `shouldHighlightFirstResult` options:
 *
 *   Allow none of the typeahead options to be highlighted, which lets
 *   the user remove highlight by going navigating (with the keyboard)
 *   past the last item or before the first item.
 *
 *   Why? A main way to initiate a search is to press enter from the
 *   search box, but if an item is highlighted then the enter key selects
 *   that item to add it as a pill to the search box.
 *
 *   `shouldHighlightFirstResult` relatedly lets us decide whether
 *   the first result should be highlighted when the typeahead opens.
 *
 * 17. Add `updateElementContent` option.
 *
 *   This is useful for complicated typeaheads that have custom logic
 *   for setting their element's contents after an item is selected.
 *
 * 18. Add `hideAfterSelect` option, default true.
 *
 *   This is useful for custom situations where we want to trigger the
 *   typeahead to do a lookup after selecting an option, when the user
 *   is making multiple related selections in a row.
 *
 * 19. Add `hideOnEmptyAfterBackspace` option, default false.
 *
 *   This allows us to prevent the typeahead menu from being displayed
 *   when a pill is deleted using the backspace key.
 * ============================================================ */

import $ from "jquery";
import assert from "minimalistic-assert";
import {insertTextIntoField} from "text-field-edit";
import getCaretCoordinates from "textarea-caret";
import * as tippy from "tippy.js";

import * as scroll_util from "./scroll_util.ts";
import {get_string_diff, the} from "./util.ts";

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

export let MAX_ITEMS = 50;

export function rewire_MAX_ITEMS(value: typeof MAX_ITEMS): void {
    MAX_ITEMS = value;
}

/* TYPEAHEAD PUBLIC CLASS DEFINITION
 * ================================= */

const FOOTER_ELEMENT_HTML =
    '<p class="typeahead-footer"><span id="typeahead-footer-text"></span></p>';
const CONTAINER_HTML = '<div class="typeahead dropdown-menu"></div>';
const MENU_HTML = '<ul class="typeahead-menu" data-simplebar></ul>';
const ITEM_HTML = '<li class="typeahead-item"><a class="typeahead-item-link"></a></li>';
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
    item_html: (item: ItemType, query: string) => string | undefined;
    updater: (
        item: ItemType,
        query: string,
        input_element: TypeaheadInputElement,
        event?: JQuery.ClickEvent | JQuery.KeyUpEvent | JQuery.KeyDownEvent,
    ) => string | undefined;
    $container: JQuery;
    $menu: JQuery;
    $footer: JQuery;
    source: (query: string, input_element: TypeaheadInputElement) => ItemType[];
    dropup: boolean;
    automated: () => boolean;
    trigger_selection: (event: JQuery.KeyDownEvent) => boolean;
    on_escape: (() => void) | undefined;
    // returns a string to show in typeahead footer or false.
    footer_html: () => string | false;
    // returns a string to show in typeahead items or false.
    option_label: (matching_items: ItemType[], item: ItemType) => string | false;
    suppressKeyPressRepeat = false;
    query = "";
    mouse_moved_since_typeahead = false;
    shown = false;
    // To trigger updater when Esc is pressed only during the stream topic typeahead in composebox.
    select_on_escape_condition: () => boolean;
    openInputFieldOnKeyUp: (() => void) | undefined;
    closeInputFieldOnHide: (() => void) | undefined;
    helpOnEmptyStrings: boolean;
    tabIsEnter: boolean;
    stopAdvance: boolean;
    advanceKeys: string[];
    non_tippy_parent_element: string | undefined;
    values: WeakMap<HTMLElement, ItemType>;
    instance: tippy.Instance | undefined;
    requireHighlight: boolean;
    shouldHighlightFirstResult: () => boolean;
    // Used for contenteditble divs. If this is set to false, we
    // don't set the html content of the div from this module, and
    // it's handled from the caller (or updater function) instead.
    updateElementContent: boolean;
    // Used to determine whether the typeahead should be shown,
    // when the user clicks anywhere on the input element.
    showOnClick: boolean;
    // Used for custom situations where we want to hide the typeahead
    // after selecting an option, instead of the default call to lookup().
    hideAfterSelect: () => boolean;
    hideOnEmptyAfterBackspace: boolean;
    // Used for adding a custom classname to the typeahead link.
    getCustomItemClassname: ((item: ItemType) => string) | undefined;

    constructor(input_element: TypeaheadInputElement, options: TypeaheadOptions<ItemType>) {
        this.input_element = input_element;
        if (this.input_element.type === "contenteditable") {
            assert(this.input_element.$element.is("[contenteditable]"));
        } else {
            assert(!this.input_element.$element.is("[contenteditable]"));
        }
        this.items = options.items ?? MAX_ITEMS;
        this.matcher = options.matcher ?? ((item, query) => this.defaultMatcher(item, query));
        this.sorter = options.sorter;
        this.item_html = options.item_html;
        this.updater = options.updater ?? ((items) => this.defaultUpdater(items));
        this.$container = $(CONTAINER_HTML);
        if (options.non_tippy_parent_element) {
            $(options.non_tippy_parent_element).append(this.$container);
        }
        this.$menu = $(MENU_HTML).appendTo(this.$container);
        this.$footer = $(FOOTER_ELEMENT_HTML).appendTo(this.$container);
        this.source = options.source;
        this.dropup = options.dropup ?? false;
        this.automated = options.automated ?? (() => false);
        this.trigger_selection = options.trigger_selection ?? (() => false);
        this.on_escape = options.on_escape;
        // return a string to show in typeahead footer or false.
        this.footer_html = options.footer_html ?? (() => false);
        // return a string to show in typeahead items or false.
        this.option_label = options.option_label ?? (() => false);
        this.stopAdvance = options.stopAdvance ?? false;
        this.select_on_escape_condition = options.select_on_escape_condition ?? (() => false);
        this.advanceKeys = options.advanceKeys ?? [];
        this.openInputFieldOnKeyUp = options.openInputFieldOnKeyUp;
        this.closeInputFieldOnHide = options.closeInputFieldOnHide;
        this.tabIsEnter = options.tabIsEnter ?? true;
        this.helpOnEmptyStrings = options.helpOnEmptyStrings ?? false;
        this.non_tippy_parent_element = options.non_tippy_parent_element;
        this.values = new WeakMap();
        this.requireHighlight = options.requireHighlight ?? true;
        this.shouldHighlightFirstResult = options.shouldHighlightFirstResult ?? (() => true);
        this.updateElementContent = options.updateElementContent ?? true;
        this.showOnClick = options.showOnClick ?? true;
        this.hideAfterSelect = options.hideAfterSelect ?? (() => true);
        this.hideOnEmptyAfterBackspace = options.hideOnEmptyAfterBackspace ?? false;
        this.getCustomItemClassname = options.getCustomItemClassname;
        this.listen();
    }

    select(e?: JQuery.ClickEvent | JQuery.KeyUpEvent | JQuery.KeyDownEvent): this {
        const active_option = this.$menu.find(".active")[0];
        const val = active_option ? this.values.get(active_option) : undefined;
        // It's possible that we got here from pressing enter with nothing highlighted.
        if (!this.requireHighlight && val === undefined) {
            return this.hide();
        }
        assert(val !== undefined);
        if (this.input_element.type === "contenteditable") {
            if (this.updateElementContent) {
                this.input_element.$element
                    .text(this.updater(val, this.query, this.input_element, e) ?? "")
                    .trigger("change");
                // Empty text after the change event handler
                // converts the input text to html elements.
                this.input_element.$element.text("");
            } else {
                this.updater(val, this.query, this.input_element, e);
                this.input_element.$element.trigger("change");
            }
        } else {
            const after_text = this.updater(val, this.query, this.input_element, e) ?? "";
            const element_val = this.input_element.$element.val();
            assert(element_val !== undefined);
            const [from, to_before, to_after] = get_string_diff(element_val, after_text);
            const replacement = after_text.slice(from, to_after);
            // select / highlight the minimal text to be replaced
            this.input_element.$element[0]!.setSelectionRange(from, to_before);
            insertTextIntoField(this.input_element.$element[0]!, replacement);
            this.input_element.$element.trigger("change");
        }

        if (this.hideAfterSelect()) {
            return this.hide();
        }
        return this.lookup(true);
    }

    set_value(): void {
        const val = this.values.get(the(this.$menu.find(".active")));
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
        if (this.shown) {
            return this;
        }

        // Call this early to avoid duplicate calls.
        this.shown = true;
        this.mouse_moved_since_typeahead = false;

        const input_element = this.input_element;
        if (!this.non_tippy_parent_element) {
            this.instance = tippy.default(the(input_element.$element), {
                // Lets typeahead take the width needed to fit the content
                // and wraps it if it overflows the visible container.
                maxWidth: "none",
                delay: [0, 0],
                theme: "dropdown-widget",
                placement: this.dropup ? "top-start" : "bottom-start",
                popperOptions: {
                    strategy: "fixed",
                    modifiers: [
                        {
                            // This will only work if there is enough space on the fallback
                            // placement, otherwise `preventOverflow` will be used to position
                            // it in the visible space.
                            name: "flip",
                            options: {
                                fallbackPlacements: ["top-start", "bottom-start"],
                            },
                        },
                        {
                            name: "preventOverflow",
                            options: {
                                // This seems required to prevent overflow, maybe because our
                                // placements are not the usual top, bottom, left, right.
                                // https://popper.js.org/docs/v2/modifiers/prevent-overflow/#altaxis
                                altAxis: true,
                            },
                        },
                    ],
                },
                interactive: true,
                appendTo: () => document.body,
                showOnCreate: true,
                content: the(this.$container),
                // We expect the typeahead creator to handle when to hide / show the typeahead.
                trigger: "manual",
                arrow: false,
                offset({placement, reference}) {
                    // Gap separates the typeahead and caret by 2px vertically.
                    const gap = 2;

                    if (input_element.type === "textarea") {
                        const caret = getCaretCoordinates(
                            the(input_element.$element),
                            the(input_element.$element).selectionStart,
                        );
                        // Used to consider the scroll height of textbox in the vertical offset.
                        const scrollTop = input_element.$element.scrollTop() ?? 0;

                        if (placement === "top-start") {
                            return [caret.left, -caret.top + scrollTop + gap];
                        }

                        // In bottom-start, the offset is calculated from bottom of the popper reference.
                        if (placement === "bottom-start") {
                            // Height of the reference is the input_element height.
                            const field_height = reference.height;
                            const distance = field_height - caret.top + scrollTop - caret.height;
                            return [caret.left, -distance + gap];
                        }
                    }
                    return [0, gap];
                },
                // We have event handlers to hide the typeahead, so we
                // don't want tippy to hide it for us.
                hideOnClick: false,
                onMount: (instance) => {
                    // The container has `display: none` as a default style.
                    // We make sure to display it. For tippy elements, this
                    // must happen after we insert the typeahead into the DOM.
                    this.$container.show();
                    // Reasons to update the position of the typeahead here:
                    // * Simplebar causes the height of the typeahead to
                    //   change, which can cause the typeahead to go off
                    //   screen like in compose topic typeahead.
                    // * Since we use an offset which can partially hide
                    //   typeahead at certain caret positions in textarea
                    //   input, we need to push it back into view once we
                    //   have rendered the typeahead.
                    requestAnimationFrame(() => {
                        // This detects any overflows by default and adjusts
                        // the placement of typeahead.
                        void instance.popperInstance?.update();
                    });
                },
            });
        }

        if (this.non_tippy_parent_element) {
            // Call this after $container is in DOM which is true here since
            // that happens in the constructor for non-tippy typeaheads.
            this.$container.show();
        }

        return this;
    }

    hide(): this {
        this.shown = false;
        if (this.non_tippy_parent_element) {
            this.$container.hide();
        } else {
            this.instance?.destroy();
            this.instance = undefined;
        }

        if (this.closeInputFieldOnHide !== undefined) {
            this.closeInputFieldOnHide();
        }
        return this;
    }

    lookup(hideOnEmpty: boolean): this {
        this.query =
            this.input_element.type === "contenteditable"
                ? this.input_element.$element.text()
                : (this.input_element.$element.val() ?? "");

        if (
            (!this.helpOnEmptyStrings || hideOnEmpty) &&
            (!this.query || this.query.length < MIN_LENGTH)
        ) {
            return this.shown ? this.hide() : this;
        }

        const items = this.source(this.query, this.input_element);

        if (items.length === 0 && this.shown) {
            this.hide();
        }
        return items.length > 0 ? this.process(items) : this;
    }

    process(items: ItemType[]): this {
        const matching_items = $.grep(items, (item) => this.matcher(item, this.query));

        const final_items = this.sorter(matching_items, this.query);

        if (final_items.length === 0) {
            return this.shown ? this.hide() : this;
        }
        if (this.automated()) {
            this.select();
            return this;
        }
        this.render(final_items.slice(0, this.items), matching_items);

        if (!this.shown) {
            return this.show();
        }

        return this;
    }

    defaultMatcher(item: ItemType, query: string): boolean {
        assert(typeof item === "string");
        return item.toLowerCase().includes(query.toLowerCase());
    }

    render(final_items: ItemType[], matching_items: ItemType[]): this {
        const $items: JQuery[] = final_items.map((item) => {
            const $i = $(ITEM_HTML);
            this.values.set(the($i), item);
            const item_html = this.item_html(item, this.query) ?? "";
            const $item_html = $i.find("a").html(item_html);

            const option_label_html = this.option_label(matching_items, item);
            if (this.getCustomItemClassname) {
                $item_html.addClass(this.getCustomItemClassname(item));
            }

            if (option_label_html) {
                $item_html
                    .addClass("typeahead-option-label-container")
                    .append($(option_label_html).addClass("typeahead-option-label"));
            }
            return $i;
        });

        // We want to re render the typeahead footer for ever update
        // in user's string since once typeahead is shown after `@`,
        // footer might change depending on whether next character is
        // `_` (silent mention) or not.
        const footer_text_html = this.footer_html();

        if (footer_text_html) {
            this.$footer.find("span#typeahead-footer-text").html(footer_text_html);
            this.$footer.show();
        } else {
            this.$footer.hide();
        }

        if (this.requireHighlight || this.shouldHighlightFirstResult()) {
            $items[0]!.addClass("active");
        }
        // Getting scroll element ensures simplebar has processed the element
        // before we render it.
        scroll_util.get_scroll_element(this.$menu);
        scroll_util.get_content_element(this.$menu).empty().append($items);
        return this;
    }

    next(): void {
        const $active = this.$menu.find(".active").removeClass("active");
        let $next = $active.next();

        // This lets there be a way to not have any item highlighted,
        // which can be important for e.g. letting the user press enter on
        // whatever's already in the search box.
        if (!this.requireHighlight && $active.length > 0 && $next.length === 0) {
            return;
        }

        if ($next.length === 0) {
            $next = this.$menu.find("li").first();
        }

        $next.addClass("active");
        scroll_util.scroll_element_into_container($next, this.$menu);
    }

    prev(): void {
        const $active = this.$menu.find(".active").removeClass("active");
        let $prev = $active.prev();

        // This lets there be a way to not have any item highlighted,
        // which can be important for e.g. letting the user press enter on
        // whatever's already in the search box.
        if (!this.requireHighlight && $active.length > 0 && $prev.length === 0) {
            return;
        }

        if ($prev.length === 0) {
            $prev = this.$menu.find("li").last();
        }

        $prev.addClass("active");
        scroll_util.scroll_element_into_container($prev, this.$menu);
    }

    listen(): void {
        $(this.input_element.$element)
            .on("blur", this.blur.bind(this))
            .on("keypress", this.keypress.bind(this))
            .on("keyup", this.keyup.bind(this))
            .on("click", this.element_click.bind(this))
            .on("keydown", this.keydown.bind(this))
            .on("typeahead.refreshPosition", this.refreshPosition.bind(this));

        this.$menu
            .on("click", "li", this.click.bind(this))
            .on("mouseenter", "li", this.mouseenter.bind(this))
            .on("mousemove", "li", this.mousemove.bind(this));

        $(window).on("resize", this.resizeHandler.bind(this));
    }

    unlisten(): void {
        this.hide();
        this.$container.remove();
        const events = ["blur", "keydown", "keyup", "keypress", "click"];
        for (const event of events) {
            $(this.input_element.$element).off(event);
        }
    }

    resizeHandler(): void {
        if (this.shown) {
            this.show();
        }
    }

    maybeStopAdvance(e: JQuery.KeyPressEvent | JQuery.KeyUpEvent | JQuery.KeyDownEvent): void {
        if (
            (this.stopAdvance || (e.key !== "Tab" && e.key !== "Enter")) &&
            !this.advanceKeys.includes(e.key)
        ) {
            e.stopPropagation();
        }
    }

    move(e: JQuery.KeyDownEvent | JQuery.KeyPressEvent): void {
        if (!this.shown) {
            return;
        }

        switch (e.key) {
            case "Tab":
                if (!this.tabIsEnter) {
                    return;
                }
                e.preventDefault();
                break;

            case "Enter":
            case "Escape":
                e.preventDefault();
                break;

            case "ArrowUp":
                e.preventDefault();
                this.prev();
                break;

            case "ArrowDown":
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
        if (this.trigger_selection(e)) {
            if (!this.shown) {
                return;
            }
            e.preventDefault();
            this.select(e);
        }
        this.suppressKeyPressRepeat = !["ArrowDown", "ArrowUp", "Tab", "Enter", "Escape"].includes(
            e.key,
        );
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
        this.mouse_moved_since_typeahead = false;
        // NOTE: Ideally we can ignore meta keyup calls here but
        // it's better to just trigger the lookup call to update the list in case
        // it did modify the query. For example, `Command + delete` on Mac
        // doesn't trigger a keyup event but when `Command` is released, it
        // triggers a keyup event which correctly updates the list.
        switch (e.key) {
            case "ArrowDown":
            case "ArrowUp":
                break;

            case "Tab":
                // If the typeahead is not shown or tabIsEnter option is not set, do nothing and return
                if (!this.tabIsEnter || !this.shown) {
                    return;
                }

                this.select(e);

                if (the(this.input_element.$element).id === "stream_message_recipient_topic") {
                    assert(this.input_element.type === "input");
                    // Move the cursor to the end of the topic
                    const topic_length = this.input_element.$element.val()!.length;
                    the(this.input_element.$element).selectionStart = topic_length;
                    the(this.input_element.$element).selectionEnd = topic_length;
                }

                break;

            case "Enter":
                if (!this.shown) {
                    return;
                }
                this.select(e);
                break;

            case "Escape":
                if (this.select_on_escape_condition()) {
                    this.select(e);
                }
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
                // when shift + tabbing to the topic field
                if (
                    e.key === "Shift" &&
                    the(this.input_element.$element).id === "stream_message_recipient_topic"
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
                if (e.key === "Backspace") {
                    this.lookup(this.hideOnEmptyAfterBackspace);
                    return;
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
            this.non_tippy_parent_element !== undefined &&
            e.relatedTarget &&
            $(e.relatedTarget).parents(this.non_tippy_parent_element).length > 0
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
        if (!this.showOnClick) {
            // If showOnClick is false, we don't want to show the typeahead
            // when the user clicks anywhere on the input element.
            return;
        }

        if (
            this.input_element.type === "contenteditable" &&
            this.input_element.$element.prop("contenteditable") === "false"
        ) {
            // We do not want to show the typeahead if user cannot type in
            // the input, for cases like user not having required permission.
            return;
        }

        // Update / hide the typeahead menu if the user clicks anywhere
        // inside the typing area. This is important in textarea elements
        // such as the compose box where multiple typeahead can exist,
        // and we want to prevent misplaced typeahead insertion.
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

    refreshPosition(e: JQuery.Event): void {
        e.stopPropagation();
        // Refresh the typeahead menu to account for any changes in the
        // input position by asking popper to recompute your tooltip's position.
        void this.instance?.popperInstance?.update();
    }
}

/* TYPEAHEAD PLUGIN DEFINITION
 * =========================== */

type TypeaheadOptions<ItemType> = {
    item_html: (item: ItemType, query: string) => string | undefined;
    items?: number;
    source: (query: string, input_element: TypeaheadInputElement) => ItemType[];
    // optional options
    advanceKeys?: string[];
    automated?: () => boolean;
    closeInputFieldOnHide?: () => void;
    dropup?: boolean;
    footer_html?: () => string | false;
    helpOnEmptyStrings?: boolean;
    hideOnEmptyAfterBackspace?: boolean;
    matcher?: (item: ItemType, query: string) => boolean;
    on_escape?: () => void;
    openInputFieldOnKeyUp?: () => void;
    option_label?: (matching_items: ItemType[], item: ItemType) => string | false;
    non_tippy_parent_element?: string;
    sorter: (items: ItemType[], query: string) => ItemType[];
    stopAdvance?: boolean;
    tabIsEnter?: boolean;
    select_on_escape_condition?: () => boolean;
    trigger_selection?: (event: JQuery.KeyDownEvent) => boolean;
    updater?: (
        item: ItemType,
        query: string,
        input_element: TypeaheadInputElement,
        event?: JQuery.ClickEvent | JQuery.KeyUpEvent | JQuery.KeyDownEvent,
    ) => string | undefined;
    requireHighlight?: boolean;
    shouldHighlightFirstResult?: () => boolean;
    updateElementContent?: boolean;
    showOnClick?: boolean;
    hideAfterSelect?: () => boolean;
    getCustomItemClassname?: (item: ItemType) => string;
};
