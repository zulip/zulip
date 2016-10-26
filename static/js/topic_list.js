var topic_list = (function () {

var exports = {};

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

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = topic_list;
}
