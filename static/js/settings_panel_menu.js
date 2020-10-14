"use strict";

exports.mobile_deactivate_section = function () {
    const $settings_overlay_container = $("#settings_overlay_container");
    $settings_overlay_container.find(".right").removeClass("show");
    $settings_overlay_container.find(".settings-header.mobile").removeClass("slide-left");
};

function two_column_mode() {
    return $("#settings_overlay_container").css("--single-column") === undefined;
}

class SettingsPanelMenu {
    constructor(opts) {
        this.main_elem = opts.main_elem;
        this.hash_prefix = opts.hash_prefix;
        this.curr_li = this.main_elem.children("li").eq(0);

        this.main_elem.on("click", "li[data-section]", (e) => {
            const section = $(e.currentTarget).attr("data-section");

            this.activate_section_or_default(section);

            // You generally want to add logic to activate_section,
            // not to this click handler.

            e.stopPropagation();
        });
    }

    show() {
        this.main_elem.show();
        const section = this.current_tab();
        if (two_column_mode()) {
            // In one column mode want to show the settings list, not the first settings section.
            this.activate_section_or_default(section);
        }
        this.curr_li.trigger("focus");
    }

    hide() {
        this.main_elem.hide();
    }

    current_tab() {
        return this.curr_li.data("section");
    }

    li_for_section(section) {
        const li = $("#settings_overlay_container li[data-section='" + section + "']");
        return li;
    }

    set_key_handlers(toggler) {
        keydown_util.handle({
            elem: this.main_elem,
            handlers: {
                left_arrow: toggler.maybe_go_left,
                right_arrow: toggler.maybe_go_right,
                enter_key: () => this.enter_panel(),
                up_arrow: () => this.prev(),
                down_arrow: () => this.next(),
            },
        });
    }

    prev() {
        this.curr_li.prevAll(":visible:first").trigger("focus").trigger("click");
        return true;
    }

    next() {
        this.curr_li.nextAll(":visible:first").trigger("focus").trigger("click");
        return true;
    }

    enter_panel() {
        const panel = this.get_panel();
        const sel = "input:visible,button:visible,select:visible";
        const panel_elem = panel.find(sel).first();

        panel_elem.trigger("focus");
        return true;
    }

    activate_section_or_default(section) {
        popovers.hide_all();
        if (!section) {
            // No section is given so we display the default.

            if (two_column_mode()) {
                // In two column mode we resume to the last active section.
                section = this.current_tab();
            } else {
                // In single column mode we close the active section
                // so that you always start at the settings list.
                exports.mobile_deactivate_section();
                return;
            }
        }

        this.curr_li = this.li_for_section(section);

        this.main_elem.children("li").removeClass("active");
        this.curr_li.addClass("active");

        const settings_section_hash = "#" + this.hash_prefix + section;
        hashchange.update_browser_history(settings_section_hash);

        $(".settings-section").removeClass("show");

        settings_sections.load_settings_section(section);

        this.get_panel().addClass("show");

        ui.reset_scrollbar($("#settings_content"));

        const $settings_overlay_container = $("#settings_overlay_container");
        $settings_overlay_container.find(".right").addClass("show");
        $settings_overlay_container.find(".settings-header.mobile").addClass("slide-left");

        settings.set_settings_header(section);
    }

    get_panel() {
        const section = this.curr_li.data("section");
        const sel = "[data-name='" + section + "']";
        const panel = $(".settings-section" + sel);
        return panel;
    }
}
exports.SettingsPanelMenu = SettingsPanelMenu;

exports.initialize = function () {
    exports.normal_settings = new SettingsPanelMenu({
        main_elem: $(".normal-settings-list"),
        hash_prefix: "settings/",
    });
    exports.org_settings = new SettingsPanelMenu({
        main_elem: $(".org-settings-list"),
        hash_prefix: "organization/",
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

window.settings_panel_menu = exports;
