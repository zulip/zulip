import $ from "jquery";
import _ from "lodash";
import tippy from "tippy.js";

import render_dropdown_list from "../templates/settings/dropdown_list.hbs";

import * as blueslip from "./blueslip";
import {$t} from "./i18n";
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

DropdownListWidget.prototype.render_default_text = function ($elem) {
    $elem.text(this.default_text);
    $elem.addClass("text-warning");
    $elem.closest(".input-group").find(".dropdown_list_reset_button").hide();
};

DropdownListWidget.prototype.render = function (value) {
    $(`#${CSS.escape(this.container_id)} #${CSS.escape(this.value_id)}`).data("value", value);

    const $elem = $(`#${CSS.escape(this.container_id)} #${CSS.escape(this.widget_name)}_name`);

    if (!value || value === this.null_value) {
        this.render_default_text($elem);
        return;
    }

    // Happy path
    const item = this.data.find((x) => x.value === value.toString());

    if (item === undefined) {
        this.render_default_text($elem);
        return;
    }

    const text = this.render_text(item.name);
    $elem.text(text);
    $elem.removeClass("text-warning");
    $elem.closest(".input-group").find(".dropdown_list_reset_button").show();
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
            const $setting_elem = $(e.currentTarget).closest(
                `.${CSS.escape(this.widget_name)}_setting`,
            );
            if (e.type === "keypress") {
                if (e.key === "Enter") {
                    $setting_elem.find(".dropdown-menu").dropdown("toggle");
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
    const $dropdown_list_body = $(
        `#${CSS.escape(this.container_id)} .dropdown-list-body`,
    ).expectOne();
    const $search_input = $(
        `#${CSS.escape(this.container_id)} .dropdown-search > input[type=text]`,
    );
    const get_data = () => {
        if (this.include_current_item) {
            return data;
        }
        return data.filter((x) => x.value !== this.value.toString());
    };

    ListWidget.create($dropdown_list_body, get_data(data), {
        name: `${CSS.escape(this.widget_name)}_list`,
        modifier(item) {
            return render_dropdown_list({item});
        },
        filter: {
            $element: $search_input,
            predicate(item, value) {
                return item.name.toLowerCase().includes(value);
            },
        },
        $simplebar_container: $(`#${CSS.escape(this.container_id)} .dropdown-list-wrapper`),
    });
};

// Sets the focus to the ListWidget input once the dropdown button is clicked.
DropdownListWidget.prototype.dropdown_toggle_click_handler = function () {
    const $dropdown_toggle = $(`#${CSS.escape(this.container_id)} .dropdown-toggle`);
    const $search_input = $(
        `#${CSS.escape(this.container_id)} .dropdown-search > input[type=text]`,
    );

    $dropdown_toggle.on("click", () => {
        $search_input.val("").trigger("input");
    });
};

DropdownListWidget.prototype.dropdown_focus_events = function () {
    const $search_input = $(
        `#${CSS.escape(this.container_id)} .dropdown-search > input[type=text]`,
    );
    const $dropdown_menu = $(`.${CSS.escape(this.widget_name)}_setting .dropdown-menu`);

    const dropdown_elements = () => {
        const $dropdown_list_body = $(
            `#${CSS.escape(this.container_id)} .dropdown-list-body`,
        ).expectOne();

        return $dropdown_list_body.children().find("a");
    };

    // Rest of the key handlers are supported by our
    // bootstrap library.
    $dropdown_menu.on("keydown", (e) => {
        function trigger_element_focus($element) {
            e.preventDefault();
            e.stopPropagation();
            $element.trigger("focus");
        }

        switch (e.key) {
            case "ArrowDown": {
                switch (e.target) {
                    case dropdown_elements().last()[0]:
                        trigger_element_focus($search_input);
                        break;
                    case $search_input[0]:
                        trigger_element_focus(dropdown_elements().first());
                        break;
                }

                break;
            }
            case "ArrowUp": {
                switch (e.target) {
                    case dropdown_elements().first()[0]:
                        trigger_element_focus($search_input);
                        break;
                    case $search_input[0]:
                        trigger_element_focus(dropdown_elements().last());
                }

                break;
            }
            case "Tab": {
                switch (e.target) {
                    case $search_input[0]:
                        trigger_element_focus(dropdown_elements().first());
                        break;
                    case dropdown_elements().last()[0]:
                        trigger_element_focus($search_input);
                        break;
                }

                break;
            }
        }
    });
};

DropdownListWidget.prototype.setup = function () {
    // populate the dropdown
    const $dropdown_list_body = $(
        `#${CSS.escape(this.container_id)} .dropdown-list-body`,
    ).expectOne();
    const $search_input = $(
        `#${CSS.escape(this.container_id)} .dropdown-search > input[type=text]`,
    );
    const $dropdown_toggle = $(`#${CSS.escape(this.container_id)} .dropdown-toggle`);

    this.setup_dropdown_widget(this.data);

    $(`#${CSS.escape(this.container_id)} .dropdown-search`).on("click", (e) => {
        e.stopPropagation();
    });

    this.dropdown_toggle_click_handler();

    $dropdown_toggle.on("focus", (e) => {
        // On opening a Bootstrap Dropdown, the parent element receives focus.
        // Here, we want our search input to have focus instead.
        e.preventDefault();
        // This function gets called twice when focusing the
        // dropdown, and only in the second call is the input
        // field visible in the DOM; so the following visibility
        // check ensures we wait for the second call to focus.
        if ($dropdown_list_body.is(":visible")) {
            $search_input.trigger("focus");
        }
    });

    this.dropdown_focus_events();

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

export function MultiSelectDropdownListWidget({
    widget_name,
    data,
    default_text,
    null_value = null,
    on_update = () => {},
    on_close,
    value,
    limit,
}) {
    // A widget mostly similar to `DropdownListWidget` but
    // used in cases of multiple dropdown selection.

    // Initializing values specific to `MultiSelectDropdownListWidget`.
    this.limit = limit;
    this.on_close = on_close;

    // Important thing to note is that this needs to be maintained as
    // a reference type and not to deep clone it/assign it to a
    // different variable, so that it can be later referenced within
    // `list_widget` as well. The way we manage dropdown elements are
    // essentially by just modifying the values in `data_selected` variable.
    this.data_selected = []; // Populate the dropdown values selected by user.

    DropdownListWidget.call(this, {
        widget_name,
        data,
        default_text,
        null_value,
        on_update,
        value,
    });

    if (limit === undefined) {
        this.limit = 2;
        blueslip.warn(
            "Multiselect dropdown-list-widget: Called without limit value; using 2 as the limit",
        );
    }

    this.initialize_dropdown_values();
}

MultiSelectDropdownListWidget.prototype = Object.create(DropdownListWidget.prototype);

MultiSelectDropdownListWidget.prototype.initialize_dropdown_values = function () {
    // Stop the execution if value parameter is undefined and null_value is passed.
    if (!this.initial_value || this.initial_value === this.null_value) {
        return;
    }
    const $elem = $(`#${CSS.escape(this.container_id)} #${CSS.escape(this.widget_name)}_name`);

    // Push values from initial valued array to `data_selected`.
    this.data_selected.push(...this.initial_value);
    this.render_button_text($elem, this.limit);
};

// Set the button text as per the selected data.
MultiSelectDropdownListWidget.prototype.render_button_text = function ($elem, limit) {
    const items_selected = this.data_selected.length;
    let text = "";

    // Destroy the tooltip once the button text reloads.
    this.destroy_tooltip();

    if (items_selected === 0) {
        this.render_default_text($elem);
        return;
    } else if (limit >= items_selected) {
        const data_selected = this.data.filter((data) => this.data_selected.includes(data.value));
        text = data_selected.map((data) => data.name).toString();
    } else {
        text = $t({defaultMessage: "{items_selected} selected"}, {items_selected});
        this.render_tooltip();
    }

    $elem.text(text);
    $elem.removeClass("text-warning");
    $elem.closest(".input-group").find(".dropdown_list_reset_button").show();
};

// Override the DrodownListWidget `render` function.
MultiSelectDropdownListWidget.prototype.render = function (value) {
    const $elem = $(`#${CSS.escape(this.container_id)} #${CSS.escape(this.widget_name)}_name`);

    if (!value || value === this.null_value) {
        this.render_default_text($elem);
        return;
    }
    this.render_button_text($elem, this.limit);
};

MultiSelectDropdownListWidget.prototype.dropdown_toggle_click_handler = function () {
    const $dropdown_toggle = $(`#${CSS.escape(this.container_id)} .dropdown-toggle`);
    const $search_input = $(
        `#${CSS.escape(this.container_id)} .dropdown-search > input[type=text]`,
    );

    $dropdown_toggle.on("click", () => {
        this.reset_dropdown_items();
        $search_input.val("").trigger("input");
    });
};

// Cases where a user presses any dropdown item but accidentally closes
// the dropdown list.
MultiSelectDropdownListWidget.prototype.reset_dropdown_items = function () {
    // Clear the data selected and stop the execution once the user has
    // pressed the `reset` button.
    if (this.is_reset) {
        this.data_selected.splice(0, this.data_selected.length);
        return;
    }

    const original_items = this.checked_items ? this.checked_items : this.initial_value;
    const items_added = _.difference(this.data_selected, original_items);

    // Removing the unnecessary items from dropdown.
    for (const val of items_added) {
        const index = this.data_selected.indexOf(val);
        if (index > -1) {
            this.data_selected.splice(index, 1);
        }
    }

    // Items that are removed in dropdown but should have been a part of it
    const items_removed = _.difference(original_items, this.data_selected);
    this.data_selected.push(...items_removed);
};

// Override the DrodownListWidget `setup_dropdown_widget` function.
MultiSelectDropdownListWidget.prototype.setup_dropdown_widget = function (data) {
    const $dropdown_list_body = $(
        `#${CSS.escape(this.container_id)} .dropdown-list-body`,
    ).expectOne();
    const $search_input = $(
        `#${CSS.escape(this.container_id)} .dropdown-search > input[type=text]`,
    );

    ListWidget.create($dropdown_list_body, data, {
        name: `${CSS.escape(this.widget_name)}_list`,
        modifier(item) {
            return render_dropdown_list({item});
        },
        multiselect: {
            selected_items: this.data_selected,
        },
        filter: {
            $element: $search_input,
            predicate(item, value) {
                return item.name.toLowerCase().includes(value);
            },
        },
        $simplebar_container: $(`#${CSS.escape(this.container_id)} .dropdown-list-wrapper`),
    });
};

// Add the check mark to dropdown element passed.
MultiSelectDropdownListWidget.prototype.add_check_mark = function ($element) {
    const value = $element.attr("data-value");
    const $link_elem = $element.find("a").expectOne();
    $link_elem.prepend($("<i>", {class: "fa fa-check"}));
    $element.addClass("checked");
    this.data_selected.push(value);
};

// Remove the check mark from dropdown element.
MultiSelectDropdownListWidget.prototype.remove_check_mark = function ($element) {
    const $icon = $element.find("i").expectOne();
    const value = $element.attr("data-value");
    const index = this.data_selected.indexOf(value);

    if (index > -1) {
        $icon.remove();
        $element.removeClass("checked");
        this.data_selected.splice(index, 1);
    }
};

// Render the tooltip once the text changes to `n` selected.
MultiSelectDropdownListWidget.prototype.render_tooltip = function () {
    const $elem = $(`#${CSS.escape(this.container_id)}`);
    const selected_items = this.data.filter((item) => this.checked_items.includes(item.value));

    tippy($elem[0], {
        content: selected_items.map((item) => item.name).join(", "),
        placement: "top",
    });
};

MultiSelectDropdownListWidget.prototype.destroy_tooltip = function () {
    const $elem = $(`#${CSS.escape(this.container_id)}`);
    const tippy_instance = $elem[0]._tippy;
    if (!tippy_instance) {
        return;
    }

    tippy_instance.destroy();
};

MultiSelectDropdownListWidget.prototype.dropdown_focus_events = function () {
    // Main keydown event handler which transfers the focus from one child element
    // to another.

    const $search_input = $(
        `#${CSS.escape(this.container_id)} .dropdown-search > input[type=text]`,
    );
    const $dropdown_menu = $(`.${CSS.escape(this.widget_name)}_setting .dropdown-menu`);
    const $filter_button = $(`#${CSS.escape(this.container_id)} .multiselect_btn`);

    const dropdown_elements = () => {
        const $dropdown_list_body = $(
            `#${CSS.escape(this.container_id)} .dropdown-list-body`,
        ).expectOne();

        return $dropdown_list_body.children().find("a");
    };

    $dropdown_menu.on("keydown", (e) => {
        function trigger_element_focus($element) {
            e.preventDefault();
            e.stopPropagation();
            $element.trigger("focus");
        }

        switch (e.key) {
            case "ArrowDown": {
                switch (e.target) {
                    case dropdown_elements().last()[0]:
                        trigger_element_focus($filter_button);
                        break;
                    case $(`#${CSS.escape(this.container_id)} .multiselect_btn`)[0]:
                        trigger_element_focus($search_input);
                        break;
                    case $search_input[0]:
                        trigger_element_focus(dropdown_elements().first());
                        break;
                }

                break;
            }
            case "ArrowUp": {
                switch (e.target) {
                    case dropdown_elements().first()[0]:
                        trigger_element_focus($search_input);
                        break;
                    case $search_input[0]:
                        trigger_element_focus($filter_button);
                        break;
                    case $(`#${CSS.escape(this.container_id)} .multiselect_btn`)[0]:
                        trigger_element_focus(dropdown_elements().last());
                        break;
                }

                break;
            }
            case "Tab": {
                switch (e.target) {
                    case $search_input[0]:
                        trigger_element_focus(dropdown_elements().first());
                        break;
                    case $filter_button[0]:
                        trigger_element_focus($search_input);
                        break;
                }

                break;
            }
        }
    });
};

// Override the `register_event_handlers` function.
MultiSelectDropdownListWidget.prototype.register_event_handlers = function () {
    const $dropdown_list_body = $(
        `#${CSS.escape(this.container_id)} .dropdown-list-body`,
    ).expectOne();

    $dropdown_list_body.on("click keypress", ".list_item", (e) => {
        if (e.type === "keypress" && e.key !== "Enter") {
            return;
        }

        const $element = $(e.target.closest("li"));
        if ($element.hasClass("checked")) {
            this.remove_check_mark($element);
        } else {
            this.add_check_mark($element);
        }

        e.stopPropagation();
    });

    $(`#${CSS.escape(this.container_id)} .dropdown_list_reset_button`).on("click", (e) => {
        // Default back the values.
        this.is_reset = true;
        this.checked_items = undefined;

        this.update(this.null_value);
        e.preventDefault();
    });

    $(`#${CSS.escape(this.container_id)} .multiselect_btn`).on("click", (e) => {
        e.preventDefault();

        // Set the value to `false` to end the scope of the
        // `reset` button.
        this.is_reset = false;
        // We deep clone the values of `data_selected` to a new
        // variable. This is so because arrays are reference types
        // and modifying the parent array can change the values
        // within the child array. Here, `checked_items` copies over the
        // value and not just the reference.
        this.checked_items = _.cloneDeep(this.data_selected);
        this.update(this.data_selected);

        // Cases when the user wants to pass a successful event after
        // the dropdown is closed.
        if (this.on_close) {
            e.stopPropagation();
            const $setting_elem = $(e.currentTarget).closest(
                `.${CSS.escape(this.widget_name)}_setting`,
            );
            $setting_elem.find(".dropdown-menu").dropdown("toggle");

            this.on_close();
        }
    });
};

// Returns array of values selected by user.
MultiSelectDropdownListWidget.prototype.value = function () {
    let val = this.checked_items;
    // Cases taken care of -
    // - User never pressed the filter button -> We return the initial value.
    // - User pressed the `reset` button -> We return an empty array.
    if (val === undefined) {
        val = this.is_reset ? [] : this.initial_value;
    }
    return val;
};
