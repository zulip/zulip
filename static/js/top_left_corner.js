var top_left_corner = (function () {

var exports = {};

exports.update_count_in_dom = function (unread_count_elem, count) {
    var count_span = unread_count_elem.find('.count');
    var value_span = count_span.find('.value');

    if (count === 0) {
        count_span.hide();
        value_span.text('');
        return;
    }

    count_span.show();
    value_span.text(count);
};

exports.update_starred_count = function (count) {
    var starred_li = $('.top_left_starred_messages');
    exports.update_count_in_dom(starred_li, count);
};

exports.update_dom_with_unread_counts = function (counts) {
    // Note that "Private messages" counts are handled in pm_list.js.

    // mentioned/home have simple integer counts
    var mentioned_li = $('.top_left_mentions');
    var home_li = $('.top_left_all_messages');

    exports.update_count_in_dom(mentioned_li, counts.mentioned_message_count);
    exports.update_count_in_dom(home_li, counts.home_unread_messages);

    unread_ui.animate_mention_changes(mentioned_li,
                                      counts.mentioned_message_count);
};

function deselect_top_left_corner_items() {
    function remove(elem) {
        elem.removeClass('active-filter active-sub-filter');
    }

    remove($('.top_left_all_messages'));
    remove($('.top_left_private_messages'));
    remove($('.top_left_starred_messages'));
    remove($('.top_left_mentions'));
}

exports.handle_narrow_activated = function (filter) {
    deselect_top_left_corner_items();

    var ops;
    var filter_name;
    var filter_li;

    // TODO: handle confused filters like "in:all stream:foo"
    ops = filter.operands('in');
    if (ops.length >= 1) {
        filter_name = ops[0];
        if (filter_name === 'home') {
            filter_li = $('.top_left_all_messages');
            filter_li.addClass('active-filter');
        }
    }
    ops = filter.operands('is');
    if (ops.length >= 1) {
        filter_name = ops[0];
        if (filter_name === 'starred') {
            filter_li = $('.top_left_starred_messages');
            filter_li.addClass('active-filter');
        } else if (filter_name === 'mentioned') {
            filter_li = $('.top_left_mentions');
            filter_li.addClass('active-filter');
        }
    }

    if (exports.should_expand_pm_list(filter)) {
        var op_pm = filter.operands('pm-with');
        pm_list.expand(op_pm);
    } else {
        pm_list.close();
    }
};

exports.should_expand_pm_list = function (filter) {
    var op_is = filter.operands('is');

    if (op_is.length >= 1 && _.contains(op_is, "private")) {
        return true;
    }

    var op_pm = filter.operands('pm-with');

    if (op_pm.length !== 1) {
        return false;
    }

    var emails_strings = op_pm[0];
    var emails = emails_strings.split(',');

    var has_valid_emails = people.is_valid_bulk_emails_for_compose(emails);

    return has_valid_emails;
};

exports.handle_narrow_deactivated = function () {
    deselect_top_left_corner_items();
    pm_list.close();

    var filter_li = $('.top_left_all_messages');
    filter_li.addClass('active-filter');
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = top_left_corner;
}
window.top_left_corner = top_left_corner;
