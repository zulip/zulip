var attachments_ui = (function () {

var exports = {};

function delete_attachments(attachment) {
    channel.del({url: '/json/attachments/' + attachment, idempotent: true});
}

exports.bytes_to_size = function (bytes) {
    var sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    if (bytes === 0) {
        return '0 B';
    }
    var i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)), 10);
    return Math.round(bytes / Math.pow(1024, i), 2) + ' ' + sizes[i];
 };

exports.set_up_attachments = function () {
    // The settings page must be rendered before this function gets called.

    var attachments = page_params.attachments;
    _.each(attachments, function (attachment) {
        attachment.create_time = timerender.absolute_time(attachment.create_time);
        attachment.size = exports.bytes_to_size(attachment.size);
    });

    var uploaded_files_table = $("#uploaded_files_table").expectOne();

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
