const DEFAULTS = {
    INITIAL_RENDER_COUNT: 80,
    LOAD_COUNT: 20,
    instances: {},
};

exports.filter = (value, list, opts) => {
    /*
        This is used by the main object (see `create`),
        but we split it out to make it a bit easier
        to test.
    */
    const predicate = opts.filter.predicate;

    return list.filter(function (item) {
        return predicate(item, value);
    });
};

// @params
// container: jQuery object to append to.
// list: The list of items to progressively append.
// opts: An object of random preferences.
exports.create = function ($container, list, opts) {
    // this memoizes the results and will return a previously invoked
    // instance's prototype.
    if (opts.name && DEFAULTS.instances[opts.name]) {
        // the false flag here means "don't run `init`". This is because a
        // user is likely reinitializing and will have put .init() afterwards.
        // This happens when the same codepath is hit multiple times.
        return DEFAULTS.instances[opts.name]
        // sets the container to the new container in this prototype's args.
            .set_container($container)
        // sets the input to the new input in the args.
            .set_opts(opts)
            .__set_events()
            .data(list)
            .init();
    }

    const meta = {
        sorting_function: null,
        prop: null,
        sorting_functions: {},
        generic_sorting_functions: {},
        offset: 0,
        listRenders: {},
        list: list,
        filtered_list: list,

    };

    function filter_list(value) {
        meta.filtered_list = exports.filter(value, meta.list, opts);
    }

    if (!opts) {
        return;
    }

    if (typeof opts.filter.predicate !== 'function') {
        blueslip.error('Filter predicate function is missing.');
        return;
    }

    const prototype = {
        // Reads the provided list (in the scope directly above)
        // and renders the next block of messages automatically
        // into the specified contianer.
        render: function (load_count) {
            load_count = load_count || opts.load_count || DEFAULTS.LOAD_COUNT;

            // Stop once the offset reaches the length of the original list.
            if (meta.offset >= meta.filtered_list.length) {
                return;
            }

            const slice = meta.filtered_list.slice(meta.offset, meta.offset + load_count);

            const html = _.reduce(slice, function (acc, item) {
                let _item = opts.modifier(item);

                // if valid jQuery selection, attempt to grab all elements within
                // and string them together into a giant outerHTML fragment.
                if (_item.constructor === jQuery) {
                    _item = (function ($nodes) {
                        let html = "";
                        $nodes.each(function () {
                            if (this.nodeType === 1) {
                                html += this.outerHTML;
                            }
                        });

                        return html;
                    }(_item));
                }

                // if is a valid element, get the outerHTML.
                if (_item instanceof Element) {
                    _item = _item.outerHTML;
                }

                // return the modified HTML or nothing if corrupt (null, undef, etc.).
                return acc + (_item || "");
            }, "");

            $container.append($(html));
            meta.offset += load_count;

            return this;
        },

        // Fills the container with an initial batch of items.
        // Needs to be enough to exceed the max height, so that a
        // scrollable area is created.
        init: function () {
            this.clear();
            this.render(DEFAULTS.INITIAL_RENDER_COUNT);
            return this;
        },

        filter: function (map_function) {
            meta.filtered_list = meta.list(map_function);
        },

        // reset the data associated with a list. This is so that instead of
        // initializing a new progressive list render instance, you can just
        // update the data of an existing one.
        data: function (data) {
            // if no args are provided then just return the existing data.
            // this interface is similar to how many jQuery functions operate,
            // where a call to the method without data returns the existing data.
            if (typeof data === "undefined" && arguments.length === 0) {
                return meta.list;
            }

            if (Array.isArray(data)) {
                meta.list = data;

                if (opts.filter && opts.filter.element) {
                    const value = $(opts.filter.element).val().toLocaleLowerCase();
                    filter_list(value);
                }

                prototype.clear();

                return this;
            }

            blueslip.warn("The data object provided to the progressive" +
                              " list render is invalid");
            return this;
        },

        clear: function () {
            $container.html("");
            meta.offset = 0;
            return this;
        },

        // Let's imagine the following:
        // list_render is initialized and becomes prototope A with scope A.
        // list_render is re-initialized and becomes prototype A with scope A again.
        // The issue is that when re-initializing, new variables could have been thrown
        // in and old variables could be useless (eg. dead nodes), so we need to
        // replace these with new copies if necessary.
        set_container: function ($new_container) {
            if ($new_container) {
                $container = $new_container;
            }

            return this;
        },

        set_opts: function (new_opts) {
            if (opts) {
                opts = new_opts;
            }

            return this;
        },

        reverse: function () {
            meta.filtered_list.reverse();
            prototype.init();
            return this;
        },

        // the sorting function is either the function or string that calls the
        // function to sort the list by. The prop is used for generic functions
        // that can be called to sort with a particular prop.

        // the `map` will normalize the values with a function you provide to make
        // it easier to sort with.

        // `do_not_display` will signal to not update the DOM, likely because in
        // the next function it will be updated in the DOM.
        sort: function (sorting_function, prop, do_not_display) {
            meta.prop = prop;

            if (typeof sorting_function === "function") {
                meta.sorting_function = sorting_function;
            } else if (typeof sorting_function === "string") {
                if (typeof prop === "string") {
                    /* eslint-disable max-len */
                    meta.sorting_function = meta.generic_sorting_functions[sorting_function](prop);
                } else {
                    meta.sorting_function = meta.sorting_functions[sorting_function];
                }
            }

            // we do not want to sort if we are just looking to reverse
            // by calling with no sorting_function
            if (meta.sorting_function) {
                meta.filtered_list = meta.filtered_list.sort(meta.sorting_function);
            }

            if (!do_not_display) {
                // clear and re-initialize the list with the newly filtered subset
                // of items.
                prototype.init();

                if (opts.filter.onupdate) {
                    opts.filter.onupdate();
                }
            }
        },

        add_sort_function: function (name, sorting_function) {
            meta.sorting_functions[name] = sorting_function;
        },

        // generic sorting functions are ones that will use a specified prop
        // and perform a sort on it with the given sorting function.
        add_generic_sort_function: function (name, sorting_function) {
            meta.generic_sorting_functions[name] = sorting_function;
        },

        remove_sort: function () {
            meta.sorting_function = false;
        },

        // this sets the events given the particular arguments assigned in
        // the container and opts.
        __set_events: function () {
            let $nearestScrollingContainer = $container;
            while ($nearestScrollingContainer.length) {
                if ($nearestScrollingContainer.is("body, html")) {
                    blueslip.warn("Please wrap progressive scrolling lists in an element with 'max-height' attribute. Error found in:\n" + blueslip.preview_node($container));
                    break;
                }

                if ($nearestScrollingContainer.css("max-height") !== "none") {
                    break;
                }

                $nearestScrollingContainer = $nearestScrollingContainer.parent();
            }

            // on scroll of the nearest scrolling container, if it hits the bottom
            // of the container then fetch a new block of items and render them.
            $nearestScrollingContainer.scroll(function () {
                if (this.scrollHeight - (this.scrollTop + this.clientHeight) < 10) {
                    prototype.render();
                }
            });

            if (opts.filter.element) {
                opts.filter.element.on(opts.filter.event || "input", function () {
                    const self = this;
                    const value = self.value.toLocaleLowerCase();

                    // run the sort algorithm that was used last, which is done
                    // by passing `undefined` -- which will make it use the params
                    // from the last sort.
                    // it will then also not run an update in the DOM (because we
                    // pass `true`), because it will update regardless below at
                    // `prototype.init()`.
                    prototype.sort(undefined, meta.prop, true);
                    filter_list(value);

                    // clear and re-initialize the list with the newly filtered subset
                    // of items.
                    prototype.init();

                    if (opts.filter.onupdate) {
                        opts.filter.onupdate();
                    }
                });
            }

            return this;
        },
    };

    prototype.__set_events();

    // add built-in generic sort functions.
    prototype.add_generic_sort_function("alphabetic", function (prop) {
        return function (a, b) {
            // The conversion to uppercase helps make the sorting case insensitive.
            const str1 = a[prop].toUpperCase();
            const str2 = b[prop].toUpperCase();

            if (str1 === str2) {
                return 0;
            } else if (str1 > str2) {
                return 1;
            }

            return -1;
        };
    });

    prototype.add_generic_sort_function("numeric", function (prop) {
        return function (a, b) {
            if (parseFloat(a[prop]) > parseFloat(b[prop])) {
                return 1;
            } else if (parseFloat(a[prop]) === parseFloat(b[prop])) {
                return 0;
            }

            return -1;
        };
    });

    // Save the instance for potential future retrieval if a name is provided.
    if (opts.name) {
        DEFAULTS.instances[opts.name] = prototype;
    }

    // Attach click handler to column heads for sorting rows accordingly
    if (opts.parent_container) {
        opts.parent_container.on("click", "[data-sort]", exports.handle_sort);
    }

    return prototype;
};

