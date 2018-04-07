var settings_streams = (function () {

var exports = {};

var meta = {
    loaded: false,
};

exports.reset = function () {
    meta.loaded = false;
};

function populate_streams() {
    var streams_table = $("#admin_streams_table").expectOne();

    var items = stream_data.get_streams_for_admin();

    list_render(streams_table, items, {
        name: "admin_streams_list",
        modifier: function (item) {
            return templates.render("admin_streams_list", { stream: item });
        },
        filter: {
            element: streams_table.closest(".settings-section").find(".search"),
            callback: function (item, value) {
                return item.name.toLowerCase().indexOf(value) >= 0;
            },
            onupdate: function () {
                ui.update_scrollbar(streams_table.closest(".progressive-table-wrapper"));
            },
        },
    }).init();

    ui.set_up_scrollbar(streams_table.closest(".progressive-table-wrapper"));

    loading.destroy_indicator($('#admin_page_streams_loading_indicator'));
}

exports.build_default_stream_table = function (streams_data) {
    var self = {};

    self.row_dict = new Dict();

    var table = $("#admin_default_streams_table").expectOne();

    list_render(table, streams_data, {
        name: "default_streams_list",
        modifier: function (item) {
            var row = $(templates.render("admin_default_streams_list", { stream: item, can_modify: page_params.is_admin }));
            self.row_dict.set(item.stream_id, row);
            return row;
        },
        filter: {
            element: table.closest(".settings-section").find(".search"),
            callback: function (item, value) {
                return item.name.toLowerCase().indexOf(value) >= 0;
            },
            onupdate: function () {
                ui.update_scrollbar(table);
            },
        },
    }).init();

    ui.set_up_scrollbar(table.closest(".progressive-table-wrapper"));

    loading.destroy_indicator($('#admin_page_default_streams_loading_indicator'));

    self.remove = function (stream_id) {
        if (self.row_dict.has(stream_id)) {
            var row = self.row_dict.get(stream_id);
            row.remove();
        }
    };

    return self;
};

var default_stream_table;

exports.remove_default_stream = function (stream_id) {
    if (default_stream_table) {
        default_stream_table.remove(stream_id);
    }
};

exports.update_default_streams_table = function () {
    if (/#*organization/.test(window.location.hash) ||
        /#*settings/.test(window.location.hash)) {
        $("#admin_default_streams_table").expectOne().find("tr.default_stream_row").remove();
        default_stream_table = exports.build_default_stream_table(
            page_params.realm_default_streams);
    }
};

function make_stream_default(stream_name) {
    var data = {
        stream_name: stream_name,
    };
    var default_stream_status = $("#admin-default-stream-status");
    default_stream_status.hide();

    channel.post({
        url: '/json/default_streams',
        data: data,
        error: function (xhr) {
            if (xhr.status.toString().charAt(0) === "4") {
                ui_report.error(i18n.t("Failed"), xhr, default_stream_status);
            } else {
                ui_report.error(i18n.t("Failed"), default_stream_status);
            }
            default_stream_status.show();
        },
    });
}

exports.set_up = function () {
    meta.loaded = true;

    populate_streams();

    exports.update_default_streams_table();

    $(".admin_stream_table").on("click", ".deactivate", function (e) {
        e.preventDefault();
        e.stopPropagation();

        $(".active_stream_row").removeClass("active_stream_row");
        var row = $(e.target).closest(".stream_row");
        row.addClass("active_stream_row");

        var stream_name = row.find('.stream_name').text();
        var deactivate_stream_modal = templates.render('deactivation-stream-modal', {stream_name: stream_name});
        $("#settings_content .organization-box").append(deactivate_stream_modal);

        overlays.open_modal('deactivation_stream_modal');
    });

    $('.create_default_stream').keypress(function (e) {
        if (e.which === 13) {
            e.preventDefault();
            e.stopPropagation();
            var default_stream_input = $(".create_default_stream");
            make_stream_default(default_stream_input.val());
            default_stream_input[0].value = "";
        }
    });

    $('.create_default_stream').typeahead({
        items: 5,
        fixed: true,
        source: function () {
            return stream_data.get_non_default_stream_names();
        },
        highlighter: function (item) {
            return typeahead_helper.render_typeahead_item({ primary: item });
        },
        updater: function (stream_name) {
            make_stream_default(stream_name);
        },
    });

    $(".default-stream-form").on("click", "#do_submit_stream", function (e) {
        e.preventDefault();
        e.stopPropagation();
        var default_stream_input = $(".create_default_stream");
        make_stream_default(default_stream_input.val());
        // Clear value inside input box
        default_stream_input[0].value = "";
    });

    $("body").on("click", ".default_stream_row .remove-default-stream", function (e) {
        var row = $(this).closest(".default_stream_row");
        var stream_name = row.attr("id");

        channel.del({
            url: "/json/default_streams" + "?" + $.param({ stream_name: stream_name }),
            error: function (xhr) {
                ui_report.generic_row_button_error(xhr, $(e.target));
            },
            success: function () {
                row.remove();
            },
        });
    });

    $("#settings_content").on("hide.bs.modal", "#deactivation_stream_modal", function () {
        $("#deactivation_stream_modal").remove();
    });
};

exports.delete_stream = function (stream_id, alert_element, stream_row) {
    channel.del({
        url: '/json/streams/' + stream_id,
        error: function (xhr) {
            ui_report.error(i18n.t("Failed"), xhr, alert_element);
        },
        success: function () {
            stream_row.remove();
        },
    });
};

$(function () {
    $("#settings_overlay_container").on("click", "#do_deactivate_stream_button", function () {
        if ($("#deactivation_stream_modal .stream_name").text() !== $(".active_stream_row").find('.stream_name').text()) {
            blueslip.error("Stream deactivation canceled due to non-matching fields.");
            ui_report.message(i18n.t("Deactivation encountered an error. Please reload and try again."),
               $("#home-error"), 'alert-error');
        }
        overlays.close_modal('deactivation_stream_modal');
        $("#deactivation_stream_modal").remove();
        $(".active_stream_row button").prop("disabled", true).text(i18n.t("Working…"));
        var stream_name = $(".active_stream_row").find('.stream_name').text();
        var stream_id = stream_data.get_sub(stream_name).stream_id;
        var row = $(".active_stream_row");
        exports.delete_stream(stream_id, $("#organization-status"), row);
    });
});

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_streams;
}
