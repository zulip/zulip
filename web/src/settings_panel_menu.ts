import $ from "jquery";
import assert from "minimalistic-assert";

import * as blueslip from "./blueslip.ts";
import * as browser_history from "./browser_history.ts";
import * as components from "./components.ts";
import type {Toggle} from "./components.ts";
import {$t, $t_html} from "./i18n.ts";
import * as keydown_util from "./keydown_util.ts";
import * as popovers from "./popovers.ts";
import * as scroll_util from "./scroll_util.ts";
import {redraw_all_bots_list, redraw_your_bots_list} from "./settings_bots.ts";
import {resize_textareas_in_section} from "./settings_components.ts";
import * as settings_sections from "./settings_sections.ts";
import {redraw_active_users_list, redraw_deactivated_users_list} from "./settings_users.ts";
import * as util from "./util.ts";

export let normal_settings: SettingsPanelMenu;
export let org_settings: SettingsPanelMenu;

export function mobile_deactivate_section(): void {
    const $settings_overlay_container = $("#settings_overlay_container");
    $settings_overlay_container.find(".right").removeClass("show");
    $settings_overlay_container.find(".settings-header.mobile").removeClass("slide-left");
}

export function mobile_activate_section(): void {
    const $settings_overlay_container = $("#settings_overlay_container");
    $settings_overlay_container.find(".right").addClass("show");
    $settings_overlay_container.find(".settings-header.mobile").addClass("slide-left");
}

function two_column_mode(): boolean {
    return Number.parseInt($("#settings_content").css("--column-count"), 10) === 2;
}

