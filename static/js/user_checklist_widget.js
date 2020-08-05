"use strict";

const render_stream_user_checkbox = require("../templates/stream_user_checkbox.hbs");

class UserChecklistWidget {
    constructor(users, container_id) {
        this.users = users.map((u) => {
            u.checked = false;
            return u;
        });
        const container = $(`#${container_id}`);
        const search_input = $(`.add-user-list-filter`);
        const user_ids = this.users.map((e) => e.user_id);
        const class_this = this;
        this.widget = list_render.create(container, user_ids, {
            name: `new_stream_users_list`,
            modifier(item) {
                return render_stream_user_checkbox({
                    user: item,
                    is_admin: page_params.is_admin,
                });
            },
            html_selector: (item) => `label[data-user-id='${item}']`,
            get_item(id) {
                return class_this.get_user(id);
            },
            filter: {
                element: search_input,
                predicate(item, value) {
                    return item.full_name.toLowerCase().includes(value);
                },
            },
            simplebar_container: $(`#${container_id}-wrapper`),
        });
    }

    get_user(id) {
        return this.users.find((e) => e.user_id === id);
    }

    check_user(id, state = true) {
        const index = this.users.findIndex((e) => e.user_id === id);
        this.users[index].checked = state;
        this.widget.render_item(id);
    }

    check_all(state = true) {
        this.users = this.users.map((e) => {
            e.checked = state;
            return e;
        });
        this.widget.hard_redraw();
    }

    get_checked() {
        return this.users.filter((e) => e.checked);
    }
}

module.exports = UserChecklistWidget;
