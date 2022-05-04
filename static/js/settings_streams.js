import $ from "jquery";

import render_admin_default_streams_list from "../templates/settings/admin_default_streams_list.hbs";

import * as channel from "./channel";
import * as hash_util from "./hash_util";
import {$t_html} from "./i18n";
import * as ListWidget from "./list_widget";
import * as loading from "./loading";
import {page_params} from "./page_params";
import * as stream_data from "./stream_data";
import * as sub_store from "./sub_store";
import * as typeahead_helper from "./typeahead_helper";
import * as ui from "./ui";
import * as ui_report from "./ui_report";

const meta = {
    loaded: false,
};

export function reset() {
    meta.loaded = false;
}

export function maybe_disable_widgets() {
    if (page_params.is_admin) {
        return;
    }

    $(".organization-box [data-name='default-streams-list']")
        .find("input:not(.search), button, select")
        .prop("disabled", true);
}

export function build_default_stream_table() {
    const $table = $("#admin_default_streams_table").expectOne();

    const stream_ids = stream_data.get_default_stream_ids();
    const subs = stream_ids.map((stream_id) => sub_store.get(stream_id));

    ListWidget.create($table, subs, {
        name: "default_streams_list",
        modifier(item) {
            return render_admin_default_streams_list({
                stream: item,
                can_modify: page_params.is_admin,
            });
        },
        filter: {
            $element: $table.closest(".settings-section").find(".search"),
            predicate(item, query) {
                return item.name.toLowerCase().includes(query.toLowerCase());
            },
            onupdate() {
                ui.reset_scrollbar($table);
            },
        },
        $parent_container: $("#admin-default-streams-list").expectOne(),
        init_sort: ["alphabetic", "name"],
        $simplebar_container: $("#admin-default-streams-list .progressive-table-wrapper"),
    });

    loading.destroy_indicator($("#admin_page_default_streams_loading_indicator"));
}

export function update_default_streams_table() {
    if (["organization", "settings"].includes(hash_util.get_current_hash_category())) {
        $("#admin_default_streams_table").expectOne().find("tr.default_stream_row").remove();
        build_default_stream_table();
    }
}

function make_stream_default(stream_id) {
    const data = {
        stream_id,
    };
    const $default_stream_status = $("#admin-default-stream-status");
    $default_stream_status.hide();

    channel.post({
        url: "/json/default_streams",
        data,
        error(xhr) {
            ui_report.error($t_html({defaultMessage: "Failed"}), xhr, $default_stream_status);
            $default_stream_status.show();
        },
    });
}

export function delete_default_stream(stream_id, $default_stream_row, $alert_element) {
    channel.del({
        url: "/json/default_streams?" + $.param({stream_id}),
        error(xhr) {
            ui_report.generic_row_button_error(xhr, $alert_element);
        },
        success() {
            $default_stream_row.remove();
        },
    });
}

export function set_up() {
    build_page();
    maybe_disable_widgets();
}

export function build_page() {
    meta.loaded = true;

    update_default_streams_table();

    $(".create_default_stream").on("keypress", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            e.stopPropagation();
            const $default_stream_input = $(".create_default_stream");
            make_stream_default(stream_data.get_stream_id($default_stream_input.val()));
            $default_stream_input[0].value = "";
        }
    });

    $(".create_default_stream").typeahead({
        items: 5,
        fixed: true,
        source() {
            return stream_data.get_non_default_stream_names();
        },
        highlighter(item) {
            return typeahead_helper.render_typeahead_item({primary: item});
        },
    });

    $(".default-stream-form").on("click", "#do_submit_stream", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const $default_stream_input = $(".create_default_stream");
        make_stream_default(stream_data.get_stream_id($default_stream_input.val()));
        // Clear value inside input box
        $default_stream_input[0].value = "";
    });

    $("body").on("click", ".default_stream_row .remove-default-stream", function (e) {
        const $row = $(this).closest(".default_stream_row");
        const stream_id = Number.parseInt($row.attr("data-stream-id"), 10);
        delete_default_stream(stream_id, $row, $(e.target));
    });
}
