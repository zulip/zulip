var NamespaceBuilder = (function () {
    var funcs = {
        split: function (namespace) {
            // only grab the first selector.
            namespace = namespace.split(/,/)[0];
            return namespace.split(/\s+/);
        },
        parse_level: function (level) {
            level = level
                // remove any pseudo elements (:hover, :after, :before).
                .replace(/:.+$/, "");

            var components = [];
            (function () {
                var str = "";
                for (var x = 0; x < level.length; x++) {
                    // if an ordinary character that isn't a class (.) or id (#)
                    // delimiter, add to the current string.
                    if (!/#|\./.test(level.charAt(x))) {
                        str += level.charAt(x);
                    } else {
                        // if a string is already in the buffer push it to the
                        // components array.
                        if (str.length > 0) {
                            components.push(str);
                        }
                        // create a new string.
                        str = level.charAt(x);
                    }
                }

                if (str.length > 0) {
                    components.push(str);
                }
            })();

            return components;
        },
        construct_level: function (components) {
            var node,
                idx = 0;

            if (/^(\.|#)/.test(components[0])) {
                node = document.createElement("div");
            } else {
                node = document.createElement(components[0] || "div");
                idx++;
            }

            while (idx < components.length) {
                if (/\./.test(components[idx])) {
                    node.classList.add(components[idx].substr(1));
                } else if (/\#/.test(components[idx])) {
                    node.id = components[idx].substr(1);
                }
                idx++;
            }

            return node;
        }
    };

    return function (sel) {
        var levels = funcs.split(sel);

        var parent = null,
            last = null;

        levels.forEach(function (level) {
            var parsed = funcs.parse_level(level);
            var node = funcs.construct_level(parsed);

            if (parent === null) {
                parent = node;
            }

            if (last) {
                last.appendChild(node);
            }

            last = node;
        });

        return {
            parent: parent,
            scope: last
        };
    };
})();