exports.get = function (name) {
    return DEFAULTS.instances[name] || false;
};

exports.handle_sort = function () {
    /*
        one would specify sort parameters like this:
            - name => sort alphabetic.
            - age  => sort numeric.

        you MUST specify the `data-list-render` in the `.progressive-table-wrapper`

        <div class="progressive-table-wrapper" data-list-render="some-list">
            <table>
                <thead>
                    <th data-sort="alphabetic" data-sort-prop="name"></th>
                    <th data-sort="numeric" data-sort-prop="age"></th>
                </thead>
                <tbody></tbody>
            </table>
        </div>
        */
    const $this = $(this);
    const sort_type = $this.data("sort");
    const prop_name = $this.data("sort-prop");
    const list_name = $this.closest(".progressive-table-wrapper").data("list-render");

    const list = exports.get(list_name);

    if (!list) {
        blueslip.error("Error. This `.progressive-table-wrapper` has no `data-list-render` attribute.");
        return;
    }

    if ($this.hasClass("active")) {
        if (!$this.hasClass("descend")) {
            $this.addClass("descend");
        } else {
            $this.removeClass("descend");
        }

        list.reverse();
        // Table has already been sorted by this property; do not re-sort.
        return;
    }

    // if `prop_name` is defined, it will trigger the generic codepath,
    // and not if it is undefined.
    list.sort(sort_type, prop_name);

    $this.siblings(".active").removeClass("active");
    $this.addClass("active");
};

window.list_render = exports;
