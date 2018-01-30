var settings_muting_user = (function () {

var exports = {};

exports.set_up_mute = function () {
    $('body').on('click', '.settings-unmute-user', function (e) {
        var $row = $(this).closest("tr");
        var muted_name = $row.data("muted-user");
	var muted_names	= muting_user.get_muted_user_names();
	var pos = $.inArray(muted_name, muted_names);
	var muted_ids = muting_user.get_muted_user_ids();
	var muted_id = muted_ids[pos];
        muting_user_ui.unmute_user([muted_id, muted_name]);
        $row.remove();
        e.stopImmediatePropagation();
    });

    muting_user_ui.set_up_muted_users_ui(muting_user.get_muted_user_names());
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_muting_user;
}
