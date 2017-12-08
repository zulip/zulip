var shortcut_notification = (function () {

var exports = {};

exports.notify = function (hotkey) {
    var old_key = hotkey;
    var new_key = exports.get_new_key(old_key);
    exports.display_message(old_key, new_key);
};

exports.get_new_key = function (old_key) {
    var deprecated_keys = {
        C: 'x'
    };
    return deprecated_keys[old_key];
};

exports.display_message = (function () {
    var meta = {
        old_key: null,
        new_key: null,
        hide_me_time: null,
        alert_hover_state: false,
        $mute: null,
    };
    var animate = {
        fadeOut: function () {
            if (meta.$mute) {
                meta.$mute.fadeOut(500).removeClass("show");
            }
        },
        fadeIn: function () {
            if (meta.$mute) {
                meta.$mute.fadeIn(500).addClass("show");
            }
        },
    };
    setInterval(function () {
        if (meta.hide_me_time < new Date().getTime() && !meta.alert_hover_state) {
            animate.fadeOut();
        }
    }, 100);

    return function (old_key, new_key) {
        var $exit = $("#deprecated_shortcut_notification .exit-me");

        if (!meta.$mute) {
            meta.$mute = $("#deprecated_shortcut_notification");

            $exit.click(function () {
                animate.fadeOut();
            });
        }

        meta.old_key = old_key;
        meta.new_key = new_key;

        meta.hide_me_time = new Date().getTime() + 4000;

        meta.$mute.find(".old_key").html(old_key);
        meta.$mute.find(".new_key").html(new_key);

        animate.fadeIn();

        meta.$mute.mouseenter(function () {
            meta.alert_hover_state = true;
        });

        meta.$mute.mouseleave(function () {
            meta.alert_hover_state = false;
            meta.hide_me_time = Math.max(meta.hide_me_time, new Date().getTime() + 2000);
        });
    };
}());

}());
if (typeof module !== 'undefined') {
    module.exports = shortcut_notification;
}
