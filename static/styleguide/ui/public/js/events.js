var events = function () {
    var validator = {
      has_input: function (value, node) {
        return (value.length > 0);
      }
    };
    
    var error = {
      highlight: function (response) {
          T.Array.forEach(response.error, function (o) {
            o.node.classList.add("warning");
          });
          T.Array.forEach(response.success, function (o) {
            o.node.classList.remove("warning");
          });
      }
    };
    
    E(form.component.get("submit")).add({
        click: {
            submit: function () {
                T.V(form.component).validate({
                    component_name: validator.has_input,
                    template_name: validator.has_input
                }, { clear: true }).then(function (values) {
                    var store = template_storage.get();

                    store.component[values.component_name] = {
                        name: values.component_name,
                        template_name: values.template_name,
                        classes: values.class_list.split(/\s*,\s*/).map(function (o) {
                            return { name: o, class: o.replace(/\./, "") };
                        }),
                        modifiers: values.modifiers.split(/\s*,\s*/),
                        description: values.description
                    };

                    window.$component = actions.build.component(store.component[values.component_name]);
                    $("#config_preview").append($component);
                    template_storage.set(store);
                    template_storage.update(actions.update_config_text);
                }).error(error.highlight);
            }
        }
    });
    
    E(form.font.get("submit")).add({
        click: {
            submit: function () {
                T.V(form.font).validate({
                    name: validator.has_input,
                    font_family: validator.has_input,
                    font_size: validator.has_input,
                    font_weight: validator.has_input
                }, { clear: true }).then(function (values) {
                    var store = template_storage.get();

                    store.font.push({
                        name: values.name,
                        family: values.font_family,
                        weight: values.font_weight,
                        size: values.font_size,
                        sample: values.sample_text
                    });

                    template_storage.set(store);
                    template_storage.update(actions.update_config_text);
                }).error(error.highlight);
            }
        }
    });

    E(form.color.get("submit")).add({
        click: {
            submit: function () {
                T.V(form.color).validate({
                    name: validator.has_input,
                    value: function (value) {
                      return /(rgba*\(.+\))|(#.{3})/.test(value);
                    },
                    palette: validator.has_input
                }, { clear: true }).then(function (values) {
                    var store = template_storage.get();
                    console.log(store.colors, values.palette);
                    store.colors[values.palette].push({
                        name: values.name,
                        value: values.value
                    });

                    template_storage.set(store);
                    template_storage.update(actions.update_config_text);
                }).error(error.highlight);
            }
        }
    });
    
    var fade_in_element = function ($elem, $parent) {
        console.log($elem.hasClass("primary"));
        if (!$elem.hasClass("primary")) {
            $parent.find(".secondary").removeClass("secondary");
            $parent.find(".primary").removeClass("primary").addClass("secondary");

            $elem.addClass("fadeInUp primary");
            setTimeout(function () {
                $elem.removeClass("fadeInUp");
            }, 500);  
        }
    };

    $("#init_block .ind-tab").click(function () {
        $(".ind-tab.color").removeClass("color");
        $(this).addClass("color");

        fade_in_element($("#init_block [data-tab='" + this.dataset.trigger + "']"), $(this).parent());
    });
    
    $("#config_preview .ind-tab").click(function () {
        $("#config_preview .ind-tab.color").removeClass("color");
        $(this).addClass("color");

        fade_in_element($("#config_preview [data-tab='" + this.dataset.trigger + "']"), $(this).parent());
    });
};