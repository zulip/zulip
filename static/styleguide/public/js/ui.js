var UIRender = function (templates) {
    var meta = {
        template: templates
    };

    var funcs = {
        note: (function () {
            var $note = $("#note");

            return {
                // block width isn't the width of the note element, but rather the element
                // that it should be centered vertically with.
                show: function (text, node, config) {
                    config = config || {};

                    var $node = $(node),
                        y = $node.offset().top + $node.outerHeight() + (config.top || 15),
                        x = $node.offset().left,
                        block_width = config.align === "left" ? 0 : node.offsetWidth;

                    $note.text(text).css({
                        top: y + "px",
                        left: (x - 105 + (block_width || 0) / 2) + "px"
                    }).stop().fadeIn(250);
                },
                hide: function () {
                    $note.stop().fadeOut(250, function () {
                        this.innerText = "";
                    });
                },
                position: function (node, config) {
                    config = config || {};

                    var $node = $(node),
                        y = $node.offset().top,
                        x = $node.offset().left,
                        block_width = config.align === "left" ? 0 : node.offsetWidth;

                    $note.css({
                        top: (y + config.top || 35) + "px",
                        left: (y - 105 + (block_width || 0) / 2) + "px"
                    });
                }
            };
        }()),
        _: {
            color_events: function (color_block) {
                event.color_button(color_block);
            }
        },
        render: {
            sidebar: function (container, _meta) {
                var t = meta.template;

                var group = {
                    component: t.ui.new("sidebar-group"),
                    font: t.ui.new("sidebar-group"),
                    color: t.ui.new("sidebar-group")
                };

                if (_meta.components) {
                    T.Object.forEach(_meta.components, function (o) {
                        var block = t.ui.new("ind-sidebar-component");

                        block.set("innerText", {
                            title: o.name
                        });

                        block.dataset.name = o.name;

                        group.component.set("innerText", {
                            title: "Components"
                        });
                        group.component.get("list").appendChild(block);
                    });
                }

                if (_meta.fonts) {
                    T.Array.forEach(_meta.fonts, function (o) {
                        var block = t.ui.new("ind-sidebar-font");
                        var family = o.family.split(",")[0];

                        block.set("innerText", {
                            name: o.name,
                            style: family + " " + o.weight
                        });

                        block.dataset.name = (o.name + family + o.weight).replace(/\s+/, "");

                        group.font.set("innerText", {
                            title: "Fonts"
                        });
                        group.font.get("list").appendChild(block);
                    });
                }

                (function () {
                    var block = t.ui.new("ind-sidebar-color");
                    block.dataset.name = "color_palette";

                    container.appendChild(block);

                    group.color.set("innerText", {
                        title: "Color Palette"
                    });
                    group.color.get("list").appendChild(block);
                }());

                container.appendChild(group.component);
                container.appendChild(group.font);
                container.appendChild(group.color);
            },
            class: function (payload, component, container) {
                var t = meta.template,
                    class_button = t.ui.new("ind-class");

                class_button.set("innerHTML", {
                    name: payload.class
                });

                class_button.set("data-name", {
                    name: payload.class
                });

                class_button.set("data-namespace", {
                    name: payload.namespace
                });

                event.class_button(class_button, container, component);

                return class_button;
            },
            create_table: function (block, component, props_list) {
                props_list.push("id");

                var head = ["Attribute", "Value"],
                    body = props_list.map(function (o) {
                        return [o, component.getAttribute(o) || component[o] || ""];
                    });

                if (props_list.length > 0) {
                    return T.DOM.table(head, body, null, {
                        td_event: {
                            input: {
                                val_change: function () {
                                    var prop = this.previousSibling.innerText.trim();

                                    T.DOM.set_attr(component, prop, this.innerText);
                                },
                                update_code: function () {
                                    block.set("innerText", {
                                        code: component.outerHTML
                                    });

                                    hljs.highlightBlock(block.get("code"));
                                }
                            },
                            hover: {
                                note: {
                                    hover: function () {
                                        if (this.dataset.column === "1") {
                                            funcs.note.show("Type here to change node properties.", this, {
                                                align: "left"
                                            });
                                        }
                                    },
                                    unhover: function () {
                                        funcs.note.hide();
                                    }
                                }
                            }
                        },
                    });
                } else {
                    return "<div class='dark-grey'>This element has no changeable properties. :(</div>";
                }
            },
            component_block: function (template, selector) {
                var t = meta.template;

                var default_namespace = (function () {
                    var div = document.createElement("div");
                    div.className = "new-style";
                    return div;
                })();

                var component = t.components.new(selector),
                    block = t.ui.new("component-block"),
                    table = funcs.render.create_table(block, component, template.modifiers),
                    code = block.get("code");

                // the default namespace should be appended in. Find a better
                // solution for this.
                default_namespace.appendChild(component);

                block.set("innerHTML", {
                    preview: default_namespace,
                    description: template.description,
                    title: template.name,
                    "set-props": table
                });

                block.set("innerText", {
                    code: component.outerHTML
                });

                block.dataset.name = template.name;

                // event.copy_button(block.get("copy-button"), block.get("code"));

                hljs.highlightBlock(code);

                if (template.classes.length > 0) {
                    template.classes.forEach(function (c) {
                        block.get("class-list").appendChild(funcs.render.class(c, component, block));
                    });
                } else {
                    block.set("innerText", {
                        "class-list": "No Classes."
                    });
                }

                return block;
            },
            font: function (font) {
                var t = meta.template;

                var block = t.ui.new("font-block"),
                    long = "The quick brown fox jumped over the lazy dog.",
                    short = "1987 &amp; Black Swans",
                    alphabet = "abcdefghijklmnopqrstuvwxyz",
                    numbers = "0123456789",
                    family = font.family.split(",")[0];

                block.set("innerHTML", {
                    title: font.name,
                    family: family,
                    weight: font.weight,
                    fragment: font.sample || short,
                    alphabet: alphabet.toUpperCase() + "<br>" +
                        alphabet.toLowerCase() + "<br>" + numbers
                });

                event.fragment(block.get("fragment"));

                var css = {
                    fontWeight: font.weight,
                    fontSize: font.size,
                    fontFamily: font.family
                };

                block.css({
                    fragment: css,
                    alphabet: css
                });

                block.dataset.name = (font.name + font.family + font.weight).replace(/\s+/, "");

                event.show_more_font(block.get("show-more"), block.get("alphabet").parentNode);

                return block;
            },
            color: function (colors) {
                var t = meta.template;

                var block = t.ui.new("color-block");

                T.Object.forEach(colors, function (o, i) {
                    var group = t.ui.new("color-group");

                    group.set("innerText", {
                        title: i
                    });

                    T.Array.forEach(o, function (color) {
                        var ind_color = t.ui.new("ind-color");

                        ind_color.css({
                            swatch: {
                                backgroundColor: color.color
                            }
                        });

                        ind_color.set("innerText", {
                            name: color.name,
                            color: color.color
                        });

                        funcs._.color_events(ind_color.get("color"));

                        group.appendChild(ind_color);
                    });

                    block.dataset.name = "color_palette";

                    block.get("body").appendChild(group);
                });

                return block;
            }
        },
        copy_to_clipboard: function (node) {
            var range = document.createRange();
            range.selectNode(node);
            window.getSelection().addRange(range);
            document.execCommand("copy");
        }
    };

    var prototype = {
        render: {
            component: funcs.render.component_block,
            sidebar: funcs.render.sidebar,
            font: funcs.render.font,
            color: funcs.render.color
        },
        note: funcs.note,
        copy_to_clipboard: funcs.copy_to_clipboard
    };

    // add the UI prototype to the event system so that it can use UI elements
    // such as the note.
    var event = new EventSystem(prototype);

    return prototype;
};