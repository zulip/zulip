var list_render = (function () {
    var DEFAULTS = {
        LOAD_COUNT: 20,
        instances: {},
    };

    // @params
    // container: jQuery object to append to.
    // list: The list of items to progressively append.
    // opts: An object of random preferences.
    var func = function ($container, list, opts) {
        // this memoizes the results and will return a previously invoked
        // instance's prototype.
        if (opts.name && DEFAULTS.instances[opts.name]) {
            return DEFAULTS.instances[opts.name].data(list);
        }

        var meta = {
            offset: 0,
            listRenders: {},
            filtered_list: list,
        };

        // this is a list that could be filtered by the value of the
        // `opts.filter.element` this value should never change.
        Object.defineProperty(meta, "list", {
            configurable: false,
            writeable: false,
            value: list,
        });

        if (!opts) {
            return;
        }

        // we want to assume below that `opts.filter` exists, but may not necessarily
        // have any defined specs.
        if (!opts.filter) {
            opts.filter = {};
        }

        var $nearestScrollingContainer = $container;
        while ($nearestScrollingContainer.length) {
            if ($nearestScrollingContainer.is("body, html")) {
                blueslip.warn("Please wrap progressive scrolling lists in an element with 'max-height' attribute. Error found in:\n" + util.preview_node($container));
                break;
            }

            if ($nearestScrollingContainer.css("max-height") !== "none") {
                break;
            }

            $nearestScrollingContainer = $nearestScrollingContainer.parent();
        }

        var prototype = {
            // this is a function that reads the provided list (in the scope
            // directly above) and renders the next block of messages automatically
            // into the specified contianer.
            render: function (load_count) {
                load_count = load_count || opts.load_count || DEFAULTS.LOAD_COUNT;

                // if the offset has surpassed the length of the list, stop
                // running the reducer.
                if (meta.offset > meta.filtered_list.length) {
                    return;
                }

                var slice = meta.filtered_list.slice(meta.offset, meta.offset + load_count);

                var html = _.reduce(slice, function (acc, item) {
                    var _item = opts.modifier(item);

                    // if valid jQuery selection, attempt to grab the first elem.
                    if (_item.constructor === jQuery) {
                        _item = _item[0];
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

            // this is the initialization function which tries to fill up the
            // container to its max height with elements so that scrolling can
            // be detected.
            init: function () {
                this.render(50);
                return this;
            },

            filter: function (map_function) {
                meta.filtered_list = meta.list(map_function);
            },

            // reset the data associated with a list. This is so that instead of
            // initializing a new progressive list render instance, you can just
            // update the data of an existing one.
            data: function (data) {
                if (Array.isArray(data)) {
                    meta.list = data;
                    meta.filtered_list = data;

                    prototype
                        .clear()
                        .init();

                    return this;
                }

                blueslip.warn("The data object provided to the progressive" +
                              " list render is invalid");
                return this;
            },

            // clear the HTML and reset the offset. This is good for DOM memory
            // cleanup.
            clear: function () {
                $container.html("");
                meta.offset = 0;

                return this;
            },
        };

        // on scroll of the nearest scrolling container, if it hits the bottom
        // of the container then fetch a new block of items and render them.
        $nearestScrollingContainer.scroll(function () {
            if (this.scrollHeight - (this.scrollTop + this.clientHeight) < 10) {
                prototype.render();
            }
        });

        if (opts.filter.element) {
            opts.filter.element.on(opts.filter.event || "input", function () {
                var self = this;
                var value = self.value.toLowerCase();

                meta.filtered_list = meta.list.filter(function (item) {
                    if (opts.filter.callback) {
                        return opts.filter.callback(item, value);
                    }

                    return !!item.toLowerCase().match(value);
                });

                // clear and re-initialize the list with the newly filtered subset
                // of items.
                prototype
                    .clear()
                    .init();
            });
        }


        // if a name is included to define the instance, set it into the map so
        // that it can be retrieved later from another place.
        if (opts.name) {
            DEFAULTS.instances[opts.name] = prototype;
        }

        return prototype;
    };

    func.get = function (name) {
        return DEFAULTS.instances[name] || false;
    };

    // this can delete list render issues and free up memory if needed.
    func.delete = function (name) {
        if (DEFAULTS.instances[name]) {
            delete DEFAULTS.instances[name];
            return true;
        }

        blueslip.warn("The progressive list render instance with the name '" +
                      name + "' does not exist.");
        return false;
    };

    return func;
}());

if (typeof module !== 'undefined') {
    module.exports = list_render;
}
