import $ from "jquery";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import * as channel from "./channel.ts";
import * as emojisets from "./emojisets.ts";
import * as information_density from "./information_density.ts";
import * as loading from "./loading.ts";
import * as overlays from "./overlays.ts";
import {DropdownWidget} from "./dropdown_widget.ts";
import {$t_html, get_language_name} from "./i18n.ts";
import {page_params} from "./page_params.ts";
import type {RealmDefaultSettings} from "./realm_user_settings_defaults.ts";
import * as settings_components from "./settings_components.ts";
import type {RequestOpts} from "./settings_ui.ts";
import * as settings_ui from "./settings_ui.ts";
import {realm} from "./state_data.ts";
import * as ui_report from "./ui_report.ts";
import {user_settings, user_settings_schema} from "./user_settings.ts";
import type {UserSettings} from "./user_settings.ts";

export type SettingsPanel = {
    container: string;
    notification_sound_elem: string | null;
} & (
    | {
          settings_object: UserSettings;
          for_realm_settings: false;
      }
    | {
          settings_object: RealmDefaultSettings;
          for_realm_settings: true;
      }
);

export const user_settings_property_schema = z.keyof(
    z.omit(user_settings_schema, {available_notification_sounds: true, emojiset_choices: true}),
);
type UserSettingsProperty = z.output<typeof user_settings_property_schema>;

const meta = {
    loaded: false,
};

export let user_settings_panel: SettingsPanel;
export let user_default_language_name: string | undefined;

export function set_default_language_name(name: string | undefined): void {
    user_default_language_name = name;
}

function change_display_setting(
    data: Record<string, string | boolean | number>,
    $status_el: JQuery,
    success_continuation?: (response_data: unknown) => void,
    error_continuation?: (response_data: unknown) => void,
    success_msg_html?: string,
    sticky?: boolean,
): void {
    const status_is_sticky = $status_el.attr("data-is_sticky") === "true";
    const display_message_html = status_is_sticky
        ? $status_el.attr("data-sticky_msg_html")
        : success_msg_html;
    const opts: RequestOpts = {
        success_msg_html: display_message_html,
        sticky: status_is_sticky || sticky,
    };

    if (success_continuation !== undefined) {
        opts.success_continuation = success_continuation;
    }
    if (error_continuation !== undefined) {
        opts.error_continuation = error_continuation;
    }
    if (sticky && success_msg_html) {
        $status_el.attr("data-is_sticky", "true");
        $status_el.attr("data-sticky_msg_html", success_msg_html);
    }
    settings_ui.do_settings_change(channel.patch, "/json/settings", data, $status_el, opts);
}

