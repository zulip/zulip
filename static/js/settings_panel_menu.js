var settings_panel_menu = (function () {

var exports = {};

exports.make_menu = function (opts) {
    var main_elem = opts.main_elem;
    var hash_prefix = opts.hash_prefix;
    var load_section = opts.load_section;

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

    self.activate_section = function (opts) {
        var li_elem = opts.li_elem;
        var section = li_elem.data('section');

        main_elem.children("li").removeClass("active no-border");
        li_elem.addClass("active");
        li_elem.prev().addClass("no-border");
        window.location.hash = hash_prefix + section;

        $(".settings-section, .settings-wrapper").removeClass("show");

        ui.update_scrollbar($("#settings_content"));

        load_section(section);

        var sel = "[data-name='" + section + "']";
        $(".settings-section" + sel + ", .settings-wrapper" + sel).addClass("show");
    };

    main_elem.on("click", "li[data-section]", function (e) {
        self.activate_section({
            li_elem: $(this),
        });

        e.stopPropagation();
    });

    return self;
};

exports.initialize = function () {
    exports.normal_settings = exports.make_menu({
        main_elem: $('.normal-settings-list'),
        hash_prefix: "settings/",
        load_section: function (section) {
            settings_sections.load_settings_section(section);
        },
    });
    exports.org_settings = exports.make_menu({
        main_elem: $('.org-settings-list'),
        hash_prefix: "organization/",
        load_section: function (section) {
            admin_sections.load_admin_section(section);
        },
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
