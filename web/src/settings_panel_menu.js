import $ from "jquery";

import * as browser_history from "./browser_history";
import * as keydown_util from "./keydown_util";
import * as popovers from "./popovers";
import * as scroll_util from "./scroll_util";
import * as settings from "./settings";
import * as settings_sections from "./settings_sections";

export let normal_settings;
export let org_settings;

export function mobile_deactivate_section() {
    const $settings_overlay_container = $("#settings_overlay_container");
    $settings_overlay_container.find(".right").removeClass("show");
    $settings_overlay_container.find(".settings-header.mobile").removeClass("slide-left");
}

function two_column_mode() {
    return $("#settings_overlay_container").css("--single-column") === undefined;
}

export class SettingsPanelMenu {
    constructor(opts) {
        this.$main_elem = opts.$main_elem;
        this.hash_prefix = opts.hash_prefix;
        this.$curr_li = this.$main_elem.children("li").eq(0);

        this.$main_elem.on("click", "li[data-section]", (e) => {
            const section = $(e.currentTarget).attr("data-section");

            this.activate_section_or_default(section);

            // You generally want to add logic to activate_section,
            // not to this click handler.

            e.stopPropagation();
        });
    }

    show() {
        this.$main_elem.show();
        const section = this.current_tab();
        if (two_column_mode()) {
            // In one column mode want to show the settings list, not the first settings section.
            this.activate_section_or_default(section);
        }
        this.$curr_li.trigger("focus");
    }

    hide() {
        this.$main_elem.hide();
    }

    current_tab() {
        return this.$curr_li.data("section");
    }

    li_for_section(section) {
        const $li = $(`#settings_overlay_container li[data-section='${CSS.escape(section)}']`);
        return $li;
    }

    set_key_handlers(toggler) {
        const {vim_left, vim_right, vim_up, vim_down} = keydown_util;
        keydown_util.handle({
            $elem: this.$main_elem,
            handlers: {
                ArrowLeft: toggler.maybe_go_left,
                ArrowRight: toggler.maybe_go_right,
                Enter: () => this.enter_panel(),
                ArrowUp: () => this.prev(),
                ArrowDown: () => this.next(),

                // Binding vim keys as well
                [vim_left]: toggler.maybe_go_left,
                [vim_right]: toggler.maybe_go_right,
                [vim_up]: () => this.prev(),
                [vim_down]: () => this.next(),
            },
        });
    }

    prev() {
        this.$curr_li.prevAll(":visible").first().trigger("focus").trigger("click");
        return true;
    }

    next() {
        this.$curr_li.nextAll(":visible").first().trigger("focus").trigger("click");
        return true;
    }

    enter_panel() {
        const $panel = this.get_panel();
        const $panel_elem = $panel.find("input:visible,button:visible,select:visible").first();

        $panel_elem.trigger("focus");
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
                mobile_deactivate_section();
                return;
            }
        }

        const $li_for_section = this.li_for_section(section);
        if ($li_for_section.length === 0) {
            // This happens when there is no such section or the user does not have
            // permission to view that section.
            section = this.current_tab();
        } else {
            this.$curr_li = $li_for_section;
        }

        this.$main_elem.children("li").removeClass("active");
        this.$curr_li.addClass("active");

        const settings_section_hash = "#" + this.hash_prefix + section;

        // It could be that the hash has already been set.
        browser_history.update_hash_internally_if_required(settings_section_hash);

        $(".settings-section").removeClass("show");

        settings_sections.load_settings_section(section);

        this.get_panel().addClass("show");

        scroll_util.reset_scrollbar($("#settings_content"));

        const $settings_overlay_container = $("#settings_overlay_container");
        $settings_overlay_container.find(".right").addClass("show");
        $settings_overlay_container.find(".settings-header.mobile").addClass("slide-left");

        settings.set_settings_header(section);
    }

    get_panel() {
        const section = this.$curr_li.data("section");
        const sel = `[data-name='${CSS.escape(section)}']`;
        const $panel = $(".settings-section" + sel);
        return $panel;
    }
}

export function initialize() {
    normal_settings = new SettingsPanelMenu({
        $main_elem: $(".normal-settings-list"),
        hash_prefix: "settings/",
    });
    org_settings = new SettingsPanelMenu({
        $main_elem: $(".org-settings-list"),
        hash_prefix: "organization/",
    });
}

export function show_normal_settings() {
    org_settings.hide();
    normal_settings.show();
}

export function show_org_settings() {
    normal_settings.hide();
    org_settings.show();
}

export function set_key_handlers(toggler) {
    normal_settings.set_key_handlers(toggler);
    org_settings.set_key_handlers(toggler);
}
