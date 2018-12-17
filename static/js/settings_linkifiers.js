var settings_linkifiers = (function () {

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

    $(".organization-box [data-name='filter-settings']")
        .find("input, button, select").attr("disabled", true);
};

exports.populate_filters = function (filters_data) {
    if (!meta.loaded) {
        return;
    }

    var filters_table = $("#admin_filters_table").expectOne();
    filters_table.find("tr.filter_row").remove();
    _.each(filters_data, function (filter) {
        filters_table.append(
            templates.render(
                "admin_filter_list", {
                    filter: {
                        pattern: filter[0],
                        url_format_string: filter[1],
                        id: filter[2],
                    },
                    can_modify: page_params.is_admin,
                }
            )
        );
    });
    loading.destroy_indicator($('#admin_page_filters_loading_indicator'));
};

exports.set_up = function () {
    exports.build_page();
    exports.maybe_disable_widgets();
};

exports.build_page = function () {
    meta.loaded = true;

    // create loading indicators
    loading.make_indicator($('#admin_page_filters_loading_indicator'));

    // Populate filters table
    exports.populate_filters(page_params.realm_filters);

    $('.admin_filters_table').on('click', '.delete', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var btn = $(this);

        channel.del({
            url: '/json/realm/filters/' + encodeURIComponent(btn.attr('data-filter-id')),
            error: function (xhr) {
                ui_report.generic_row_button_error(xhr, btn);
            },
            success: function () {
                var row = btn.parents('tr');
                row.remove();
            },
        });
    });

    $(".organization form.admin-filter-form").off('submit').on('submit', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var filter_status = $('#admin-filter-status');
        var pattern_status = $('#admin-filter-pattern-status');
        var format_status = $('#admin-filter-format-status');
        var add_filter_button = $('.new-filter-form button');
        add_filter_button.attr("disabled", "disabled");
        filter_status.hide();
        pattern_status.hide();
        format_status.hide();
        var filter = {};
        _.each($(this).serializeArray(), function (obj) {
            filter[obj.name] = obj.value;
        });

        channel.post({
            url: "/json/realm/filters",
            data: $(this).serialize(),
            success: function (data) {
                $('#filter_pattern').val('');
                $('#filter_format_string').val('');
                add_filter_button.removeAttr("disabled");
                filter.id = data.id;
                ui_report.success(i18n.t("Custom filter added!"), filter_status);
            },
            error: function (xhr) {
                var errors = JSON.parse(xhr.responseText).errors;
                add_filter_button.removeAttr("disabled");
                if (errors.pattern !== undefined) {
                    xhr.responseText = JSON.stringify({msg: errors.pattern});
                    ui_report.error(i18n.t("Failed"), xhr, pattern_status);
                }
                if (errors.url_format_string !== undefined) {
                    xhr.responseText = JSON.stringify({msg: errors.url_format_string});
                    ui_report.error(i18n.t("Failed"), xhr, format_status);
                }
                if (errors.__all__ !== undefined) {
                    xhr.responseText = JSON.stringify({msg: errors.__all__});
                    ui_report.error(i18n.t("Failed"), xhr, filter_status);
                }
            },
        });
    });
    function open_linkifier_info_form_modal(filter){
      var html = templates.render('linkifier-info-form-modal',{
        pattern: filter[0],
        url_format_string: filter[1],
        filter_id: filter[2],
      });
      var linkifier_info_form_modal = $(html);
      var modal_container = $('#user-info-form-modal-container');
      modal_container.empty().append(linkifier_info_form_modal);
      overlays.open_modal('linkifier-info-form-modal');

      return linkifier_info_form_modal;
    }

    $(".admin_filters_table").on("click",".open-linkifier-form",function(e){
      var filter_id = $(e.currentTarget).attr("data-filter-id");
      var filter_pattern = $(e.currentTarget).attr("data-pattern");
      var filter_url_format_string = $(e.currentTarget).attr("data-url-format-string");
      var linkifier_info_form_modal = open_linkifier_info_form_modal([filter_pattern,filter_url_format_string,filter_id]);

      linkifier_info_form_modal.find(".submit_linkifier_info_change").on("click", function (e){
        e.preventDefault();
        e.stopPropagation();
        var new_pattern = $('#filter_pattern').val();
        var new_url_format_string = $('#filter_url_format_string').val();

        channel.patch({
          url: "/json/realm/filters/update/"+ encodeURIComponent(filter_id),
          data: {
            pattern: JSON.stringify(new_pattern),
            url_format_string: JSON.stringify(new_url_format_string)
          },
        });



      });

    });


};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_linkifiers;
}
window.settings_linkifiers = settings_linkifiers;
