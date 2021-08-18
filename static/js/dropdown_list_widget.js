import $ from "jquery";

import render_multiselect_pills from "../templates/multiselect_dropdown_pills.hbs";
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

DropdownListWidget.prototype.callback_after_widget_render = function () {};

DropdownListWidget.prototype.dropdown_focus_events = function () {
    const search_input = $(`#${CSS.escape(this.container_id)} .dropdown-search > input[type=text]`);
    const dropdown_menu = $(`.${CSS.escape(this.widget_name)}_setting .dropdown-menu`);

    const dropdown_elements = () => {
        const dropdown_list_body = $(
            `#${CSS.escape(this.container_id)} .dropdown-list-body`,
        ).expectOne();

        return dropdown_list_body.children().find("a");
    };

    // Rest of the key handlers are supported by our
    // bootstrap library.
    dropdown_menu.on("keydown", (e) => {
        function trigger_element_focus(element) {
            e.preventDefault();
            e.stopPropagation();
            element.trigger("focus");
        }

        switch (e.key) {
            case "ArrowDown": {
                switch (e.target) {
                    case dropdown_elements().last()[0]:
                        trigger_element_focus(search_input);
                        break;
                    case search_input[0]:
                        trigger_element_focus(dropdown_elements().first());
                        break;
                }
                break;
            }
            case "ArrowUp": {
                switch (e.target) {
                    case dropdown_elements().first()[0]:
                        trigger_element_focus(search_input);
                        break;
                    case search_input[0]:
                        trigger_element_focus(dropdown_elements().last());
                }
                break;
            }
            case "Tab": {
                switch (e.target) {
                    case search_input[0]:
                        trigger_element_focus(dropdown_elements().first());
                        break;
                    case dropdown_elements().last()[0]:
                        trigger_element_focus(search_input);
                        break;
                }
                break;
            }
        }
    });
};

