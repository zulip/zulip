var EventSystem = function (node) {
    var meta = {
        events: {}
    };

    var simulated_events = {
        hover: function (node, hover, unhover) {
            node.addEventListener("mouseenter", function (e) {
                hover.call(this, e);
            });

            node.addEventListener("mouseleave", function (e) {
                unhover.call(this, e);
            });
        }
    };

    var funcs = {
        find: function (type, name) {
            if (meta.events[type]) {
                var arr = meta.events[type],
                    x;

                for (x = 0; x < arr.length; x++) {
                    if (arr[x].name === name) {
                        return arr[x].func;
                    }
                }
            }
            return false;
        },
        error: {
            __register: function (message) {
                console.warn(message);
            },
            event_exists: function (type, name) {
                this.__register("Error. The event of type '" + type + "' and name '" + name + "' already exists.");
            },
            event_not_exists: function (type, name) {
                this.__register("Error. The event of type '" + type + "' and name '" + name + "' does not exist.");
            }
        },
        add_event: function (type, name, func) {
            if (!meta.events[type]) {
                meta.events[type] = [];
            }

            if (!funcs.find(type, name)) {
                meta.events[type].push({
                    name: name,
                    func: func
                });

                if (type === "hover") {
                    simulated_events.hover(node, func.hover, func.unhover);
                }
                node.addEventListener(type, func);
            } else {
                funcs.error.event_exists(type, name);
            }
        }
    };

    return {
        add: function (_, _name, func) {
            if (typeof _ === "object") {
                for (var type in _) {
                    for (var name in _[type]) {
                        funcs.add_event(type, name, _[type][name]);
                    }
                }
            } else {
                funcs.add_event(_, _name, func);
            }

            return this;
        },

        remove: function (type, name) {
            var func = funcs.find(type, name);

            if (func) {
                node.removeEventListener(type, func);
            } else {
                funcs.error.event_not_exists(type, name);
            }

            return this;
        }
    };
};

var E = EventSystem;
