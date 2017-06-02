var EventSystem = (function (ui) {
    return {
        color_button: function (color_block) {
            var ev = {};
            ev[T.isMobile ? "click" : "dblclick"] = {
                switch_format: function () {
                    var color = this.innerText.trim();
                    if (T.color.format(color) === "hex") {
                        this.innerText = T.color.hex_to_rgb(color);
                    } else {
                        this.innerText = T.color.rgb_to_hex(color);
                    }
                    ui.note.position(this);
                }
            };

            E(color_block).add(ev);
        },
        copy_button: function (button, code) {
            E(button).add({
                click: {
                    copy: function () {
                        ui.copy_to_clipboard(code);
                    }
                }
            });
        },
        class_button: function (class_button, container, component) {

            var set_namespace = function (namespace, $component, $preview) {
                // get the new namespace wrapper.
                var payload = NamespaceBuilder(namespace),
                    $component_box = $preview.closest(".component");

                // remove the component gracefully.
                $component.remove();
                // add the component to the new payload inner scope.
                $(payload.scope).append($component);
                // remove all old scopes from .styleguide-preview.
                $preview.html("").append(payload.scope);

                if (namespace) {
                    $component_box.find(".namespace-warning")
                        .html("Inside the <code>" + namespace + "</code> namespace.");

                    $component_box.find(".ind-class").each(function () {
                        var o_ns = $(this.get("name")).data("namespace");
                        if (o_ns.length > 0 && o_ns !== namespace) {
                            $(this).removeClass("sea-green").addClass("black");
                            $preview.removeClass($(this.get("name")).data("name"));
                        }
                    });
                }
            };

            E(class_button).add({
                click: {
                    toggle: function () {
                        var name = $(this.get("name")).data("name"),
                            namespace = $(this.get("name")).data("namespace"),
                            $component = $(component),
                            $preview = $component.closest(".styleguide-preview"),
                            $section = $(this).closest(".section");

                        if ($(this).hasClass("black")) {
                            set_namespace(namespace, $component, $preview);
                        } else {
                            var list = $preview.find("*");
                            list[list.length - 2].appendChild(component);
                            console.log(list, list.length - 2);
                        }

                        $(this).toggleClass("black sea-green");
                        $(component).toggleClass(name);

                        container.set("innerText", {
                            code: component.outerHTML
                        });

                        hljs.highlightBlock(container.get("code"));
                        ui.note.hide();
                    }
                },
                hover: {
                    note: {
                        hover: function () {
                            ui.note.show("Click to toggle this class.", this);
                        },
                        unhover: function () {
                            ui.note.hide();
                        }
                    }
                }
            });
        },
        fragment: function (fragment) {
            E(fragment).add({
                hover: {
                    note: {
                        hover: function () {
                            ui.note.show("Type to change text samples.", this);
                        },
                        unhover: function () {
                            ui.note.hide();
                        }
                    }
                },
                click: {
                  hide_note: function () {
                    ui.note.hide();
                  }
                }
            });
        },
        show_more_font: function (show_more_button, alphabet) {
            E(show_more_button).add({
                click: {
                    toggle: function () {
                        if (alphabet.classList.contains("hidden")) {
                            this.innerHTML = "Show Less";
                            alphabet.classList.remove("hidden");
                        } else {
                            this.innerHTML = "Show More";
                            alphabet.classList.add("hidden");
                        }
                    }
                }
            });
        }
    };
});