export function set_up(settings_panel: SettingsPanel): void {
    meta.loaded = true;
    const $container = $(settings_panel.container);
    const settings_object = settings_panel.settings_object;
    const for_realm_settings = settings_panel.for_realm_settings;

    // ---- Default language dropdown ----
    const $dropdown_container = $container.find("#default_language_dropdown_container");

    if ($dropdown_container.length > 0) {
        const language_options = (page_params.all_languages ?? []).map((lang) => ({
            unique_id: lang.code,
            name: `${lang.name} (${lang.percent_translated}%)`,
        }));

        const default_language_dropdown = new DropdownWidget({
    widget_name: "default_language",
    default_id: settings_object.default_language ?? "en",
    $events_container: $container,   // ✅ pass container so events bind properly
    get_options() {
        return language_options;
    },
    item_click_callback(event, instance, widget) {
        const selected_lang = widget.value(); // better than instance.value()
        const data = {default_language: selected_lang};

        const $status_element = $container
            .closest(".subsection-parent")
            .find(".alert-notification");

        change_display_setting(
            data,
            $status_element,
            undefined,
            undefined,
            $t_html({
                defaultMessage:
                    "Saved. Please <z-link>reload</z-link> for the change to take effect.",
            }, {
                "z-link": (content_html) =>
                    `<a class='reload_link'>${content_html.join("")}</a>`,
            }),
            true,
        );
    },
});


        default_language_dropdown.setup($dropdown_container);
    }

    if (for_realm_settings) {
        // Realm settings handled separately → stop here.
        return;
    }

    // ---- General UI bindings for user preferences ----
    $container.on("change", "input[type=checkbox], select", function (this: HTMLElement, e) {
        const $input_elem = $(e.currentTarget);
        const setting = $input_elem.attr("name");
        assert(setting !== undefined);
        const data: Record<string, string | boolean | number> = {};
        const setting_value = settings_components.get_input_element_value(this)!;
        assert(typeof setting_value !== "object");
        data[setting] = setting_value;

        const $status_element = $input_elem
            .closest(".subsection-parent")
            .find(".alert-notification");
        change_display_setting(data, $status_element);
    });

    $container.find(".info-density-button").on("click", function (this: HTMLElement, e) {
        e.preventDefault();
        const changed_property = z
            .enum(["web_font_size_px", "web_line_height_percent"])
            .parse($(this).closest(".button-group").attr("data-property"));
        const original_value = user_settings[changed_property];

        const new_value = information_density.update_information_density_settings(
            $(this),
            changed_property,
            true,
        );
        const data: Record<string, number> = {};
        data[changed_property] = new_value;

        const $status_element = $(this).closest(".subsection-parent").find(".alert-notification");
        information_density.enable_or_disable_control_buttons($container);

        const error_continuation: () => void = () => {
            information_density.update_information_density_settings(
                $(this),
                changed_property,
                true,
                original_value,
            );
            information_density.enable_or_disable_control_buttons($container);
        };
        change_display_setting(data, $status_element, undefined, error_continuation);
    });

    $container.find(".setting_color_scheme").on("change", function () {
        const $input_elem = $(this);
        const new_theme_code = $input_elem.val();
        assert(new_theme_code !== undefined);
        const data = {color_scheme: new_theme_code};

        const $status_element = $input_elem
            .closest(".subsection-parent")
            .find(".alert-notification");

        const opts: RequestOpts = {
            error_continuation() {
                setTimeout(() => {
                    const prev_theme_code = user_settings.color_scheme;
                    $input_elem
                        .parent()
                        .find(
                            `.setting_color_scheme[value='${CSS.escape(prev_theme_code.toString())}']`,
                        )
                        .prop("checked", true);
                }, 500);
            },
        };

        settings_ui.do_settings_change(
            channel.patch,
            "/json/settings",
            data,
            $status_element,
            opts,
        );
    });

    $container.find(".setting_emojiset_choice").on("click", function () {
        const data = {emojiset: $(this).val()};
        const current_emojiset = settings_object.emojiset;
        if (current_emojiset === data.emojiset) {
            return;
        }
        const $spinner = $container.find(".emoji-preferences-settings-status").expectOne();
        loading.make_indicator($spinner, {text: settings_ui.strings.saving});

        void channel.patch({
            url: "/json/settings",
            data,
            success() {},
            error(xhr) {
                ui_report.error(
                    settings_ui.strings.failure_html,
                    xhr,
                    $container.find(".emoji-preferences-settings-status").expectOne(),
                );
            },
        });
    });

    $container.find(".setting_user_list_style_choice").on("click", function () {
        const data = {user_list_style: $(this).val()};
        const current_user_list_style = settings_object.user_list_style;
        if (current_user_list_style === data.user_list_style) {
            return;
        }
        const $spinner = $container.find(".information-settings-status").expectOne();
        loading.make_indicator($spinner, {text: settings_ui.strings.saving});

        void channel.patch({
            url: "/json/settings",
            data,
            success() {},
            error(xhr) {
                ui_report.error(
                    settings_ui.strings.failure_html,
                    xhr,
                    $container.find(".information-settings-status").expectOne(),
                );
            },
        });
    });
}

export async function report_emojiset_change(settings_panel: SettingsPanel): Promise<void> {
    await emojisets.select(settings_panel.settings_object.emojiset);

    const $spinner = $(settings_panel.container).find(".emoji-preferences-settings-status");
    if ($spinner.length > 0) {
        loading.destroy_indicator($spinner);
        ui_report.success(
            $t_html({defaultMessage: "Emoji set changed successfully!"}),
            $spinner.expectOne(),
            1000,
        );
        settings_ui.display_checkmark($spinner);
    }
}

export function report_user_list_style_change(settings_panel: SettingsPanel): void {
    const $spinner = $(settings_panel.container).find(".information-settings-status");
    if ($spinner.length > 0) {
        loading.destroy_indicator($spinner);
        ui_report.success(
            $t_html({defaultMessage: "User list style changed successfully!"}),
            $spinner.expectOne(),
            1000,
        );
        settings_ui.display_checkmark($spinner);
    }
}

export function update_page(property: UserSettingsProperty): void {
    if (!overlays.settings_open()) {
        return;
    }
    const $container = $(user_settings_panel.container);
    let value = user_settings[property];

    if (property === "default_language") {
        const $dropdown_container = $container.find("#default_language_dropdown_container");
        const current_lang = user_settings.default_language;
        const language_name = get_language_name(current_lang);
        $dropdown_container.find(".dropdown_widget_value").text(language_name);
        return;
    }

    if (property === "emojiset" || property === "user_list_style") {
        $container.find(`input[value=${CSS.escape(value.toString())}]`).prop("checked", true);
        return;
    }

    if (property === "twenty_four_hour_time") {
        value = value.toString();
    }

    const $input_elem = $container.find(`[name=${CSS.escape(property)}]`);
    settings_components.set_input_element_value($input_elem, value);
}

export function initialize(): void {
    const user_language_name = get_language_name(user_settings.default_language);
    set_default_language_name(user_language_name);

    user_settings_panel = {
        container: "#user-preferences",
        settings_object: user_settings,
        for_realm_settings: false,
        notification_sound_elem: null,
    };
}
