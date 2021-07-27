import $ from "jquery";

import render_dropdown_list from "../templates/settings/dropdown_list.hbs";

import * as blueslip from "./blueslip";
import * as ListWidget from "./list_widget";

export function DropdownListWidget({
    widget_name,
    data,
    default_text,
    render_text = (item_name) => item_name,
    null_value = null,
    include_current_item = true,
    value,
    on_update = () => {},
}) {
    // Initializing values
    this.widget_name = widget_name;
    this.data = data;
    this.default_text = default_text;
    this.render_text = render_text;
    this.null_value = null_value;
    this.include_current_item = include_current_item;
    this.initial_value = value;
    this.on_update = on_update;

    this.container_id = `${widget_name}_widget`;
    this.value_id = `id_${widget_name}`;

    if (value === undefined) {
        this.initial_value = null_value;
        blueslip.warn("dropdown-list-widget: Called without a default value; using null value");
    }

    // Setting up dropdown_list_widget
    this.setup();
}

DropdownListWidget.prototype.render_default_text = function (elem) {
    elem.text(this.default_text);
    elem.addClass("text-warning");
    elem.closest(".input-group").find(".dropdown_list_reset_button:enabled").hide();
};

DropdownListWidget.prototype.render = function (value) {
    $(`#${CSS.escape(this.container_id)} #${CSS.escape(this.value_id)}`).data("value", value);

    const elem = $(`#${CSS.escape(this.container_id)} #${CSS.escape(this.widget_name)}_name`);

    if (!value || value === this.null_value) {
        this.render_default_text(elem);
        return;
    }

    // Happy path
    const item = this.data.find((x) => x.value === value.toString());

    if (item === undefined) {
        this.render_default_text(elem);
        return;
    }

    const text = this.render_text(item.name);
    elem.text(text);
    elem.removeClass("text-warning");
    elem.closest(".input-group").find(".dropdown_list_reset_button:enabled").show();
};

DropdownListWidget.prototype.update = function (value) {
    this.render(value);
    this.on_update(value);
};

DropdownListWidget.prototype.register_event_handlers = function () {
    $(`#${CSS.escape(this.container_id)} .dropdown-list-body`).on(
        "click keypress",
        ".list_item",
        (e) => {
            const setting_elem = $(e.currentTarget).closest(
                `.${CSS.escape(this.widget_name)}_setting`,
            );
            if (e.type === "keypress") {
                if (e.key === "Enter") {
                    setting_elem.find(".dropdown-menu").dropdown("toggle");
                } else {
                    return;
                }
            }
            const value = $(e.currentTarget).attr("data-value");
            this.update(value);
        },
    );
    $(`#${CSS.escape(this.container_id)} .dropdown_list_reset_button`).on("click", (e) => {
        this.update(this.null_value);
        e.preventDefault();
    });
};

DropdownListWidget.prototype.setup_dropdown_widget = function (data) {
    const dropdown_list_body = $(
        `#${CSS.escape(this.container_id)} .dropdown-list-body`,
    ).expectOne();
    const search_input = $(`#${CSS.escape(this.container_id)} .dropdown-search > input[type=text]`);
    const get_data = () => {
        if (this.include_current_item) {
            return data;
        }
        return data.filter((x) => x.value !== this.value.toString());
    };

    ListWidget.create(dropdown_list_body, get_data(data), {
        name: `${CSS.escape(this.widget_name)}_list`,
        modifier(item) {
            return render_dropdown_list({item});
        },
        filter: {
            element: search_input,
            predicate(item, value) {
                return item.name.toLowerCase().includes(value);
            },
        },
        simplebar_container: $(`#${CSS.escape(this.container_id)} .dropdown-list-wrapper`),
    });
};

// Sets the focus to the ListWidget input once the dropdown button is clicked.
DropdownListWidget.prototype.dropdown_toggle_click_handler = function () {
    const dropdown_toggle = $(`#${CSS.escape(this.container_id)} .dropdown-toggle`);
    const search_input = $(`#${CSS.escape(this.container_id)} .dropdown-search > input[type=text]`);

    dropdown_toggle.on("click", () => {
        search_input.val("").trigger("input");
    });
};

DropdownListWidget.prototype.setup = function () {
    // populate the dropdown
    const dropdown_list_body = $(
        `#${CSS.escape(this.container_id)} .dropdown-list-body`,
    ).expectOne();
    const search_input = $(`#${CSS.escape(this.container_id)} .dropdown-search > input[type=text]`);
    const dropdown_toggle = $(`#${CSS.escape(this.container_id)} .dropdown-toggle`);

    this.setup_dropdown_widget(this.data);

    $(`#${CSS.escape(this.container_id)} .dropdown-search`).on("click", (e) => {
        e.stopPropagation();
    });

    this.dropdown_toggle_click_handler();

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

    this.render(this.initial_value);
    this.register_event_handlers();
};

// Returns the updated value
DropdownListWidget.prototype.value = function () {
    let val = $(`#${CSS.escape(this.container_id)} #${CSS.escape(this.value_id)}`).data("value");
    if (val === null) {
        val = "";
    }
    return val;
};
