// todo: Refactor pills subsystem to use modern javascript classes?

import $ from "jquery";
import assert from "minimalistic-assert";

import render_input_pill from "../templates/input_pill.hbs";

import * as keydown_util from "./keydown_util.ts";
import * as ui_util from "./ui_util.ts";
import * as util from "./util.ts";

// See https://zulip.readthedocs.io/en/latest/subsystems/input-pills.html

export type InputPillConfig = {
    exclude_inaccessible_users?: boolean;
    setting_name?: string;
    setting_type?: "realm" | "stream" | "group";
    user_id?: number;
};

type InputPillCreateOptions<ItemType> = {
    $container: JQuery;
    pill_config?: InputPillConfig | undefined;
    split_text_on_comma?: boolean;
    convert_to_pill_on_enter?: boolean;
    create_item_from_text: (
        text: string,
        existing_items: ItemType[],
        pill_config?: InputPillConfig,
    ) => ItemType | undefined;
    get_text_from_item: (item: ItemType) => string;
    get_display_value_from_item: (item: ItemType) => string;
    generate_pill_html?: (item: ItemType, disabled?: boolean) => string;
    on_pill_exit?: (
        clicked_pill: HTMLElement,
        all_pills: InputPill<ItemType>[],
        remove_pill: (pill: HTMLElement) => void,
    ) => void;
    show_outline_on_invalid_input?: boolean;
};

export type InputPill<ItemType> = {
    item: ItemType;
    $element: JQuery;
    disabled: boolean;
};

type InputPillStore<ItemType> = {
    onTextInputHook?: () => void;
    pills: InputPill<ItemType>[];
    pill_config: InputPillCreateOptions<ItemType>["pill_config"];
    $parent: JQuery;
    $input: JQuery;
    create_item_from_text: InputPillCreateOptions<ItemType>["create_item_from_text"];
    get_text_from_item: InputPillCreateOptions<ItemType>["get_text_from_item"];
    get_display_value_from_item: InputPillCreateOptions<ItemType>["get_display_value_from_item"];
    generate_pill_html: InputPillCreateOptions<ItemType>["generate_pill_html"];
    on_pill_exit: InputPillCreateOptions<ItemType>["on_pill_exit"];
    onPillCreate?: () => void;
    onPillRemove?: (pill: InputPill<ItemType>, trigger: RemovePillTrigger) => void;
    onPillExpand?: (pill: JQuery) => void;
    createPillonPaste?: () => void;
    split_text_on_comma: boolean;
    convert_to_pill_on_enter: boolean;
    show_outline_on_invalid_input: boolean;
};

// These are the functions that are exposed to other modules.
export type InputPillContainer<ItemType> = {
    appendValue: (text: string) => void;
    appendValidatedData: (item: ItemType, disabled?: boolean, quiet?: boolean) => void;
    getByElement: (element: HTMLElement) => InputPill<ItemType> | undefined;
    items: () => ItemType[];
    removePill: (
        element: HTMLElement,
        trigger: RemovePillTrigger,
    ) => InputPill<ItemType> | undefined;
    onPillCreate: (callback: () => void) => void;
    onPillRemove: (
        callback: (pill: InputPill<ItemType>, trigger: RemovePillTrigger) => void,
    ) => void;
    onPillExpand: (callback: (pill: JQuery) => void) => void;
    onTextInputHook: (callback: () => void) => void;
    createPillonPaste: (callback: () => void) => void;
    clear: (quiet?: boolean) => void;
    clear_text: () => void;
    getCurrentText: () => string | null;
    is_pending: () => boolean;
    _get_pills_for_testing: () => InputPill<ItemType>[];
};

export type RemovePillTrigger = "close" | "backspace" | "clear";

