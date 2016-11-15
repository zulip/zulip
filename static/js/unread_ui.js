var unread_ui = (function () {

var exports = {};

var last_private_message_count = 0;
var last_mention_count = 0;

function do_new_messages_animation(li) {
    li.addClass("new_messages");
    function mid_animation() {
        li.removeClass("new_messages");
        li.addClass("new_messages_fadeout");
    }
    function end_animation() {
        li.removeClass("new_messages_fadeout");
    }
    setTimeout(mid_animation, 3000);
    setTimeout(end_animation, 6000);
}

exports.animate_private_message_changes = function (li, new_private_message_count) {
    if (new_private_message_count > last_private_message_count) {
        do_new_messages_animation(li);
    }
    last_private_message_count = new_private_message_count;
};

exports.animate_mention_changes = function (li, new_mention_count) {
    if (new_mention_count > last_mention_count) {
        do_new_messages_animation(li);
    }
    last_mention_count = new_mention_count;
};

exports.set_count_toggle_button = function (elem, count) {
    if (count === 0) {
        if (elem.is(':animated')) {
            return elem.stop(true, true).hide();
        }
        return elem.hide(500);
    } else if ((count > 0) && (count < 1000)) {
        elem.show(500);
        return elem.text(count);
    } else {
        elem.show(500);
        return elem.text("1k+");
    }
};


return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = unread_ui;
}
