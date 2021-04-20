import $ from "jquery";

import render_admin_playground_list from "../templates/settings/admin_playground_list.hbs";

import * as ListWidget from "./list_widget";
import {page_params} from "./page_params";
import * as ui from "./ui";

const meta = {
    loaded: false,
};

export function reset() {
    meta.loaded = false;
}

function compare_by_index(a, b, i) {
    if (a[i] > b[i]) {
        return 1;
    } else if (a[i] === b[i]) {
        return 0;
    }
    return -1;
}

function sort_pygments_language(a, b) {
    return compare_by_index(a, b, 0);
}

function sort_playground_name(a, b) {
    return compare_by_index(a, b, 1);
}

export function maybe_disable_widgets() {
    if (page_params.is_admin) {
        return;
    }
}

export function populate_playgrounds(playgrounds_data) {
    if (!meta.loaded) {
        return;
    }

    const playgrounds_table = $("#admin_playgrounds_table").expectOne();
    ListWidget.create(playgrounds_table, playgrounds_data, {
        name: "playgrounds_list",
        modifier(playground) {
            return render_admin_playground_list({
                playground: {
                    playground_name: playground.name,
                    pygments_language: playground.pygments_language,
                    url_prefix: playground.url_prefix,
                },
            });
        },
        filter: {
            element: playgrounds_table.closest(".settings-section").find(".search"),
            predicate(item, value) {
                return (
                    item.name.toLowerCase().includes(value) ||
                    item.pygments_language.toLowerCase().includes(value)
                );
            },
            onupdate() {
                ui.reset_scrollbar(playgrounds_table);
            },
        },
        parent_container: $("#playground-settings").expectOne(),
        init_sort: [sort_pygments_language],
        sort_fields: {
            pygments_language: sort_pygments_language,
            playground_name: sort_playground_name,
        },
        simplebar_container: $("#playground-settings .progressive-table-wrapper"),
    });
}

export function set_up() {
    build_page();
    maybe_disable_widgets();
}

function build_page() {
    meta.loaded = true;
    populate_playgrounds(page_params.realm_playgrounds);
}
