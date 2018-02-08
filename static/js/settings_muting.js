var settings_muting = (function () {

var exports = {};

exports.set_up = function () {
    $('body').on('click', '.settings-unmute-topic', function (e) {
        var $row = $(this).closest("tr");
        var stream = $row.data("stream");
        var topic = $row.data("topic");

        muting_ui.unmute(stream, topic);
        $row.remove();
        e.stopImmediatePropagation();
    });

    $('body').on('click', '.settings-unmute-user', function (e) {
        var $row = $(this).closest("tr");
        var muted_name = $row.data("muted-user");
        var muted_names = muting_user.get_muted_user_names();
        var pos = $.inArray(muted_name, muted_names);
        var muted_ids = muting_user.get_muted_user_ids();
        var muted_id = muted_ids[pos];
        $row.remove();
        muting_user_ui.unmute_user([muted_id, muted_name]);
        e.stopImmediatePropagation();
    });

    muting_user_ui.set_up_muted_users_ui(muting_user.get_muted_user_names());

    muting_ui.set_up_muted_topics_ui(muting.get_muted_topics());
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_muting;
}
