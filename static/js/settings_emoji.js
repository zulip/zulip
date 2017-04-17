var settings_emoji = (function () {

var exports = {};

var meta = {
    loaded: false,
};

exports.reset = function () {
    meta.loaded = false;
};

exports.populate_emoji = function (emoji_data) {
    if (!meta.loaded) {
        return;
    }

    var emoji_table = $('#admin_emoji_table').expectOne();
    emoji_table.find('tr.emoji_row').remove();
    _.each(emoji_data, function (data, name) {
        emoji_table.append(templates.render('admin_emoji_list', {
            emoji: {
                name: name, source_url: data.source_url,
                display_url: data.display_url,
                author: data.author,
                is_admin: page_params.is_admin,
            },
        }));
    });
    loading.destroy_indicator($('#admin_page_emoji_loading_indicator'));
};

exports.set_up = function () {
    meta.loaded = true;

    loading.make_indicator($('#admin_page_emoji_loading_indicator'));

    // Populate emoji table
    exports.populate_emoji(page_params.realm_emoji);

    $('.admin_emoji_table').on('click', '.delete', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var btn = $(this);

        channel.del({
            url: '/json/realm/emoji/' + encodeURIComponent(btn.attr('data-emoji-name')),
            error: function (xhr) {
                if (xhr.status.toString().charAt(0) === "4") {
                    btn.closest("td").html(
                        $("<p>").addClass("text-error").text(JSON.parse(xhr.responseText).msg)
                    );
                } else {
                    btn.text(i18n.t("Failed!"));
                }
            },
            success: function () {
                var row = btn.parents('tr');
                row.remove();
            },
        });
    });

    $(".organization").on("submit", "form.admin-emoji-form", function (e) {
        e.preventDefault();
        e.stopPropagation();
        var emoji_status = $('#admin-emoji-status');
        var emoji = {};
        _.each($(this).serializeArray(), function (obj) {
            emoji[obj.name] = obj.value;
        });

        channel.put({
            url: "/json/realm/emoji/" + encodeURIComponent(emoji.name),
            data: $(this).serialize(),
            success: function () {
                $('#admin-emoji-status').hide();
                ui_report.success(i18n.t("Custom emoji added!"), emoji_status);
                $("form.admin-emoji-form input[type='text']").val("");
            },
            error: function (xhr) {
                $('#admin-emoji-status').hide();
                var errors = JSON.parse(xhr.responseText).msg;
                xhr.responseText = JSON.stringify({msg: errors});
                ui_report.error(i18n.t("Failed!"), xhr, emoji_status);
            },
        });
    });
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_emoji;
}
