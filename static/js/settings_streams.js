var settings_streams = (function () {

var exports = {};

var meta = {
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
        .find("input:not(.search), button, select").attr("disabled", true);
};

exports.build_default_stream_table = function (streams_data) {
    var self = {};

    self.row_dict = new Dict();

    var table = $("#admin_default_streams_table").expectOne();

    list_render.create(table, streams_data, {
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
                ui.reset_scrollbar(table);
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

exports.delete_default_stream = function (stream_name, default_stream_row, alert_element) {
    channel.del({
        url: "/json/default_streams" + "?" + $.param({ stream_name: stream_name }),
        error: function (xhr) {
            ui_report.generic_row_button_error(xhr, alert_element);
        },
        success: function () {
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
        exports.delete_default_stream(stream_name, row, $(e.target));
    });
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_streams;
}
window.settings_streams = settings_streams;