DropdownListWidget.prototype.setup = function () {
    // populate the dropdown
    const dropdown_list_body = $(
        `#${CSS.escape(this.container_id)} .dropdown-list-body`,
    ).expectOne();
    const search_input = $(`#${CSS.escape(this.container_id)} .dropdown-search > input[type=text]`);
    const dropdown_toggle = $(`#${CSS.escape(this.container_id)} .dropdown-toggle`);
    const get_data = () => {
        if (this.include_current_item) {
            return this.data;
        }
        return this.data.filter((x) => x.value !== this.value.toString());
    };

    ListWidget.create(dropdown_list_body, get_data(this.data), {
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
        callback_after_render: () => {
            this.callback_after_widget_render();
        },
    });

    $(`#${CSS.escape(this.container_id)} .dropdown-search`).on("click", (e) => {
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
    null_value = null,
    on_pill_add = () => {},
    on_pill_remove = () => {},
    value,
}) {
    // A widget mostly similar to `DropdownListWidget` but
    // used in cases of multiple dropdown selection.

    // Initializing values specific to `MultiSelectDropdownListWidget`.
    this.on_pill_add = on_pill_add;
    this.on_pill_remove = on_pill_remove;

    this.data_selected = []; // Populate the dropdown values selected by user.

    DropdownListWidget.call(this, {
        widget_name,
        data,
        null_value,
        value,
    });

    this.initialize_dropdown_values();
}

MultiSelectDropdownListWidget.prototype = Object.create(DropdownListWidget.prototype);

MultiSelectDropdownListWidget.prototype.initialize_dropdown_values = function () {
    // Stop the execution if value parameter is undefined and null_value is passed.
    if (!this.initial_value || this.initial_value === this.null_value) {
        return;
    }
    const pill_container = $("#pill-container");
    pill_container.empty();

    for (const val of this.initial_value) {
        const item = this.data.find((data_object) => data_object.value === val);
        const rendered_pill = render_multiselect_pills({
            display_value: item.name,
        });
        pill_container.append(rendered_pill);
    }

    this.data_selected.push(...this.initial_value);
};

MultiSelectDropdownListWidget.prototype.callback_after_widget_render = function () {
    const dropdown_list_body = $(
        `#${CSS.escape(this.container_id)} .dropdown-list-body`,
    ).expectOne();
    for (const item of dropdown_list_body.children()) {
        const item_value = $(item).attr("data-value");

        if (this.data_selected.includes(item_value)) {
            $(item).addClass("disabled-list-item");
        }
    }
};

MultiSelectDropdownListWidget.prototype.dropdown_focus_events = function () {
    // Main keydown event handler which transfers the focus from one child element
    // to another.

    const search_input = $(`#${CSS.escape(this.container_id)} .dropdown-search > input[type=text]`);
    const dropdown_menu = $(`.${CSS.escape(this.widget_name)}_setting .dropdown-menu`);
    const filter_icon = $(`#${CSS.escape(this.container_id)} .multiselect-icon`);
    const pill_container = $(`#${CSS.escape(this.container_id)} #pill-container`);

    const dropdown_list_elements = () => {
        const dropdown_list_body = $(
            `#${CSS.escape(this.container_id)} .dropdown-list-body`,
        ).expectOne();

        return dropdown_list_body.children().find("a");
    };

    function pill_container_items() {
        return pill_container.find(".pill");
    }

    function trigger_element_focus(e, element) {
        e.stopPropagation();
        e.preventDefault();
        element.trigger("focus");
    }

    dropdown_menu.on("keydown", (e) => {
        switch (e.key) {
            case "ArrowDown": {
                switch (e.target) {
                    case dropdown_list_elements().last()[0]:
                        trigger_element_focus(e, search_input);
                        break;
                    case search_input[0]:
                        trigger_element_focus(e, dropdown_list_elements().first());
                        break;
                }
                break;
            }
            case "ArrowUp": {
                switch (e.target) {
                    case dropdown_list_elements().first()[0]:
                        trigger_element_focus(e, search_input);
                        break;
                    case search_input[0]:
                        trigger_element_focus(e, dropdown_list_elements().last());
                        break;
                }
                break;
            }
            case "Tab": {
                switch (e.target) {
                    case search_input[0]:
                        trigger_element_focus(e, dropdown_list_elements().first());
                        break;
                }
                break;
            }

            // Close the dropdown and bring back the focus to the
            // filter button.
            case "Escape": {
                dropdown_menu.dropdown("toggle");
                trigger_element_focus(e, filter_icon);
                break;
            }

            case "ArrowRight": {
                trigger_element_focus(e, pill_container_items().first());
                dropdown_menu.dropdown("toggle");
                break;
            }
        }
    });

    pill_container.on("keydown", (e) => {
        const element = $(e.originalEvent.target);
        switch (e.key) {
            case "Tab":
            case "ArrowRight": {
                if (element[0] !== pill_container_items().last()[0] && !e.shiftKey) {
                    trigger_element_focus(e, element.next());
                }
                break;
            }
            case "ArrowLeft": {
                switch (element[0]) {
                    case pill_container_items().first()[0]:
                        trigger_element_focus(e, filter_icon);
                        break;

                    default:
                        trigger_element_focus(e, element.prev());
                }
                break;
            }
            case "Backspace": {
                switch (element[0]) {
                    case pill_container_items().first()[0]:
                        trigger_element_focus(e, filter_icon);
                        break;

                    default:
                        // Trigger the focus event previous element.
                        trigger_element_focus(e, element.prev());
                }

                // Finally, remove the element from pill container
                element.remove();
                this.enable_list_item(element.find(".pill-value"));
                break;
            }
        }
    });

    filter_icon.on("keydown", (e) => {
        switch (e.key) {
            case "ArrowRight": {
                if (pill_container_items().length > 0) {
                    trigger_element_focus(e, pill_container_items().first());
                }
                break;
            }
            case "Enter": {
                e.stopPropagation();
                dropdown_menu.dropdown("toggle");
                search_input.trigger("focus");
                break;
            }
            case "Tab": {
                if (!e.shiftKey && pill_container_items().length > 0) {
                    trigger_element_focus(e, pill_container_items().first());
                    break;
                }
            }
        }
    });
};

MultiSelectDropdownListWidget.prototype.disable_list_item = function (element, value) {
    if (!element.length > 0) {
        return;
    }
    element.addClass("disabled-list-item");
    // Trigger the callback function on adding a pill.
    this.on_pill_add(value);
};

MultiSelectDropdownListWidget.prototype.enable_list_item = function (pill) {
    const pill_text = pill.text().trim();
    const pill_value = this.data.find(
        (item) => item.name.toLowerCase() === pill_text.toLowerCase(),
    ).value;
    const dropdown_list_body = $(
        `#${CSS.escape(this.container_id)} .dropdown-list-body`,
    ).expectOne();

    const element = dropdown_list_body.find(`li[data-value = ${pill_value}]`);
    element.removeClass("disabled-list-item");

    if (this.data_selected.includes(pill_value)) {
        const index = this.data_selected.indexOf(pill_value);
        if (index > -1) {
            this.data_selected.splice(index, 1);
        }
    }

    // Trigger the callback once any pill is removed.
    this.on_pill_remove(pill_value);
};

// Override the `register_event_handlers` function.
MultiSelectDropdownListWidget.prototype.register_event_handlers = function () {
    const dropdown_list_body = $(
        `#${CSS.escape(this.container_id)} .dropdown-list-body`,
    ).expectOne();
    const pill_container = $("#pill-container");

    dropdown_list_body.on("click keypress", ".list_item", (e) => {
        if (e.type === "keypress" && e.key !== "Enter") {
            return;
        }
        const element = $(e.target.closest("li"));
        if (element.hasClass("disabled-list-item")) {
            e.preventDefault();
            e.stopPropagation();
            return;
        }

        const element_text = element.text().trim();
        const rendered_pill = render_multiselect_pills({
            display_value: element_text,
        });
        pill_container.append(rendered_pill);
        this.disable_list_item(element, element.attr("data-value"));
        this.data_selected.push(element.attr("data-value"));

        e.stopPropagation();
    });

    // We bind the mousedown here instead of click event,
    // as we don't want the pill item to retain the focus
    // when clicked on it which causes the pill focus color to flicker.
    pill_container.on("mousedown", ".exit", (e) => {
        e.stopPropagation();
        e.preventDefault();

        const target = $(e.target);
        const pill_item = target.closest(".pill");
        if (!pill_item.length > 0) {
            return;
        }
        pill_item.remove();
        this.enable_list_item(pill_item.find(".pill-value"));
    });
};

// Returns array of values selected by user.
MultiSelectDropdownListWidget.prototype.value = function () {
    let val = this.data_selected;
    // Cases taken care of -
    // - User never pressed any dropdown item button -> We return the initial value.
    // - User passes the null value.
    if (val !== null && val.length === 0) {
        val = this.null_value;
    }
    return val;
};
