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
            E(class_button).add({
                click: {
                    toggle: function () {
                        var $name = $(this).find("span").data("name");

                        $(this).toggleClass("black solid sea-green");
                        $(component).toggleClass($name);

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