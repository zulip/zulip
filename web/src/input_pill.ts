// todo: Refactor pills subsystem to use modern javascript classes?

import $ from "jquery";
import assert from "minimalistic-assert";

import render_input_pill from "../templates/input_pill.hbs";

import * as blueslip from "./blueslip";
import type {EmojiRenderingDetails} from "./emoji";
import * as keydown_util from "./keydown_util";
import * as ui_util from "./ui_util";

// See https://zulip.readthedocs.io/en/latest/subsystems/input-pills.html

export type InputPillItem<T> = {
    display_value: string;
    type: string;
    img_src?: string;
    deactivated?: boolean;
    status_emoji_info?: EmojiRenderingDetails & {emoji_alt_code?: boolean}; // TODO: Move this in user_status.js
    should_add_guest_user_indicator?: boolean;
} & T;

export type InputPillConfig = {
    show_user_status_emoji?: boolean;
    exclude_inaccessible_users?: boolean;
};

type InputPillCreateOptions<T> = {
    $container: JQuery;
    pill_config?: InputPillConfig | undefined;
    create_item_from_text: (
        text: string,
        existing_items: InputPillItem<T>[],
        pill_config?: InputPillConfig | undefined,
    ) => InputPillItem<T> | undefined;
    get_text_from_item: (item: InputPillItem<T>) => string;
};

type InputPill<T> = {
    item: InputPillItem<T>;
    $element: JQuery;
};

type InputPillStore<T> = {
    onTextInputHook?: () => void;
    pills: InputPill<T>[];
    pill_config: InputPillCreateOptions<T>["pill_config"];
    $parent: JQuery;
    $input: JQuery;
    create_item_from_text: InputPillCreateOptions<T>["create_item_from_text"];
    get_text_from_item: InputPillCreateOptions<T>["get_text_from_item"];
    onPillCreate?: () => void;
    onPillRemove?: (pill: InputPill<T>) => void;
    createPillonPaste?: () => void;
};

type InputPillRenderingDetails = {
    display_value: string;
    has_image: boolean;
    img_src?: string;
    deactivated?: boolean;
    has_status?: boolean;
    status_emoji_info?: EmojiRenderingDetails & {emoji_alt_code?: boolean};
    should_add_guest_user_indicator?: boolean;
};

// These are the functions that are exposed to other modules.
export type InputPillContainer<T> = {
    appendValue: (text: string) => void;
    appendValidatedData: (item: InputPillItem<T>) => void;
    getByElement: (element: HTMLElement) => InputPill<T> | undefined;
    items: () => InputPillItem<T>[];
    onPillCreate: (callback: () => void) => void;
    onPillRemove: (callback: (pill: InputPill<T>) => void) => void;
    onTextInputHook: (callback: () => void) => void;
    createPillonPaste: (callback: () => void) => void;
    clear: () => void;
    clear_text: () => void;
    getCurrentText: () => string | null;
    is_pending: () => boolean;
    _get_pills_for_testing: () => InputPill<T>[];
};

