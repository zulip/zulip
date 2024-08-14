import $ from "jquery";

import * as blueslip from "./blueslip";
import * as browser_history from "./browser_history";
import * as components from "./components";
import {$t, $t_html} from "./i18n";
import * as keydown_util from "./keydown_util";
import * as popovers from "./popovers";
import * as scroll_util from "./scroll_util";
import * as settings_sections from "./settings_sections";
import {redraw_active_users_list, redraw_deactivated_users_list} from "./settings_users";

export let normal_settings;
export let org_settings;

export function mobile_deactivate_section() {
    const $settings_overlay_container = $("#settings_overlay_container");
    $settings_overlay_container.find(".right").removeClass("show");
    $settings_overlay_container.find(".settings-header.mobile").removeClass("slide-left");
}

export function mobile_activate_section() {
    const $settings_overlay_container = $("#settings_overlay_container");
    $settings_overlay_container.find(".right").addClass("show");
    $settings_overlay_container.find(".settings-header.mobile").addClass("slide-left");
}

function two_column_mode() {
    return $("#settings_overlay_container").css("--single-column") === undefined;
}

function set_settings_header(key) {
    const selected_tab_key = $("#settings_page .tab-switcher .selected").data("tab-key");
    let header_prefix = $t_html({defaultMessage: "Personal settings"});
    if (selected_tab_key === "organization") {
        header_prefix = $t_html({defaultMessage: "Organization settings"});
    }
    $(".settings-header h1 .header-prefix").text(header_prefix);

    const header_text = $(
        `#settings_page .sidebar-list [data-section='${CSS.escape(key)}'] .text`,
    ).text();
    if (header_text) {
        $(".settings-header h1 .section").text(" / " + header_text);
    } else {
        blueslip.warn(
            "Error: the key '" +
                key +
                "' does not exist in the settings" +
                " sidebar list. Please add it.",
        );
    }
}

export class SettingsPanelMenu {
    constructor(opts) {
        this.$main_elem = opts.$main_elem;
        this.hash_prefix = opts.hash_prefix;
        this.$curr_li = this.$main_elem.children("li").eq(0);
        this.current_tab = this.$curr_li.data("section");
        this.current_user_settings_tab = "active";
        this.org_user_settings_toggler = components.toggle({
            html_class: "org-user-settings-switcher",
            child_wants_focus: true,
            values: [
                {label: $t({defaultMessage: "Users"}), key: "active"},
                {
                    label: $t({defaultMessage: "Deactivated"}),
                    key: "deactivated",
                },
                {label: $t({defaultMessage: "Invitations"}), key: "invitations"},
            ],
            callback: (_name, key) => {
                browser_history.update(`#organization/users/${key}`);
                this.set_user_settings_tab(key);
                $(".user-settings-section").hide();
                if (key === "active") {
                    redraw_active_users_list();
                } else if (key === "deactivated") {
                    redraw_deactivated_users_list();
                }
                $(`[data-user-settings-section="${CSS.escape(key)}"]`).show();
            },
        });

        this.$main_elem.on("click", "li[data-section]", (e) => {
            const section = $(e.currentTarget).attr("data-section");

            this.activate_section_or_default(section, this.current_user_settings_tab);
            // You generally want to add logic to activate_section,
            // not to this click handler.

            e.stopPropagation();
        });
    }

    show() {
        this.$main_elem.show();
        const section = this.current_tab;
        const user_settings_tab = this.current_user_settings_tab;

        const activate_section_for_mobile = two_column_mode();
        this.activate_section_or_default(section, user_settings_tab, activate_section_for_mobile);
        this.$curr_li.trigger("focus");
    }

    show_org_user_settings_toggler() {
        if ($("#admin-user-list").find(".tab-switcher").length === 0) {
            const toggler_html = this.org_user_settings_toggler.get();
            $("#admin-user-list .tab-container").html(toggler_html);

            // We need to re-register these handlers since they are
            // destroyed once the settings modal closes.
            this.org_user_settings_toggler.register_event_handlers();
            this.set_key_handlers(this.org_user_settings_toggler, $(".org-user-settings-switcher"));
        }
    }

    hide() {
        this.$main_elem.hide();
    }

    li_for_section(section) {
        const $li = $(`#settings_overlay_container li[data-section='${CSS.escape(section)}']`);
        return $li;
    }

    set_key_handlers(toggler, $elem = this.$main_elem) {
        const {vim_left, vim_right, vim_up, vim_down} = keydown_util;
        keydown_util.handle({
            $elem,
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

    set_current_tab(tab) {
        this.current_tab = tab;
    }

    set_user_settings_tab(tab) {
        this.current_user_settings_tab = tab;
    }

    activate_section_or_default(section, user_settings_tab, activate_section_for_mobile = true) {
        popovers.hide_all();
        if (!section) {
            // No section is given so we display the default.

            if (two_column_mode()) {
                // In two column mode we resume to the last active section.
                section = this.current_tab;
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
            section = this.current_tab;
        } else {
            this.$curr_li = $li_for_section;
        }

        this.$main_elem.children("li").removeClass("active");
        this.$curr_li.addClass("active");
        this.set_current_tab(section);

        if (section !== "users") {
            const settings_section_hash = "#" + this.hash_prefix + section;

            // It could be that the hash has already been set.
            browser_history.update_hash_internally_if_required(settings_section_hash);
        }
        if (section === "users" && this.org_user_settings_toggler !== undefined) {
            this.show_org_user_settings_toggler();
            this.org_user_settings_toggler.goto(user_settings_tab);
        }

        $(".settings-section").removeClass("show");

        settings_sections.load_settings_section(section);

        this.get_panel().addClass("show");

        scroll_util.reset_scrollbar($("#settings_content"));

        if (activate_section_for_mobile) {
            mobile_activate_section();
        }

        set_settings_header(section);
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
