var list_selectors = ["#group-pm-list", "#stream_filters", "#global_filters", "#user_presences"];

exports.inside_list = function (e) {
    var $target = $(e.target);
    var in_list = $target.closest(list_selectors.join(", ")).length > 0;
    return in_list;
};

exports.go_down = function (e) {
    var $target = $(e.target);
    $target.closest("li").next().find("a").focus();
};

exports.go_up = function (e) {
    var $target = $(e.target);
    $target.closest("li").prev().find("a").focus();
};

window.list_util = exports;
