import $ from "jquery";

import render_dropdown_list from "../templates/settings/dropdown_list.hbs";

import * as blueslip from "./blueslip";
import * as ListWidget from "./list_widget";

export const DropdownListWidget = function ({
    widget_name,
    data,
    default_text,
    render_text = (item_name) => item_name,
    null_value = null,
    include_current_item = true,
    value,
    on_update = () => {},
}) {
    const container_id = `${widget_name}_widget`;
    const value_id = `id_${widget_name}`;
    if (value === undefined) {
        value = null_value;
        blueslip.warn("dropdown-list-widget: Called without a default value; using null value");
    }

    const render_default_text = (elem) => {
        elem.text(default_text);
        elem.addClass("text-warning");
        elem.closest(".input-group").find(".dropdown_list_reset_button:enabled").hide();
    };

    const render = (value) => {
        $(`#${CSS.escape(container_id)} #${CSS.escape(value_id)}`).data("value", value);

        const elem = $(`#${CSS.escape(container_id)} #${CSS.escape(widget_name)}_name`);

        if (!value || value === null_value) {
            render_default_text(elem);
            return;
        }

        // Happy path
        const item = data.find((x) => x.value === value.toString());

        if (item === undefined) {
            render_default_text(elem);
            return;
        }

        const text = render_text(item.name);
        elem.text(text);
        elem.removeClass("text-warning");
        elem.closest(".input-group").find(".dropdown_list_reset_button:enabled").show();
    };

    const update = (value) => {
        render(value);
        on_update(value);
    };

    const register_event_handlers = () => {
        $(`#${CSS.escape(container_id)} .dropdown-list-body`).on(
            "click keypress",
            ".list_item",
            function (e) {
                const setting_elem = $(this).closest(`.${CSS.escape(widget_name)}_setting`);
                if (e.type === "keypress") {
                    if (e.key === "Enter") {
                        setting_elem.find(".dropdown-menu").dropdown("toggle");
                    } else {
                        return;
                    }
                }
                const value = $(this).attr("data-value");
                update(value);
            },
        );
        $(`#${CSS.escape(container_id)} .dropdown_list_reset_button`).on("click", (e) => {
            update(null_value);
            e.preventDefault();
        });
    };

    const setup = () => {
        // populate the dropdown
        const dropdown_list_body = $(
            `#${CSS.escape(container_id)} .dropdown-list-body`,
        ).expectOne();
        const search_input = $(`#${CSS.escape(container_id)} .dropdown-search > input[type=text]`);
        const dropdown_toggle = $(`#${CSS.escape(container_id)} .dropdown-toggle`);
        const get_data = (data) => {
            if (include_current_item) {
                return data;
            }
            return data.filter((x) => x.value !== value.toString());
        };

        ListWidget.create(dropdown_list_body, get_data(data), {
            name: `${CSS.escape(widget_name)}_list`,
            modifier(item) {
                return render_dropdown_list({item});
            },
            filter: {
                element: search_input,
                predicate(item, value) {
                    return item.name.toLowerCase().includes(value);
                },
            },
            simplebar_container: $(`#${CSS.escape(container_id)} .dropdown-list-wrapper`),
        });
        $(`#${CSS.escape(container_id)} .dropdown-search`).on("click", (e) => {
            e.stopPropagation();
        });

        dropdown_toggle.on("click", () => {
            search_input.val("").trigger("input");
        });

        dropdown_toggle.on("focus", (e) => {
            // On opening a Bootstrap Dropdown, the parent element receives focus.
            // Here, we want our search input to have focus instead.
            e.preventDefault();
            // This function gets called twice when focusing the
            // dropdown, and only in the second call is the input
            // field visible in the DOM; so the following visibility
            // check ensures we wait for the second call to focus.
            if (dropdown_list_body.is(":visible")) {
                search_input.trigger("focus");
            }
        });

        search_input.on("keydown", (e) => {
            const {key, keyCode, which} = e;
            const navigation_keys = ["ArrowUp", "ArrowDown", "Escape"];
            if (!navigation_keys.includes(key)) {
                return;
            }
            e.preventDefault();
            e.stopPropagation();

            // We pass keyCode instead of key here because the outdated
            // bootstrap library we have at static/third/ still uses the
            // deprecated keyCode & which properties.
            const custom_event = new $.Event("keydown.dropdown.data-api", {keyCode, which});
            dropdown_toggle.trigger(custom_event);
        });

        render(value);
        register_event_handlers();
    };

    const get_value = () => {
        let val = $(`#${CSS.escape(container_id)} #${CSS.escape(value_id)}`).data("value");
        if (val === null) {
            val = "";
        }
        return val;
    };

    // Run setup() automatically on initialization.
    setup();

    return {
        render,
        value: get_value,
        update,
    };
};
