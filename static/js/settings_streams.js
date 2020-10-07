"use strict";

const render_admin_default_streams_list = require("../templates/admin_default_streams_list.hbs");

const meta = {
    loaded: false,
};

exports.reset = function () {
    meta.loaded = false;
};

exports.maybe_disable_widgets = function () {
    if (page_params.is_admin) {
        return;
    }

    $(".organization-box [data-name='default-streams-list']")
        .find("input:not(.search), button, select")
        .prop("disabled", true);
};

exports.build_default_stream_table = function () {
    const table = $("#admin_default_streams_table").expectOne();

    const stream_ids = stream_data.get_default_stream_ids();
    const subs = stream_ids.map(stream_data.get_sub_by_id);

    list_render.create(table, subs, {
        name: "default_streams_list",
        modifier(item) {
            return render_admin_default_streams_list({
                stream: item,
                can_modify: page_params.is_admin,
            });
        },
        filter: {
            element: table.closest(".settings-section").find(".search"),
            predicate(item, query) {
                return item.name.toLowerCase().includes(query.toLowerCase());
            },
            onupdate() {
                ui.reset_scrollbar(table);
            },
        },
        parent_container: $("#admin-default-streams-list").expectOne(),
        init_sort: ["alphabetic", "name"],
        simplebar_container: $("#admin-default-streams-list .progressive-table-wrapper"),
    });

    loading.destroy_indicator($("#admin_page_default_streams_loading_indicator"));
};

exports.update_default_streams_table = function () {
    if (/#*organization/.test(window.location.hash) || /#*settings/.test(window.location.hash)) {
        $("#admin_default_streams_table").expectOne().find("tr.default_stream_row").remove();
        exports.build_default_stream_table();
    }
};

function make_stream_default(stream_id) {
    const data = {
        stream_id,
    };
    const default_stream_status = $("#admin-default-stream-status");
    default_stream_status.hide();

    channel.post({
        url: "/json/default_streams",
        data,
        error(xhr) {
            if (xhr.status.toString().charAt(0) === "4") {
                ui_report.error(i18n.t("Failed"), xhr, default_stream_status);
            } else {
                ui_report.error(i18n.t("Failed"), default_stream_status);
            }
            default_stream_status.show();
        },
    });
}

exports.delete_default_stream = function (stream_id, default_stream_row, alert_element) {
    channel.del({
        url: "/json/default_streams?" + $.param({stream_id}),
        error(xhr) {
            ui_report.generic_row_button_error(xhr, alert_element);
        },
        success() {
            default_stream_row.remove();
        },
    });
};

exports.set_up = function () {
    exports.build_page();
    exports.maybe_disable_widgets();
};

exports.build_page = function () {
    meta.loaded = true;

    exports.update_default_streams_table();

    $(".create_default_stream").on("keypress", (e) => {
        if (e.which === 13) {
            e.preventDefault();
            e.stopPropagation();
            const default_stream_input = $(".create_default_stream");
            make_stream_default(stream_data.get_stream_id(default_stream_input.val()));
            default_stream_input[0].value = "";
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
        const default_stream_input = $(".create_default_stream");
        make_stream_default(stream_data.get_stream_id(default_stream_input.val()));
        // Clear value inside input box
        default_stream_input[0].value = "";
    });

    $("body").on("click", ".default_stream_row .remove-default-stream", function (e) {
        const row = $(this).closest(".default_stream_row");
        const stream_id = Number.parseInt(row.attr("data-stream-id"), 10);
        exports.delete_default_stream(stream_id, row, $(e.target));
    });
};

window.settings_streams = exports;
