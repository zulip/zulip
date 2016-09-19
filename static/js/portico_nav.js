var Dropdown = function () {
    // where internal variables are stored.
    var meta = {
        category: []
    };

    var errors = [];

    // internal non-public functions.
    var funcs = {
        // find a particular category and return a pointer if found.
        find: function (category) {
            var ret = false;

            meta.category.forEach(function (cat) {
                if (cat.name === category) {
                    ret = cat;
                }
            });

            return ret;
        },
        // insert a list-item to a category in object form with attributes "name"
        // and "addr".
        insert_item: function (category, obj) {
            var bin = funcs.find(category);
            if (bin) {
                if (obj.name && obj.addr && Object.keys(obj).length >= 2) {
                    bin.items.push(obj);
                } else {
                    errors.push({
                      error: "Error. The item object is not valid. " +
                             "Must include a 'name' and 'addr' property."
                    });
                }
            } else {
                errors.push({
                  error: "A category with the name '" + category +
                         "' was not found. Item '" + JSON.stringify(obj) +
                         "' was not inserted."
                });
            }

            return {
                item: funcs.insert_item.bind(null, category)
            };
        },
        // generic element builder that allows an element to be built with a tag
        // specifier and attribute object.
        element: function (tag, attr) {
            var div = document.createElement(tag || "div");

            var special = ["innerHTML", "className"];
            attr = attr || {};

            for (var x in attr) {
                if (attr.hasOwnProperty(x)) {
                    if (special.indexOf(x) === -1) {
                        div.setAttribute(x, attr[x]);
                    } else {
                        div[x] = attr[x];
                    }
                }
            }

            return div;
        },
        // create an event listener wrapper to save literally dozens of characters!
        e: function (elem) {
            return {
                on: function (type, func) {
                    elem.addEventListener(type, func);
                }
            };
        },
        // functions for rendering components (containers and lists).
        render: {
            container: function (category) {
                var div = funcs.element("div", {
                    id: category.toLowerCase().replace(/[^A-z]/, "_") + "_section",
                    className: "dropdown-section",
                    "data-name": category
                });

                return div;
            },
            list: function (category) {
                var bin = funcs.find(category);

                var ul = funcs.element("ul", {
                    className: "list"
                });

                bin.items.forEach(function (item) {
                    var li = funcs.element("li", {
                        className: "list-item",
                        innerHTML: "<a href='" + item.addr + "' target='" + (item.target || "") + "'>" + item.name + "</a>"
                    });

                    ul.appendChild(li);
                });

                return ul;
            }
        }
    };

    return {
        add: {
            category: function (name) {
                if (!funcs.find(name)) {
                    meta.category.push({
                        name: name,
                        items: [],
                        div: null
                    });
                }

                return {
                    item: funcs.insert_item.bind(null, name)
                };
            }
        },
        get: function () {
            return meta.category;
        },
        render: function () {
            var dropdown = funcs.element("div", {
                className: "dropdown"
            });

            meta.category.forEach(function (block) {
                block.div = funcs.render.container(block.name);
                var list = funcs.render.list(block.name);
                block.div.appendChild(list);

                dropdown.appendChild(block.div);
            });

            return dropdown;
        }
    };
};

(function () {
    var dropdown = new Dropdown();

    dropdown.add.category("About Zulip")
        .item({ name: "Features", addr: "/features" });

    dropdown.add.category("Integrations")
        .item({ name: "API", addr: "/api" })
        .item({ name: "Endpoints", addr: "/api/endpoints" })
        .item({ name: "Contributing", addr: "http://zulip.readthedocs.io/en/latest/integration-guide.html", target: "_blank" });

    dropdown.add.category("Open Source")
        .item({ name: "Something", addr: "/something" });

    dropdown.add.category("Apps")
        .item({ name: "Mac", addr: "/apps#mac" })
        .item({ name: "Windows", addr: "/apps#windows" })
        .item({ name: "Linux", addr: "/apps#linux" })
        .item({ name: "iOS", addr: "/apps#iphone" })
        .item({ name: "Android", addr: "/apps#android" });

    var dropdown_elem = dropdown.render();

    var overlay = document.querySelector(".overlay");
    $(".dropdown-container").append(dropdown_elem);

    (function () {
        var last = null;

        var sel = $([dropdown_elem, overlay]);

        $("body").click(function (e) {
            var $target = $(e.target);
            var name = $target.text().trim();

            if ($target.hasClass("trigger")) {
                $(".dropdown-section.highlighted").removeClass("highlighted");

                if (last === name) {
                    sel.removeClass("shown");
                    last = null;
                } else {
                    $(".dropdown [data-name='" + name + "']").addClass("highlighted");
                    sel.addClass("shown");
                    last = name;
                }
            } else if (!$target.is(".dropdown, .dropdown *") && !($target.is(".trigger") && last !== "name")) {
                sel.removeClass("shown");
                last = null;
            }
        });

        $("body").on("click", ".dropdown-section", function (e) {
            $(".dropdown-section.highlighted").removeClass("highlighted");
            $(this).addClass("highlighted");
            e.stopPropagation();
        });
    }());
}());
