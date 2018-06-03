var settings_panel_menu = (function () {

var exports = {};

exports.make_menu = function (opts) {
    var main_elem = opts.main_elem;

    var self = {};

    self.goto_top = function () {
        main_elem.children('li').eq(0).click();
    };

    self.show = function () {
        main_elem.show();
    };

    self.hide = function () {
        main_elem.hide();
    };

    return self;
};

exports.initialize = function () {
    exports.normal_settings = exports.make_menu({
        main_elem: $('.normal-settings-list'),
    });
    exports.org_settings = exports.make_menu({
        main_elem: $('.org-settings-list'),
    });
};

exports.show_normal_settings = function () {
    exports.org_settings.hide();
    exports.normal_settings.show();
};

exports.show_org_settings = function () {
    exports.normal_settings.hide();
    exports.org_settings.show();
};

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = settings_panel_menu;
}
