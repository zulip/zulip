var muting_user_ui = (function () {

var exports = {};

function timestamp_ms() {
    return (new Date()).getTime();
}

var last_update = 0;

exports.notify_mute_with_undo_option = (function () {
    var meta = {
	muted_user_id: null,
	muted_user_name: null,
        hide_me_time: null,
        alert_hover_state: false,
        $mute_user: null,
    };
    var animate = {
        fadeOut: function () {
            if (meta.$mute_user) {
                meta.$mute_user.fadeOut(500).removeClass("show");
            }
        },
        fadeIn: function () {
            if (meta.$mute_user) {
                meta.$mute_user.fadeIn(500).addClass("show");
            }
        },
    };
    setInterval(function () {
        if (meta.hide_me_time < new Date().getTime() && !meta.alert_hover_state) {
            animate.fadeOut();
        }
    }, 100);

    return function (muted_user_id, muted_user_name) {
        var $exit_mute = $("#unmute_muted_user_notification .exit-me-user");

        if (!meta.$mute_user) {
          meta.$mute_user = $("#unmute_muted_user_notification");

          $exit_mute.click(function () {
              animate.fadeOut();
          });

          meta.$mute_user.find("#unmute-user").click(function () {
              // it should reference the meta variable and not get stuck with
              // a pass-by-value of muted_user_name/id.
              exports.unmute_user([meta.muted_user_id, meta.muted_user_name]);
              animate.fadeOut();
          });
        }

        meta.muted_user_id = muted_user_id;
	meta.muted_user_name = muted_user_name;
        // add a four second delay before closing up.
        meta.hide_me_time = new Date().getTime() + 4000;

        meta.$mute_user.find(".muted-user").html(muted_user_name);

        animate.fadeIn();

        // if the user mouses over the notification, don't hide it.
        meta.$mute_user.mouseenter(function () {
            meta.alert_hover_state = true;
        });

        // once the user's mouse leaves the notification, restart the countdown.
        meta.$mute_user.mouseleave(function () {
            meta.alert_hover_state = false;
            // add at least 2000ms but if more than that exists just keep the
            // current amount.
            meta.hide_me_time = Math.max(meta.hide_me_time, new Date().getTime() + 2000);
        });
    };
}());

exports.dismiss_user_mute_confirmation = function () {
    var $mute_user = $("#unmute_muted_user_notification");
    if ($mute_user) {
        $mute_user.fadeOut(500).removeClass("show");
    }
};

exports.persist_user_mute = function (muted_user_id) {
    var data = { muted_user_profile_id: muted_user_id };
    last_update = timestamp_ms();
    channel.put({
        url: '/json/users/me/user_mute/' + muted_user_id,
        idempotent: true,
        data: data,
    });
};

exports.persist_user_unmute = function (muted_user_id) {
	var data = { muted_user_profile_id: muted_user_id };
    last_update = timestamp_ms();
    channel.del({
        url: '/json/users/me/user_mute/' + muted_user_id,
        idempotent: true,
        data: data,
    });
};

exports.handle_mute_updates = function (muted_users) { //muted_users is a list of tuples with each tuple containing muted_user_id and muted_user_name
    if (timestamp_ms() < last_update + 1000) {
        // This mute update is either the one that we just rendered, or,
        // much less likely, it's coming from another device and would probably
        // be overwriting this device's preferences with stale data.
        return;
    }

    exports.update_muted_users(muted_users);
};

exports.update_muted_users = function (muted_users) {
    muting_user.set_muted_users(muted_users);
};

exports.set_up_muted_users_ui = function (muted_user_names) {
    var muted_users_table = $("#muted_users_table tbody");
    muted_users_table.empty();
    _.each(muted_user_names, function (name) {
        var row = templates.render('muted_user_ui_row', {muted_user_name: name});
        muted_users_table.append(row);
    });
};

exports.mute_user = function (muted_user) {
    muting_user.add_muted_user(muted_user);
    exports.persist_user_mute(muted_user[0]);
    exports.notify_mute_with_undo_option(muted_user);
    exports.set_up_muted_users_ui(muting_user.get_muted_user_names());
};

exports.unmute_user = function (muted_user) {
    // we don't run a unmute_notify function because it isn't an issue as much
    // if someone accidentally unmutes a stream rather than if they mute it
    // and miss out on info.
    muting_user.remove_muted_user(muted_user);
    exports.persist_user_unmute(muted_user[0]);
    exports.set_up_muted_users_ui(muting_user.get_muted_user_names());
    exports.dismiss_user_mute_confirmation();
};

$(function () {
    exports.update_muted_users(page_params.muted_users);
});

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = muting_user_ui;
}
