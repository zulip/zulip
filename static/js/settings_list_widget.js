const DropdownListWidget = function (opts) {
    opts = Object.assign({
        null_value: null,
        render_text: (item_name) => item_name,
    }, opts);
    opts.container_id = `${opts.setting_name}_widget`;
    opts.value_id = `id_${opts.setting_name}`;

    const render_dropdown_list = require("../templates/settings/dropdown_list.hbs");

    const setup = () => {
        // populate the dropdown
        const dropdown_list_body = $(`#${opts.container_id} .dropdown-list-body`).expectOne();
        const search_input = $(`#${opts.container_id} .dropdown-search > input[type=text]`);
        list_render.create(dropdown_list_body, opts.data, {
            name: `${opts.setting_name}_list`,
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

        $(`#${opts.container_id} .dropdown-toggle`).click(function () {
            search_input.val("").trigger("input");
        });
    };

    const render = (value) => {
        $(`#${opts.container_id} #${opts.value_id}`).data("value", value);

        const elem = $(`#${opts.container_id} #${opts.setting_name}_name`);

        if (!value || value === opts.null_value) {
            elem.text(opts.default_text);
            elem.addClass("text-warning");
            elem.closest('.input-group').find('.dropdown_list_reset_button').hide();
            return;
        }

        // Happy path
        const item = opts.data.find(x => x.value === value.toString());
        const text = opts.render_text(item.name);
        elem.text(text);
        elem.removeClass('text-warning');
        elem.closest('.input-group').find('.dropdown_list_reset_button').show();
    };

    const update = (value) => {
        render(value);
        settings_org.save_discard_widget_status_handler($(`#org-${opts.subsection}`));
    };

    const register_event_handlers = () => {
        $(`#${opts.container_id} .dropdown-list-body`).on("click keypress", ".list_item", function (e) {
            const setting_elem = $(this).closest(`.${opts.setting_name}_setting`);
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
        $(`#${opts.container_id} .dropdown_list_reset_button`).click(function () {
            update(opts.null_value);
        });
    };

    const value = () => {
        let val = $(`#${opts.container_id} #${opts.value_id}`).data('value');
        if (val === null) {
            val = '';
        }
        return val;
    };

    return {
        setup,
        render,
        register_event_handlers,
        value,
    };
};

window.settings_list_widget = DropdownListWidget;
