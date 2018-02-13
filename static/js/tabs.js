var tabs = (function () {

// Implement tabs for multitasking in narrows.

var exports = {};

var all_tabs = [{
        name: "Default",
        operators: [],
        locked: false,
    }];
var current_tab_index = 0;

exports.set_current_operators = function (operators) {
    all_tabs[current_tab_index].operators = operators;
};

exports.activate = function (index) {
    if (!all_tabs[index]) {
        return false;
    }
    current_tab_index = index;
    narrow.activate(all_tabs[index].operators);
    return true;
};

exports.next = function () {
    if (all_tabs.length<2) {
        return false;
    }
    var index = current_tab_index + 1;
    if (index === all_tabs.length) {
        index = 0;
    }
    return exports.activate(index);
};

exports.previous = function () {
    if (all_tabs.length<2) {
        return false;
    }
    var index = current_tab_index - 1;
    if (index === -1) {
        index = all_tabs.length - 1;
    }
    return exports.activate(index);
};

exports.new = function (from_index) {
    from_index = from_index || current_tab_index;
    var new_tab = Object.assign({}, all_tabs[from_index]);
    all_tabs.splice(from_index + 1, 0, new_tab);
    current_tab_index = from_index + 1;
};

exports.close = function (index) {
    index = index || current_tab_index;
    if (!all_tabs[index] || all_tabs.length === 1) {
        return false;
    }
    if (all_tabs[current_tab_index-1]) {
        current_tab_index--;
    } else {
        current_tab_index = 0;
    }
    return all_tabs.splice(index, 1);
};

exports.get = function () {
    return all_tabs;
};

exports._print = function () {
    blueslip.debug("All Tabs", all_tabs);
    blueslip.debug("Current Tab", all_tabs[current_tab_index]);
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = tabs;
}
