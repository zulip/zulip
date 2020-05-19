const DropdownListWidget = function (opts) {
    const init = () => {
        // Run basic sanity checks on opts, and set up sane defaults.
        opts = Object.assign({
            null_value: null,
            render_text: (item_name) => item_name,
            on_update: () => {},
        }, opts);
        opts.container_id = `${opts.widget_name}_widget`;
        opts.value_id = `id_${opts.widget_name}`;
        if (opts.value === undefined) {
            opts.value = opts.null_value;
            blueslip.warn('dropdown-list-widget: Called without a default value; using null value');
        }
    };
    init();

    const render_dropdown_list = require("../templates/settings/dropdown_list.hbs");

    const render = (value) => {
        $(`#${opts.container_id} #${opts.value_id}`).data("value", value);

        const elem = $(`#${opts.container_id} #${opts.widget_name}_name`);

        if (!value || value === opts.null_value) {
            elem.text(opts.default_text);
            elem.addClass("text-warning");
            elem.closest('.input-group').find('.dropdown_list_reset_button:not([disabled])').hide();
            return;
        }

        // Happy path
        const item = opts.data.find(x => x.value === value.toString());
        const text = opts.render_text(item.name);
        elem.text(text);
        elem.removeClass('text-warning');
        elem.closest('.input-group').find('.dropdown_list_reset_button:not([disabled])').show();
    };

    const update = (value) => {
        render(value);
        opts.on_update(value);
    };

    const register_event_handlers = () => {
        $(`#${opts.container_id} .dropdown-list-body`).on("click keypress", ".list_item", function (e) {
            const setting_elem = $(this).closest(`.${opts.widget_name}_setting`);
            if (e.type === "keypress") {
                if (e.which === 13) {
                    setting_elem.find(".dropdown-menu").dropdown("toggle");
                } else {
                    return;
                }
            }
            const value = $(this).attr('data-value');
            update(value);
        });
        $(`#${opts.container_id} .dropdown_list_reset_button`).click(function (e) {
            update(opts.null_value);
            e.preventDefault();
        });
    };

    const setup = () => {
        // populate the dropdown
        const dropdown_list_body = $(`#${opts.container_id} .dropdown-list-body`).expectOne();
        const search_input = $(`#${opts.container_id} .dropdown-search > input[type=text]`);
        const dropdown_toggle = $(`#${opts.container_id} .dropdown-toggle`);

        list_render.create(dropdown_list_body, opts.data, {
            name: `${opts.widget_name}_list`,
            modifier: function (item) {
                return render_dropdown_list({ item: item });
            },
            filter: {
                element: search_input,
                predicate: function (item, value) {
                    return item.name.toLowerCase().includes(value);
                },
            },
        });
        $(`#${opts.container_id} .dropdown-search`).click(function (e) {
            e.stopPropagation();
        });

        dropdown_toggle.click(function () {
            search_input.val("").trigger("input");
        });

        dropdown_toggle.focus(function (e) {
            // On opening a Bootstrap Dropdown, the parent element recieves focus.
            // Here, we want our search input to have focus instead.
            e.preventDefault();
            search_input.focus();
        });

        search_input.keydown(function (e) {
            if (!/(38|40|27)/.test(e.keyCode)) {
                return;
            }
            e.preventDefault();
            const custom_event = jQuery.Event("keydown.dropdown.data-api", {
                keyCode: e.keyCode,
                which: e.keyCode,
            });
            dropdown_toggle.trigger(custom_event);
        });

        render(opts.value);
        register_event_handlers();
    };

    const value = () => {
        let val = $(`#${opts.container_id} #${opts.value_id}`).data('value');
        if (val === null) {
            val = '';
        }
        return val;
    };

    // Run setup() automatically on initialization.
    setup();

    return {
        render,
        value,
        update,
    };
};

window.dropdown_list_widget = DropdownListWidget;
