var settings_panel_menu = (function () {

var exports = {};

exports.make_menu = function (opts) {
    var main_elem = opts.main_elem;
    var hash_prefix = opts.hash_prefix;
    var load_section = opts.load_section;
    var curr_li = main_elem.children('li').eq(0);

    var self = {};

    self.show = function () {
        main_elem.show();
        self.activate_section({
            li_elem: curr_li,
        });
        curr_li.focus();
    };

    self.hide = function () {
        main_elem.hide();
    };

    self.current_tab = function () {
        return curr_li.data('section');
    };

    self.set_key_handlers = function (toggler) {
        keydown_util.handle({
            elem: main_elem,
            handlers: {
                left_arrow: toggler.maybe_go_left,
                right_arrow: toggler.maybe_go_right,
                enter_key: self.enter_panel,
                up_arrow: self.prev,
                down_arrow: self.next,
            },
        });
    };

    self.prev = function () {
        curr_li.prev().focus().click();
        return true;
    };

    self.next = function () {
        curr_li.next().focus().click();
        return true;
    };

    self.enter_panel = function () {
        var panel = self.get_panel();
        var sel = 'input:visible:first,button:visible:first,select:visible:first';
        var panel_elem = panel.find(sel).first();

        panel_elem.focus();
        return true;
    };

    self.activate_section = function (opts) {
        var li_elem = opts.li_elem;
        var section = li_elem.data('section');

        curr_li = li_elem;

        main_elem.children("li").removeClass("active no-border");
        li_elem.addClass("active");
        li_elem.prev().addClass("no-border");

        var settings_section_hash = hash_prefix + section;
        hashchange.update_browser_history(settings_section_hash);

        $(".settings-section, .settings-wrapper").removeClass("show");

        ui.update_scrollbar($("#settings_content"));

        load_section(section);

        self.get_panel().addClass('show');
    };

    self.get_panel = function () {
        var section = curr_li.data('section');
        var sel = "[data-name='" + section + "']";
        var panel = $(".settings-section" + sel + ", .settings-wrapper" + sel);
        return panel;
    };

    main_elem.on("click", "li[data-section]", function (e) {
        self.activate_section({
            li_elem: $(this),
        });

        var $settings_overlay_container = $("#settings_overlay_container");
        $settings_overlay_container.find(".right").addClass("show");
        $settings_overlay_container.find(".settings-header.mobile").addClass("slide-left");

        settings.set_settings_header($(this).attr("data-section"));

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

exports.set_key_handlers = function (toggler) {
    exports.normal_settings.set_key_handlers(toggler);
    exports.org_settings.set_key_handlers(toggler);
};

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = settings_panel_menu;
}

window.settings_panel_menu = settings_panel_menu;
