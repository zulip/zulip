var attachments_ui = (function () {

var exports = {};

function delete_attachments(attachment) {
    channel.del({url: '/json/attachments/' + attachment, idempotent: true});
}

exports.set_up_attachments = function () {
    // The settings page must be rendered before this function gets called.

    var attachment_list_html = "";
    _.each(page_params.attachments, function (attachment) {
        _.each(attachment.messages, function (o) {
            o.name = timerender.absolute_time(o.name);
        });

        var attachment_name_splitted = attachment.path_id.split(/\./);

        if (attachment_name_splitted.length === 1) {
            attachment.extension = "";
        } else {
            attachment.extension = attachment_name_splitted.pop();
        }

        attachment.large_ext_name = attachment.extension.length > 5;

        var li = templates.render('attachment-item', {attachment: attachment});
        attachment_list_html = attachment_list_html.concat(li);
    });

    $('#attachments_list').html(attachment_list_html);

    $('#attachments_list').on('click', '.remove-attachment', function (event) {
        var li = $(event.currentTarget).parents('li');
        li.remove();
        delete_attachments($(this).data('attachment'));
    });
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = attachments_ui;
}