function set_settings_header(key: string): void {
    const selected_tab_key = $("#settings_page .tab-switcher .selected").attr("data-tab-key");
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
    $main_elem: JQuery;
    hash_prefix: string;
    $curr_li: JQuery;
    current_tab: string;
    current_user_settings_tab: string | undefined;
    current_bot_settings_tab: string | undefined;
    org_user_settings_toggler: Toggle;
    org_bot_settings_toggler: Toggle;

    constructor(opts: {$main_elem: JQuery; hash_prefix: string}) {
        this.$main_elem = opts.$main_elem;
        this.hash_prefix = opts.hash_prefix;
        this.$curr_li = this.$main_elem.children("li").eq(0);
        this.current_tab = this.$curr_li.attr("data-section")!;
        this.current_user_settings_tab = "active";
        this.current_bot_settings_tab = "all-bots";
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

        this.org_bot_settings_toggler = components.toggle({
            html_class: "org-bot-settings-switcher",
            child_wants_focus: true,
            values: [
                {label: $t({defaultMessage: "All bots"}), key: "all-bots"},
                {
                    label: $t({defaultMessage: "Your bots"}),
                    key: "your-bots",
                },
            ],
            callback: (_name, key) => {
                browser_history.update(`#organization/bots/${key}`);
                this.set_bot_settings_tab(key);
                $(".bot-settings-section").hide();
                if (key === "all-bots") {
                    redraw_all_bots_list();
                } else if (key === "your-bots") {
                    redraw_your_bots_list();
                }
                $(`[data-bot-settings-section="${CSS.escape(key)}"]`).show();
            },
        });

        this.$main_elem.on("click", "li[data-section]", (e) => {
            const section = $(e.currentTarget).attr("data-section")!;

            const settings_tab = this.get_settings_tab(section);
            this.activate_section_or_default(section, settings_tab);
            // You generally want to add logic to activate_section,
            // not to this click handler.

            e.stopPropagation();
        });
    }

    show(): void {
        this.$main_elem.show();
        const section = this.current_tab;

        const activate_section_for_mobile = two_column_mode();
        const settings_tab = this.get_settings_tab(section);
        this.activate_section_or_default(section, settings_tab, activate_section_for_mobile);
        this.$curr_li.trigger("focus");
    }

    show_org_user_settings_toggler(): void {
        if ($("#admin-user-list").find(".tab-switcher").length === 0) {
            const toggler_html = util.the(this.org_user_settings_toggler.get());
            $("#admin-user-list .tab-container").html(toggler_html);

            // We need to re-register these handlers since they are
            // destroyed once the settings modal closes.
            this.org_user_settings_toggler.register_event_handlers();
            this.set_key_handlers(this.org_user_settings_toggler, $(".org-user-settings-switcher"));
        }
    }

    show_org_bot_settings_toggler(): void {
        if ($("#admin-bot-list").find(".tab-switcher").length === 0) {
            const toggler_html = util.the(this.org_bot_settings_toggler.get());
            $("#admin-bot-list .tab-container").html(toggler_html);

            // We need to re-register these handlers since they are
            // destroyed once the settings modal closes.
            this.org_bot_settings_toggler.register_event_handlers();
            this.set_key_handlers(this.org_bot_settings_toggler, $(".org-bot-settings-switcher"));
        }
    }

    hide(): void {
        this.$main_elem.hide();
    }

    li_for_section(section: string): JQuery {
        const $li = $(`#settings_overlay_container li[data-section='${CSS.escape(section)}']`);
        return $li;
    }

    set_key_handlers(toggler: Toggle, $elem = this.$main_elem): void {
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

    prev(): boolean {
        const li = [...this.$curr_li.prevAll()].find((li) => li.getClientRects().length);
        li?.focus();
        li?.click();
        return true;
    }

    next(): boolean {
        const li = [...this.$curr_li.nextAll()].find((li) => li.getClientRects().length);
        li?.focus();
        li?.click();
        return true;
    }

    enter_panel(): boolean {
        const $panel = this.get_panel();
        [...$panel.find("input,button,select")]
            .find((element) => element.getClientRects().length)
            ?.focus();
        return true;
    }

    set_current_tab(tab: string): void {
        this.current_tab = tab;
    }

    set_user_settings_tab(tab: string | undefined): void {
        this.current_user_settings_tab = tab;
    }

    set_bot_settings_tab(tab: string | undefined): void {
        this.current_bot_settings_tab = tab;
    }

    get_settings_tab(section: string): string | undefined {
        if (section === "users") {
            return this.current_user_settings_tab;
        }

        if (section === "bots") {
            return this.current_bot_settings_tab;
        }

        return undefined;
    }

    activate_section_or_default(
        section: string | undefined,
        settings_tab?: string,
        activate_section_for_mobile = true,
    ): void {
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

        if (section !== "users" && section !== "bots") {
            const settings_section_hash = "#" + this.hash_prefix + section;

            // It could be that the hash has already been set.
            browser_history.update_hash_internally_if_required(settings_section_hash);
        }
        if (section === "users" && this.org_user_settings_toggler !== undefined) {
            assert(settings_tab !== undefined);
            this.show_org_user_settings_toggler();
            this.org_user_settings_toggler.goto(settings_tab);
        }

        if (section === "bots" && this.org_bot_settings_toggler !== undefined) {
            assert(settings_tab !== undefined);
            this.show_org_bot_settings_toggler();
            this.org_bot_settings_toggler.goto(settings_tab);
        }

        $(".settings-section").removeClass("show");

        settings_sections.load_settings_section(section);

        this.get_panel().addClass("show");

        scroll_util.reset_scrollbar($("#settings_content"));

        if (activate_section_for_mobile) {
            mobile_activate_section();
        }

        set_settings_header(section);
        resize_textareas_in_section(this.get_panel());
    }

    get_panel(): JQuery {
        const section = this.$curr_li.attr("data-section")!;
        const sel = `[data-name='${CSS.escape(section)}']`;
        const $panel = $(".settings-section" + sel);
        return $panel;
    }
}

export function initialize(): void {
    normal_settings = new SettingsPanelMenu({
        $main_elem: $(".normal-settings-list"),
        hash_prefix: "settings/",
    });
    org_settings = new SettingsPanelMenu({
        $main_elem: $(".org-settings-list"),
        hash_prefix: "organization/",
    });
}

export function show_normal_settings(): void {
    org_settings.hide();
    normal_settings.show();
}

export function show_org_settings(): void {
    normal_settings.hide();
    org_settings.show();
}

export function set_key_handlers(toggler: Toggle): void {
    normal_settings.set_key_handlers(toggler);
    org_settings.set_key_handlers(toggler);
}
