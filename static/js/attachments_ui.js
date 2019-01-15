var attachments_ui = (function () {

var exports = {};

var attachments;

exports.bytes_to_size = function (bytes, kb_with_1024_bytes) {
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
    if (i > 0 && size < 10) {
        size = Math.round(bytes / Math.pow(kb_size, i) * 10) / 10;
    }
    return size + ' ' + sizes[i];
};

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

function render_attachments_ui() {
    var uploaded_files_table = $("#uploaded_files_table").expectOne();
    var $search_input = $("#upload_file_search");

    var list = list_render.create(uploaded_files_table, attachments, {
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
                ui.reset_scrollbar(uploaded_files_table.closest(".progressive-table-wrapper"));
            },
        },
        parent_container: $('#attachments-settings').expectOne(),
    }).init();

    list.sort('numeric', 'create_time');

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

    ui.reset_scrollbar(uploaded_files_table.closest(".progressive-table-wrapper"));
}

function format_attachment_data(new_attachments) {
    _.each(new_attachments, function (attachment) {
        var time = new XDate(attachment.create_time);
        attachment.create_time_str = timerender.render_now(time).time_str;
        attachment.size_str = exports.bytes_to_size(attachment.size);
    });
}

exports.update_attachments = function (event) {
    if (attachments === undefined) {
        // If we haven't fetched attachment data yet, there's nothing to do.
        return;
    }
    if (event.op === 'remove' || event.op === 'update') {
        attachments = attachments.filter(function (a) {
            return a.id !== event.attachment.id;
        });
    }
    if (event.op === 'add' || event.op === 'update') {
        format_attachment_data([event.attachment]);
        attachments.push(event.attachment);
    }

    // TODO: This is inefficient and we should be able to do some sort
    // of incremental list_render update instead.
    render_attachments_ui();
};

exports.set_up_attachments = function () {
    // The settings page must be rendered before this function gets called.

    var uploaded_files_table = $("#uploaded_files_table").expectOne();
    var status = $('#delete-upload-status');
    loading.make_indicator($('#attachments_loading_indicator'), {text: 'Loading...'});

    ui.set_up_scrollbar(uploaded_files_table.closest(".progressive-table-wrapper"));

    $('#uploaded_files_table').on('click', '.remove-attachment', function (e) {
        delete_attachments($(e.target).closest(".uploaded_file_row").attr('data-attachment-id'));
    });

    channel.get({
        url: "/json/attachments",
        idempotent: true,
        success: function (data) {
            loading.destroy_indicator($('#attachments_loading_indicator'));
            format_attachment_data(data.attachments);
            attachments = data.attachments;
            render_attachments_ui();
        },
        error: function (xhr) {
            loading.destroy_indicator($('#attachments_loading_indicator'));
            ui_report.error(i18n.t("Failed"), xhr, status);
        },
    });
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = attachments_ui;
}
window.attachments_ui = attachments_ui;
