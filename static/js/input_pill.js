"use strict";

const render_input_pill = require("../templates/input_pill.hbs");

// See https://zulip.readthedocs.io/en/latest/subsystems/input-pills.html
exports.random_id = function () {
    return Math.random().toString(16);
};

exports.create = function (opts) {
    // a dictionary of the key codes that are associated with each key
    // to make if/else more human readable.
    const KEY = {
        ENTER: 13,
        BACKSPACE: 8,
        LEFT_ARROW: 37,
        RIGHT_ARROW: 39,
        COMMA: 188,
    };

    if (!opts.container) {
        blueslip.error("Pill needs container.");
        return;
    }

    if (!opts.create_item_from_text) {
        blueslip.error("Pill needs create_item_from_text");
        return;
    }

    if (!opts.get_text_from_item) {
        blueslip.error("Pill needs get_text_from_item");
        return;
    }

    // a stateful object of this `pill_container` instance.
    // all unique instance information is stored in here.
    const store = {
        pills: [],
        $parent: opts.container,
        $input: opts.container.find(".input").expectOne(),
        create_item_from_text: opts.create_item_from_text,
        get_text_from_item: opts.get_text_from_item,
    };

    // a dictionary of internal functions. Some of these are exposed as well,
    // and nothing in here should be assumed to be private (due to the passing)
    // of the `this` arg in the `Function.prototype.bind` use in the prototype.
    const funcs = {
        // return the value of the contenteditable input form.
        value(input_elem) {
            return input_elem.innerText;
        },

        // clear the value of the input form.
        clear(input_elem) {
            input_elem.innerText = "";
        },

        clear_text() {
            store.$input.text("");
        },

        is_pending() {
            // This function returns true if we have text
            // in out widget that hasn't been turned into
            // pills.  We use it to decide things like
            // whether we're ready to send typing indicators.
            return store.$input.text().trim() !== "";
        },

        create_item(text) {
            const existing_items = funcs.items();
            const item = store.create_item_from_text(text, existing_items);

            if (!item || !item.display_value) {
                store.$input.addClass("shake");
                return;
            }

            return item;
        },

        // This is generally called by typeahead logic, where we have all
        // the data we need (as opposed to, say, just a user-typed email).
        appendValidatedData(item) {
            const id = exports.random_id();

            if (!item.display_value) {
                blueslip.error("no display_value returned");
                return;
            }

            const payload = {
                id,
                item,
            };

            store.pills.push(payload);

            const has_image = item.img_src !== undefined;

            const opts = {
                id: payload.id,
                display_value: item.display_value,
                has_image,
            };

            if (has_image) {
                opts.img_src = item.img_src;
            }

            if (typeof store.onPillCreate === "function") {
                store.onPillCreate();
            }

            const pill_html = render_input_pill(opts);
            payload.$element = $(pill_html);
            store.$input.before(payload.$element);
        },

        // this appends a pill to the end of the container but before the
        // input block.
        appendPill(value) {
            if (value.length === 0) {
                return;
            }
            if (value.match(",")) {
                funcs.insertManyPills(value);
                return false;
            }

            const payload = this.create_item(value);
            // if the pill object is undefined, then it means the pill was
            // rejected so we should return out of this.
            if (!payload) {
                return false;
            }

            this.appendValidatedData(payload);
        },

        // this searches given a particlar pill ID for it, removes the node
        // from the DOM, removes it from the array and returns it.
        // this would generally be used for DOM-provoked actions, such as a user
        // clicking on a pill to remove it.
        removePill(id) {
            let idx;
            for (let x = 0; x < store.pills.length; x += 1) {
                if (store.pills[x].id === id) {
                    idx = x;
                }
            }

            if (typeof idx === "number") {
                store.pills[idx].$element.remove();
                const pill = store.pills.splice(idx, 1);
                if (typeof store.removePillFunction === "function") {
                    store.removePillFunction(pill);
                }

                return pill;
            }
        },

        // this will remove the last pill in the container -- by default tied
        // to the "Backspace" key when the value of the input is empty.
        // If quiet is a truthy value, the event handler associated with the
        // pill will not be evaluated. This is useful when using clear to reset
        // the pills.
        removeLastPill(quiet) {
            const pill = store.pills.pop();

            if (pill) {
                pill.$element.remove();
                if (!quiet && typeof store.removePillFunction === "function") {
                    store.removePillFunction(pill);
                }
            }
        },

        removeAllPills(quiet) {
            while (store.pills.length > 0) {
                this.removeLastPill(quiet);
            }

            this.clear(store.$input[0]);
        },

        insertManyPills(pills) {
            if (typeof pills === "string") {
                pills = pills.split(/,/g).map((pill) => pill.trim());
            }

            // this is an array to push all the errored values to, so it's drafts
            // of pills for the user to fix.
            const drafts = [];

            pills.forEach((pill) => {
                // if this returns `false`, it erroed and we should push it to
                // the draft pills.
                if (funcs.appendPill(pill) === false) {
                    drafts.push(pill);
                }
            });

            store.$input.text(drafts.join(", "));
            // when using the `text` insertion feature with jQuery the caret is
            // placed at the beginning of the input field, so this moves it to
            // the end.
            ui_util.place_caret_at_end(store.$input[0]);

            // this sends a flag that the operation wasn't completely successful,
            // which in this case is defined as some of the pills not autofilling
            // correctly.
            if (drafts.length > 0) {
                return false;
            }
        },

        getByID(id) {
            return store.pills.find((pill) => pill.id === id);
        },

        items() {
            return store.pills.map((pill) => pill.item);
        },

        createPillonPaste() {
            if (typeof store.createPillonPaste === "function") {
                return store.createPillonPaste();
            }
            return true;
        },
    };

    (function events() {
        store.$parent.on("keydown", ".input", (e) => {
            const char = e.keyCode || e.charCode;

            if (char === KEY.ENTER) {
                // regardless of the value of the input, the ENTER keyword
                // should be ignored in favor of keeping content to one line
                // always.
                e.preventDefault();

                // if there is input, grab the input, make a pill from it,
                // and append the pill, then clear the input.
                const value = funcs.value(e.target).trim();
                if (value.length > 0) {
                    // append the pill and by proxy create the pill object.
                    const ret = funcs.appendPill(value);

                    // if the pill to append was rejected, no need to clear the
                    // input; it may have just been a typo or something close but
                    // incorrect.
                    if (ret !== false) {
                        // clear the input.
                        funcs.clear(e.target);
                        e.stopPropagation();
                    }
                }

                return;
            }

            // if the user backspaces and there is input, just do normal char
            // deletion, otherwise delete the last pill in the sequence.
            if (
                char === KEY.BACKSPACE &&
                (funcs.value(e.target).length === 0 || window.getSelection().anchorOffset === 0)
            ) {
                e.preventDefault();
                funcs.removeLastPill();

                return;
            }

            // if one is on the ".input" element and back/left arrows, then it
            // should switch to focus the last pill in the list.
            // the rest of the events then will be taken care of in the function
            // below that handles events on the ".pill" class.
            if (char === KEY.LEFT_ARROW) {
                if (window.getSelection().anchorOffset === 0) {
                    store.$parent.find(".pill").last().trigger("focus");
                }
            }

            // Typing of the comma is prevented if the last field doesn't validate,
            // as well as when the new pill is created.
            if (char === KEY.COMMA) {
                // if the pill is successful, it will create the pill and clear
                // the input.
                if (funcs.appendPill(store.$input.text().trim()) !== false) {
                    funcs.clear(store.$input[0]);
                }
                e.preventDefault();

                return;
            }
        });

        // handle events while hovering on ".pill" elements.
        // the three primary events are next, previous, and delete.
        store.$parent.on("keydown", ".pill", (e) => {
            const char = e.keyCode || e.charCode;

            const $pill = store.$parent.find(".pill:focus");

            if (char === KEY.LEFT_ARROW) {
                $pill.prev().trigger("focus");
            } else if (char === KEY.RIGHT_ARROW) {
                $pill.next().trigger("focus");
            } else if (char === KEY.BACKSPACE) {
                const $next = $pill.next();
                const id = $pill.data("id");
                funcs.removePill(id);
                $next.trigger("focus");
                // the "Backspace" key in Firefox will go back a page if you do
                // not prevent it.
                e.preventDefault();
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
            const text = (e.originalEvent || e).clipboardData.getData("text/plain");

            // insert text manually
            document.execCommand("insertText", false, text);

            if (funcs.createPillonPaste()) {
                funcs.insertManyPills(store.$input.text().trim());
            }
        });

        // when the "×" is clicked on a pill, it should delete that pill and then
        // select the next pill (or input).
        store.$parent.on("click", ".exit", function (e) {
            e.stopPropagation();
            const $pill = $(this).closest(".pill");
            const $next = $pill.next();
            const id = $pill.data("id");

            funcs.removePill(id);
            $next.trigger("focus");
        });

        store.$parent.on("click", function (e) {
            if ($(e.target).is(".pill-container")) {
                $(this).find(".input").trigger("focus");
            }
        });

        store.$parent.on("copy", ".pill", (e) => {
            const id = store.$parent.find(":focus").data("id");
            const data = funcs.getByID(id);
            e.originalEvent.clipboardData.setData(
                "text/plain",
                store.get_text_from_item(data.item),
            );
            e.preventDefault();
        });
    })();

    // the external, user-accessible prototype.
    const prototype = {
        appendValue: funcs.appendPill.bind(funcs),
        appendValidatedData: funcs.appendValidatedData.bind(funcs),

        getByID: funcs.getByID,
        items: funcs.items,

        onPillCreate(callback) {
            store.onPillCreate = callback;
        },

        onPillRemove(callback) {
            store.removePillFunction = callback;
        },

        createPillonPaste(callback) {
            store.createPillonPaste = callback;
        },

        clear: funcs.removeAllPills.bind(funcs),
        clear_text: funcs.clear_text,
        is_pending: funcs.is_pending,
    };

    return prototype;
};

window.input_pill = exports;
