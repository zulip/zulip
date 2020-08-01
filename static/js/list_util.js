"use strict";

const list_selectors = ["#stream_filters", "#global_filters", "#user_presences"];

exports.inside_list = function (e) {
    const $target = $(e.target);
    const in_list = $target.closest(list_selectors.join(", ")).length > 0;
    return in_list;
};

exports.go_down = function (e) {
    const $target = $(e.target);
    $target.closest("li").next().find("a").trigger("focus");
};

exports.go_up = function (e) {
    const $target = $(e.target);
    $target.closest("li").prev().find("a").trigger("focus");
};

window.list_util = exports;
