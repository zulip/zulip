var topic_list = (function () {

var exports = {};

function iterate_to_find(selector, name_to_find, context) {
    // This code is duplicated with stream_list.js, but we should
    // not try to de-dup this; instead, we should try to make it sane
    // for topics and avoid O(N) iteration.
    //
    // We could start by using canonical lowercase values for the
    // data-name attributes (and eventually use topic ids when the
    // back end allows).  Either that, or we should have a data
    // structure that links topic names to list items, so that we
    // don't have to search the DOM at all.
    var lowercase_name = name_to_find.toLowerCase();
    var found = _.find($(selector, context), function (elem) {
        return $(elem).attr('data-name').toLowerCase() === lowercase_name;
    });
    return found ? $(found) : $();
}

exports.remove_expanded_topics = function () {
    popovers.hide_topic_sidebar_popover();
    $("ul.expanded_subjects").remove();
};

function get_topic_filter_li(stream_li, topic) {
    return iterate_to_find(".expanded_subjects li.expanded_subject", topic, stream_li);
}

exports.activate_topic = function (stream_li, active_topic) {
    get_topic_filter_li(stream_li, active_topic).addClass('active-sub-filter');
};

exports.update_count_in_dom = function (count_span, value_span, count) {
    if (count === 0) {
        count_span.hide();
        value_span.text('');
    } else {
        count_span.removeClass("zero_count");
        count_span.show();
        value_span.text(count);
    }
};

exports.set_count = function (stream_li, topic, count) {
    var topic_li = get_topic_filter_li(stream_li, topic);
    var count_span = topic_li.find('.subject_count');
    var value_span = count_span.find('.value');

    if (count_span.length === 0 || value_span.length === 0) {
        return;
    }

    exports.update_count_in_dom(count_span, value_span, count);
};


return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = topic_list;
}
