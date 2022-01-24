import $ from "jquery";

import render_admin_default_streams_list from "../templates/settings/admin_default_streams_list.hbs";

import * as channel from "./channel";
import {DropdownListWidget} from "./dropdown_list_widget";
import * as hash_util from "./hash_util";
import {$t, $t_html} from "./i18n";
import * as ListWidget from "./list_widget";
import * as loading from "./loading";
import {page_params} from "./page_params";
import * as stream_data from "./stream_data";
import * as stream_settings_data from "./stream_settings_data";
import * as sub_store from "./sub_store";
import * as ui from "./ui";
import * as ui_report from "./ui_report";

const meta = {
    loaded: false,
};

export let default_stream_widget = null;

export function init_dropdown_widgets() {
    const streams = stream_settings_data.get_streams_for_settings_page();
    const non_default_streams = streams.filter(
        (x) => !stream_data.is_default_stream_id(x.stream_id),
    );
    const streams_list = {
        data: non_default_streams.map((x) => ({
            name: x.name,
            value: x.stream_id.toString(),
        })),
        default_text: $t({defaultMessage: "None"}),
        render_text: (x) => `#${x}`,
        null_value: -1,
    };
    default_stream_widget = new DropdownListWidget({
        widget_name: "default_stream_id",
        value: page_params.default_stream_id,
        ...streams_list,
    });

    $(".default-stream-form").on("click", "#default_stream_id_widget", () => {
        const stream_name = $("#default_stream_id_widget")[0].outerText;
        if (stream_name === "None") {
            $("#do_submit_stream").prop("disabled", true);
        } else {
            $("#do_submit_stream").prop("disabled", false);
        }
    });
}

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
    init_dropdown_widgets();

    $(".default-stream-form").on("click", "#do_submit_stream", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const default_stream_input = stream_data.maybe_get_stream_name(
            Number.parseInt(default_stream_widget.value(), 10),
        );
        make_stream_default(stream_data.get_stream_id(default_stream_input));
        $("#do_submit_stream").prop("disabled", true);
        init_dropdown_widgets();
    });

    $("body").on("click", ".default_stream_row .remove-default-stream", function (e) {
        const $row = $(this).closest(".default_stream_row");
        const stream_id = Number.parseInt($row.attr("data-stream-id"), 10);
        delete_default_stream(stream_id, $row, $(e.target));
    });
}