export function create<ItemType extends {type: string}>(
    opts: InputPillCreateOptions<ItemType>,
): InputPillContainer<ItemType> {
    // a stateful object of this `pill_container` instance.
    // all unique instance information is stored in here.
    const store: InputPillStore<ItemType> = {
        pills: [],
        pill_config: opts.pill_config,
        $parent: opts.$container,
        $input: opts.$container.find(".input").expectOne(),
        create_item_from_text: opts.create_item_from_text,
        get_text_from_item: opts.get_text_from_item,
        get_display_value_from_item: opts.get_display_value_from_item,
        split_text_on_comma: opts.split_text_on_comma ?? true,
        convert_to_pill_on_enter: opts.convert_to_pill_on_enter ?? true,
        generate_pill_html: opts.generate_pill_html,
        on_pill_exit: opts.on_pill_exit,
        show_outline_on_invalid_input: opts.show_outline_on_invalid_input ?? false,
    };

    // a dictionary of internal functions. Some of these are exposed as well,
    // and nothing in here should be assumed to be private (due to the passing)
    // of the `this` arg in the `Function.prototype.bind` use in the prototype.
    const funcs = {
        // return the value of the contenteditable input form.
        value(input_elem: HTMLElement) {
            return input_elem.textContent ?? "";
        },

        // clear the value of the input form.
        clear(input_elem: HTMLElement) {
            input_elem.textContent = "";
        },

        clear_text() {
            store.$input.text("");
        },

        getCurrentText() {
            return store.$input.text();
        },

        is_pending() {
            // This function returns true if we have text
            // in out widget that hasn't been turned into
            // pills.  We use it to decide things like
            // whether we're ready to send typing indicators.
            return store.$input.text().trim() !== "";
        },

        create_item(text: string) {
            const existing_items = funcs.items();
            const item = store.create_item_from_text(text, existing_items, store.pill_config);
            if (!item) {
                store.$input.addClass("shake");

                if (store.show_outline_on_invalid_input) {
                    store.$parent.addClass("invalid");
                }
                return undefined;
            }
            return item;
        },

        // This is generally called by typeahead logic, where we have all
        // the data we need (as opposed to, say, just a user-typed email).
        appendValidatedData(item: ItemType, disabled = false, quiet = false) {
            let pill_html;
            if (store.generate_pill_html !== undefined) {
                pill_html = store.generate_pill_html(item, disabled);
            } else {
                pill_html = render_input_pill({
                    display_value: store.get_display_value_from_item(item),
                    disabled,
                });
            }
            const payload: InputPill<ItemType> = {
                item,
                $element: $(pill_html),
                disabled,
            };

            store.pills.push(payload);
            store.$input.before(payload.$element);

            if (store.show_outline_on_invalid_input && store.$parent.hasClass("invalid")) {
                store.$parent.removeClass("invalid");
            }

            // If we check is_pending just after adding a pill, the
            // text is still present until further input, so we
            // manually clear it here.
            this.clear_text();

            if (!quiet && store.onPillCreate !== undefined) {
                store.onPillCreate();
            }
        },

        // this appends a pill to the end of the container but before the
        // input block.
        appendPill(value: string) {
            if (value.length === 0) {
                return true;
            }
            if (store.split_text_on_comma && value.includes(",")) {
                funcs.insertManyPills(value);
                return false;
            }

            const payload = this.create_item(value);
            // if the pill object is undefined, then it means the pill was
            // rejected so we should return out of this.
            if (payload === undefined) {
                return false;
            }

            this.appendValidatedData(payload);
            return true;
        },

        // this searches given the DOM node for a pill, removes the node
        // from the DOM, removes it from the array and returns it.
        // this would generally be used for DOM-provoked actions, such as a user
        // clicking on a pill to remove it.
        removePill(element: HTMLElement, trigger: RemovePillTrigger) {
            const idx = store.pills.findIndex((pill) => pill.$element[0] === element);

            if (idx !== -1) {
                if (store.pills[idx]!.disabled) {
                    return undefined;
                }
                store.pills[idx]!.$element.remove();
                const pill = util.the(store.pills.splice(idx, 1));
                if (store.onPillRemove !== undefined) {
                    store.onPillRemove(pill, trigger);
                }

                // This is needed to run the "change" event handler registered in
                // compose_recipient.js, which calls the `update_on_recipient_change` to update
                // the compose_fade state.
                store.$input.trigger("change");

                return pill;
            }

            /* istanbul ignore next */
            return undefined;
        },

        // This will remove the last pill in the container.
        // If quiet is a truthy value, the event handler associated with the
        // pill will not be evaluated. This is useful when using clear to reset
        // the pills.
        removeLastPill(trigger: RemovePillTrigger, quiet?: boolean) {
            const pill = store.pills.pop();

            if (pill && !pill.disabled) {
                pill.$element.remove();
                if (!quiet && store.onPillRemove !== undefined) {
                    store.onPillRemove(pill, trigger);
                }
            }
        },

        removeAllPills(trigger: RemovePillTrigger, quiet?: boolean) {
            while (store.pills.length > 0) {
                this.removeLastPill(trigger, quiet);
            }
            this.clear(util.the(store.$input));
        },

        insertManyPills(pills: string | string[]) {
            if (typeof pills === "string") {
                pills = pills.split(/,/g).map((pill) => pill.trim());
            }

            // this is an array to push all the errored values to, so it's drafts
            // of pills for the user to fix.
            const drafts = pills.filter(
                (pill) =>
                    // if this returns `false`, it errored and we should push it to
                    // the draft pills.
                    !funcs.appendPill(pill),
            );

            store.$input.text(drafts.join(", "));
            // when using the `text` insertion feature with jQuery the caret is
            // placed at the beginning of the input field, so this moves it to
            // the end.
            ui_util.place_caret_at_end(util.the(store.$input));

            // this sends a flag if the operation wasn't completely successful,
            // which in this case is defined as some of the pills not autofilling
            // correctly.
            return drafts.length === 0;
        },

        getByElement(element: HTMLElement) {
            return store.pills.find((pill) => pill.$element[0] === element);
        },

        _get_pills_for_testing() {
            return store.pills;
        },

        items() {
            return store.pills.map((pill) => pill.item);
        },

        createPillonPaste() {
            if (store.createPillonPaste !== undefined) {
                store.createPillonPaste();
                return undefined;
            }
            return true;
        },
    };

    {
        store.$parent.on("keydown", ".input", function (this: HTMLElement, e) {
            // `convert_to_pill_on_enter = false` allows some pill containers,
            // which don't convert all of their text input to pills, to have
            // their own custom handlers of enter events.
            if (keydown_util.is_enter_event(e) && store.convert_to_pill_on_enter) {
                // regardless of the value of the input, the ENTER keyword
                // should be ignored in favor of keeping content to one line
                // always.
                e.preventDefault();

                // if there is input, grab the input, make a pill from it,
                // and append the pill, then clear the input.
                const value = funcs.value(this).trim();
                if (value.length > 0) {
                    // append the pill and by proxy create the pill object.
                    const ret = funcs.appendPill(value);

                    // if the pill to append was rejected, no need to clear the
                    // input; it may have just been a typo or something close but
                    // incorrect.
                    if (ret) {
                        // clear the input.
                        funcs.clear(this);
                    }
                    e.stopPropagation();
                }

                return;
            }
            const selection = window.getSelection();
            // If no text is selected, and the cursor is just to the
            // right of the last pill (with or without text in the
            // input), then backspace highlights or deletes the last pill.
            if (
                e.key === "Backspace" &&
                (funcs.value(this).length === 0 ||
                    (selection?.anchorOffset === 0 && selection?.toString()?.length === 0))
            ) {
                e.preventDefault();
                const pill = store.pills.at(-1);
                // We focus the pill first first, as a signal that the pill
                // is about to be deleted. The deletion will then happen through
                // `removePill` from the event handler on the pill.
                if (pill) {
                    assert(!pill.$element.is(":focus"));
                    pill.$element.trigger("focus");
                }
            }

            // if one is on the ".input" element and back/left arrows, then it
            // should switch to focus the last pill in the list.
            // the rest of the events then will be taken care of in the function
            // below that handles events on the ".pill" class.
            if (e.key === "ArrowLeft" && selection?.anchorOffset === 0) {
                store.$parent.find(".pill").last().trigger("focus");
            }

            // Typing of the comma is prevented if the last field doesn't validate,
            // as well as when the new pill is created.
            if (e.key === ",") {
                // if the pill is successful, it will create the pill and clear
                // the input.
                if (funcs.appendPill(store.$input.text().trim())) {
                    funcs.clear(util.the(store.$input));
                }
                e.preventDefault();

                return;
            }
        });

        // Register our `onTextInputHook` to be called on "input" events so that
        // the hook receives the updated text content of the input unlike the "keydown"
        // event which does not have the updated text content.
        store.$parent.on("input", ".input", () => {
            if (
                store.show_outline_on_invalid_input &&
                funcs.value(store.$input[0]!).length === 0 &&
                store.$parent.hasClass("invalid")
            ) {
                store.$parent.removeClass("invalid");
            }
            store.onTextInputHook?.();
        });

        // handle events while hovering on ".pill" elements.
        // the three primary events are next, previous, and delete.
        store.$parent.on("keydown", ".pill", (e) => {
            const $pill = store.$parent.find(".pill:focus");

            switch (e.key) {
                case "ArrowLeft":
                    $pill.prev().trigger("focus");
                    break;
                case "ArrowRight":
                    $pill.next().trigger("focus");
                    break;
                case "Backspace": {
                    const $prev = $pill.prev();
                    const $next = $pill.next();
                    funcs.removePill(util.the($pill), "backspace");
                    if ($prev.length > 0) {
                        $prev.trigger("focus");
                    } else {
                        $next.trigger("focus");
                    }
                    // the "Backspace" key in Firefox will go back a page if you do
                    // not prevent it.
                    e.preventDefault();
                    break;
                }
            }
        });

        // when the shake animation is applied to the ".input" on invalid input,
        // we want to remove the class when finished automatically.
        store.$parent.on("animationend", ".input", function () {
            $(this).removeClass("shake");
        });

        // replace formatted input with plaintext to allow for sane copy-paste
        // actions.
        store.$parent.on("paste", ".input", (e) => {
            e.preventDefault();

            // get text representation of clipboard
            assert(e.originalEvent instanceof ClipboardEvent);
            const text = e.originalEvent.clipboardData?.getData("text/plain").replaceAll("\n", ",");

            // insert text manually
            // eslint-disable-next-line @typescript-eslint/no-deprecated
            document.execCommand("insertText", false, text);

            if (funcs.createPillonPaste()) {
                funcs.insertManyPills(store.$input.text().trim());
            }
        });

        // when the "×" is clicked on a pill, it should delete that pill and then
        // select the input field.
        store.$parent.on("click", ".exit", function (this: HTMLElement, e) {
            if (store.on_pill_exit) {
                store.on_pill_exit(this, store.pills, (pill: HTMLElement): void => {
                    funcs.removePill(pill, "close");
                });
                // This is needed to run the "change" event handler registered in
                // compose_recipient.js, which calls the `update_on_recipient_change` to update
                // the compose_fade state.
                store.$input.trigger("change");
            } else {
                e.stopPropagation();
                const pill = util.the($(this).closest(".pill"));
                funcs.removePill(pill, "close");
            }
            // Since removing a pill moves the $input, typeahead needs to refresh
            // to appear at the correct position.
            store.$input.trigger(new $.Event("typeahead.refreshPosition"));
            store.$input.trigger("focus");
        });

        store.$parent.on("click", ".expand", function (this: HTMLElement, e) {
            assert(store.onPillExpand !== undefined);
            e.stopPropagation();
            store.onPillExpand($(this).closest(".pill"));
            const pill = util.the($(this).closest(".pill"));
            funcs.removePill(pill, "close");
            store.$input.trigger("focus");
        });

        store.$parent.on("click", function (e) {
            if ($(e.target).is(".pill-container")) {
                $(this).find(".input").trigger("focus");
            }
        });

        store.$parent.on("copy", ".pill", function (this: HTMLElement, e) {
            const {item} = funcs.getByElement(this)!;
            assert(e.originalEvent instanceof ClipboardEvent);
            e.originalEvent.clipboardData?.setData("text/plain", store.get_text_from_item(item));
            e.preventDefault();
        });
    }

    // the external, user-accessible prototype.
    const prototype: InputPillContainer<ItemType> = {
        appendValue: funcs.appendPill.bind(funcs),
        appendValidatedData: funcs.appendValidatedData.bind(funcs),

        getByElement: funcs.getByElement.bind(funcs),
        getCurrentText: funcs.getCurrentText.bind(funcs),
        items: funcs.items.bind(funcs),
        removePill: funcs.removePill.bind(funcs),

        onPillCreate(callback) {
            store.onPillCreate = callback;
        },

        onPillRemove(callback) {
            store.onPillRemove = callback;
        },

        onPillExpand(callback) {
            store.onPillExpand = callback;
        },

        onTextInputHook(callback) {
            store.onTextInputHook = callback;
        },

        createPillonPaste(callback) {
            store.createPillonPaste = callback;
        },

        clear(quiet?: boolean) {
            funcs.removeAllPills.bind(funcs)("clear", quiet);
        },
        clear_text: funcs.clear_text.bind(funcs),
        is_pending: funcs.is_pending.bind(funcs),
        _get_pills_for_testing: funcs._get_pills_for_testing.bind(funcs),
    };

    return prototype;
}
