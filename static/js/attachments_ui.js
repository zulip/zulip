var attachments_ui = (function () {

var exports = {};

function delete_attachments(attachment) {
    var status = $('#delete-upload-status');
    channel.del({
        url: '/json/attachments/' + attachment,
        idempotent: true,
        error: function (xhr) {
            ui_report.error(i18n.t("Failed"), xhr, status);
        },
        success: function () {
            ui_report.success(i18n.t("Attachment deleted"), status);
        },
    });
}

function bytes_to_size(bytes, kb_with_1024_bytes) {
    if (kb_with_1024_bytes === undefined) {
        kb_with_1024_bytes = false;
    }
    var kb_size = kb_with_1024_bytes ? 1024 : 1000;
    var sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    if (bytes === 0) {
        return '0 B';
    }
    var i = parseInt(Math.floor(Math.log(bytes) / Math.log(kb_size)), 10);
    var size = Math.round(bytes / Math.pow(kb_size, i));
    if ((i > 0) && (size < 10)) {
        size = Math.round((bytes / Math.pow(kb_size, i)) * 10) / 10;
    }
    return size + ' ' + sizes[i];
 }

exports.set_up_attachments = function () {
    // The settings page must be rendered before this function gets called.

    var attachments = page_params.attachments;
    _.each(attachments, function (attachment) {
        var time = new XDate(attachment.create_time);
        attachment.create_time_str = timerender.render_now(time).time_str;
        attachment.size_str = bytes_to_size(attachment.size);
    });

    var uploaded_files_table = $("#uploaded_files_table").expectOne();
    var $search_input = $("#upload_file_search");

    var list = list_render(uploaded_files_table, attachments, {
        name: "uploaded-files-list",
        modifier: function (attachment) {
            return templates.render("uploaded_files_list", { attachment: attachment });
        },
        filter: {
            element: $search_input,
            callback: function (item, value) {
                return item.name.toLocaleLowerCase().indexOf(value) >= 0;
            },
            onupdate: function () {
                ui.update_scrollbar(uploaded_files_table.closest(".progressive-table-wrapper"));
            },
        },
    }).init();

    list.add_sort_function("mentioned-in", function (a, b) {
        var a_m = a.messages[0];
        var b_m = b.messages[0];

        if (!a_m) { return 1; }
        if (!b_m) { return -1; }

        if (a_m.id > b_m.id) {
            return 1;
        } else if (a_m.id === b_m.id) {
            return 0;
        }

        return -1;
    });



    ui.set_up_scrollbar(uploaded_files_table.closest(".progressive-table-wrapper"));

    uploaded_files_table.empty();
    _.each(attachments, function (attachment) {
        var row = templates.render('uploaded_files_list', { attachment: attachment });
        uploaded_files_table.append(row);
    });

    $('#uploaded_files_table').on('click', '.remove-attachment', function (e) {
        var row = $(e.target).closest(".uploaded_file_row");
        row.remove();
        delete_attachments($(this).data('attachment'));
    });
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = attachments_ui;
}
