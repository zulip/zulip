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

<<<<<<< 23062f5bf64cfbd7e9b78d72d465926b303b534f
exports.bytes_to_size = function (bytes, kb_with_1024_bytes) {
    if (kb_with_1024_bytes === undefined) {
        kb_with_1024_bytes = false;
    }
=======
exports.bytes_to_size = function (bytes, kb_with_1024_bytes=false) {
>>>>>>> user settings: fix uploaded files UI
    var kb_size = kb_with_1024_bytes ? 1024 : 1000;
    var sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    if (bytes === 0) {
        return '0 B';
    }
<<<<<<< 23062f5bf64cfbd7e9b78d72d465926b303b534f
<<<<<<< 0d9d10853a726e617244793cc00969d220e16b26
    var i = parseInt(Math.floor(Math.log(bytes) / Math.log(kb_size)), 10);
    var size = Math.round(bytes / Math.pow(kb_size, i));
    if ((i > 0) && (size < 10)) {
        size = Math.round((bytes / Math.pow(kb_size, i)) * 10) / 10;
=======
    var i = parseInt(Math.floor(Math.log(bytes) / Math.log(1000)), 10);
    var size = Math.round(bytes / Math.pow(1000, i), 2);
    if ((i > 0) && (size < 10)) {
        size = '0' + size;
>>>>>>> user settings: Change file size display format
=======
    var i = parseInt(Math.floor(Math.log(bytes) / Math.log(kb_size)), 10);
    var size = Math.round(bytes / Math.pow(kb_size, i));
    if ((i > 0) && (size < 10)) {
        size = Math.round((bytes / Math.pow(kb_size, i)) * 10) / 10;
>>>>>>> user settings: fix uploaded files UI
    }
    return size + ' ' + sizes[i];
 };

exports.set_up_attachments = function () {
    // The settings page must be rendered before this function gets called.

    var attachments = page_params.attachments;
    _.each(attachments, function (attachment) {
<<<<<<< 23062f5bf64cfbd7e9b78d72d465926b303b534f
<<<<<<< ee4fc0ed44726ab233a08d1393614f0f70e6367f
        var time = new XDate(attachment.create_time);
        attachment.create_time_str = timerender.render_now(time).time_str;
=======

        attachment.create_time_str = timerender.relative_date(attachment.create_time);
>>>>>>> user settings: change 'Date uploaded' display format
=======
        var time = new XDate(attachment.create_time);
        attachment.create_time_str = timerender.render_now(time).time_str;
>>>>>>> user settings: fix uploaded files UI
        attachment.size_str = exports.bytes_to_size(attachment.size);
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