export function create<T>(opts: InputPillCreateOptions<T>): InputPillContainer<T> {
    // a stateful object of this `pill_container` instance.
    // all unique instance information is stored in here.
    const store: InputPillStore<T> = {
        pills: [],
        pill_config: opts.pill_config,
        $parent: opts.$container,
        $input: opts.$container.find(".input").expectOne(),
        create_item_from_text: opts.create_item_from_text,
        get_text_from_item: opts.get_text_from_item,
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

            if (!item?.display_value) {
                store.$input.addClass("shake");
                return undefined;
            }

            return item;
        },

        // This is generally called by typeahead logic, where we have all
        // the data we need (as opposed to, say, just a user-typed email).
        appendValidatedData(item: InputPillItem<T>) {
            if (!item.display_value) {
                blueslip.error("no display_value returned");
                return;
            }

            if (!item.type) {
                blueslip.error("no type defined for the item");
                return;
            }

            const has_image = item.img_src !== undefined;

            const opts: InputPillRenderingDetails = {
                display_value: item.display_value,
                has_image,
                deactivated: item.deactivated,
                should_add_guest_user_indicator: item.should_add_guest_user_indicator,
            };

            if (has_image) {
                opts.img_src = item.img_src;
            }

            if (store.pill_config?.show_user_status_emoji === true) {
                const has_status = item.status_emoji_info !== undefined;
                if (has_status) {
                    opts.status_emoji_info = item.status_emoji_info;
                }
                opts.has_status = has_status;
            }

            const pill_html = render_input_pill(opts);
            const payload: InputPill<T> = {
                item,
                $element: $(pill_html),
            };

            store.pills.push(payload);
            store.$input.before(payload.$element);

            if (store.onPillCreate !== undefined) {
                store.onPillCreate();
            }
        },

        // this appends a pill to the end of the container but before the
        // input block.
        appendPill(value: string) {
            if (value.length === 0) {
                return true;
            }
            if (value.match(",")) {
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
        removePill(element: HTMLElement) {
            let idx: number | undefined;
            for (let x = 0; x < store.pills.length; x += 1) {
                if (store.pills[x].$element[0] === element) {
                    idx = x;
                }
            }

            if (idx !== undefined) {
                store.pills[idx].$element.remove();
                const pill = store.pills.splice(idx, 1);
                if (store.onPillRemove !== undefined) {
                    store.onPillRemove(pill[0]);
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

        // this will remove the last pill in the container -- by default tied
        // to the "Backspace" key when the value of the input is empty.
        // If quiet is a truthy value, the event handler associated with the
        // pill will not be evaluated. This is useful when using clear to reset
        // the pills.
        removeLastPill(quiet?: boolean) {
            const pill = store.pills.pop();

            if (pill) {
                pill.$element.remove();
                if (!quiet && store.onPillRemove !== undefined) {
                    store.onPillRemove(pill);
                }
            }
        },

        removeAllPills(quiet?: boolean) {
            while (store.pills.length > 0) {
                this.removeLastPill(quiet);
            }

            this.clear(store.$input[0]);
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
            ui_util.place_caret_at_end(store.$input[0]);

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
            if (keydown_util.is_enter_event(e)) {
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
                        e.stopPropagation();
                    }
                }

                return;
            }
            const selection = window.getSelection();
            // If no text is selected, and the cursor is just to the
            // right of the last pill (with or without text in the
            // input), then backspace deletes the last pill.
            if (
                e.key === "Backspace" &&
                (funcs.value(this).length === 0 ||
                    (selection?.anchorOffset === 0 && selection?.toString()?.length === 0))
            ) {
                e.preventDefault();
                funcs.removeLastPill();

                return;
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
                    funcs.clear(store.$input[0]);
                }
                e.preventDefault();

                return;
            }
        });

        // Register our `onTextInputHook` to be called on "input" events so that
        // the hook receives the updated text content of the input unlike the "keydown"
        // event which does not have the updated text content.
        store.$parent.on("input", ".input", () => {
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
                    const $next = $pill.next();
                    funcs.removePill($pill[0]);
                    $next.trigger("focus");
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
            document.execCommand("insertText", false, text);

            if (funcs.createPillonPaste()) {
                funcs.insertManyPills(store.$input.text().trim());
            }
        });

        // when the "×" is clicked on a pill, it should delete that pill and then
        // select the next pill (or input).
        store.$parent.on("click", ".exit", function (this: HTMLElement, e) {
            e.stopPropagation();
            const $pill = $(this).closest(".pill");
            const $next = $pill.next();

            funcs.removePill($pill[0]);
            $next.trigger("focus");
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
    const prototype: InputPillContainer<T> = {
        appendValue: funcs.appendPill.bind(funcs),
        appendValidatedData: funcs.appendValidatedData.bind(funcs),

        getByElement: funcs.getByElement.bind(funcs),
        getCurrentText: funcs.getCurrentText.bind(funcs),
        items: funcs.items.bind(funcs),

        onPillCreate(callback) {
            store.onPillCreate = callback;
        },

        onPillRemove(callback) {
            store.onPillRemove = callback;
        },

        onTextInputHook(callback) {
            store.onTextInputHook = callback;
        },

        createPillonPaste(callback) {
            store.createPillonPaste = callback;
        },

        clear: funcs.removeAllPills.bind(funcs),
        clear_text: funcs.clear_text.bind(funcs),
        is_pending: funcs.is_pending.bind(funcs),
        _get_pills_for_testing: funcs._get_pills_for_testing.bind(funcs),
    };

    return prototype;
}
