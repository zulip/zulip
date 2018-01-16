var top_left_corner = (function () {

var exports = {};

exports.get_global_filter_li = function (filter_name) {
    var selector = "#global_filters li[data-name='" + filter_name + "']";
    return $(selector);
};

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


exports.update_dom_with_unread_counts = function (counts) {
    // Note that "Private messages" counts are handled in pm_list.js.

    // mentioned/home have simple integer counts
    var mentioned_li = exports.get_global_filter_li('mentioned');
    var home_li = exports.get_global_filter_li('home');

    exports.update_count_in_dom(mentioned_li, counts.mentioned_message_count);
    exports.update_count_in_dom(home_li, counts.home_unread_messages);

    unread_ui.animate_mention_changes(mentioned_li,
                                      counts.mentioned_message_count);
};

function deselect_top_left_corner_items() {
    function remove(name) {
        var li = exports.get_global_filter_li(name);
        li.removeClass('active-filter active-sub-filter');
    }

    remove('home');
    remove('private');
    remove('starred');
    remove('mentioned');
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
            filter_li = exports.get_global_filter_li(filter_name);
            filter_li.addClass('active-filter');
        }
    }
    ops = filter.operands('is');
    if (ops.length >= 1) {
        filter_name = ops[0];
        if ((filter_name === 'starred') || (filter_name === 'mentioned')) {
            filter_li = exports.get_global_filter_li(filter_name);
            filter_li.addClass('active-filter');
        }
    }

    var op_is = filter.operands('is');
    var op_pm = filter.operands('pm-with');
    if (((op_is.length >= 1) && _.contains(op_is, "private")) || op_pm.length >= 1) {
        pm_list.expand(op_pm);
    } else {
        pm_list.close();
    }
};

exports.handle_narrow_deactivated = function () {
    deselect_top_left_corner_items();
    pm_list.close();

    var filter_li = exports.get_global_filter_li('home');
    filter_li.addClass('active-filter');
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = top_left_corner;
}
