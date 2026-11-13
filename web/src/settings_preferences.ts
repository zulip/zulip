import {$} from "jquery";
import Cookies from "js-cookie";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";
import * as z from "zod/mini";

import render_dialog_default_language from "../templates/default_language_modal.hbs";
import render_confirm_language_change from "../templates/settings/confirm_language_change.hbs";
import render_confirm_left_sidebar_topics_order_default from "../templates/settings/confirm_left_sidebar_topics_order_default.hbs";

import * as channel from "./channel.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import * as emojisets from "./emojisets.ts";
import {$t, $t_html, get_language_list_columns} from "./i18n.ts";
import * as information_density from "./information_density.ts";
import * as loading from "./loading.ts";
import * as overlays from "./overlays.ts";
import {page_params} from "./page_params.ts";
import type {RealmDefaultSettings} from "./realm_user_settings_defaults.ts";
import * as settings_components from "./settings_components.ts";
import * as settings_config from "./settings_config.ts";
import type {RequestOpts} from "./settings_ui.ts";
import * as settings_ui from "./settings_ui.ts";
import * as stream_color from "./stream_color.ts";
import * as stream_data from "./stream_data.ts";
import type {StreamSubscription} from "./sub_store.ts";
import * as ui_report from "./ui_report.ts";
import {user_settings, user_settings_schema} from "./user_settings.ts";
import type {UserSettings} from "./user_settings.ts";
import * as util from "./util.ts";

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
let default_language_dropdown_widget: dropdown_widget.DropdownWidget;

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

function spectator_default_language_modal_post_render(): void {
    $("#language_selection_modal")
        .find(".language")
        .on("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            dialog_widget.close();

            assert(
                page_params.language_cookie_name !== undefined,
                "Expected language_cookie_name present for spectator",
            );

            const $link = $(e.target).closest("a[data-code]");
            Cookies.set(page_params.language_cookie_name, $link.attr("data-code")!);
            window.location.reload();
        });
}

export function launch_default_language_setting_modal_for_spectator(): void {
    const selected_language = user_settings.default_language;

    const modal_content_html = render_dialog_default_language({
        language_list: get_language_list_columns(selected_language).toSorted((a, b) =>
            util.strcmp(a.name_with_percent, b.name_with_percent),
        ),
    });

    dialog_widget.launch({
        modal_title_html: $t_html({defaultMessage: "Select language"}),
        modal_content_html,
        modal_submit_button_text: $t({defaultMessage: "Close"}),
        id: "language_selection_modal",
        close_on_submit: true,
        focus_submit_on_open: true,
        single_footer_button: true,
        post_render: spectator_default_language_modal_post_render,
        on_click() {
            // We perform no actions since the 'close_on_submit' field takes care
            // of closing the modal.
        },
    });
}

// Changing the default only affects channels that follow it, so
// before saving, list the channels that don't and offer to reset
// them. A reset can be undone until the change is confirmed, when
// the resets go in one request, and the new default is saved once
// they succeed.
function confirm_left_sidebar_topics_order_default_change(
    overriding_subs: StreamSubscription[],
    $status_element: JQuery,
    save: () => void,
    cancel: () => void,
): void {
    const values = Object.values(settings_config.web_left_sidebar_topics_order_values);
    const channels = overriding_subs.map((sub) => ({
        stream_id: sub.stream_id,
        name: sub.name,
        invite_only: sub.invite_only,
        is_web_public: sub.is_web_public,
        is_archived: sub.is_archived,
        stream_privacy_icon_color: stream_color.get_stream_privacy_icon_color(sub.color),
        order_description: values.find((value) => value.code === sub.left_sidebar_topics_order)
            ?.description,
    }));
    let saved = false;
    const stream_ids_to_reset = new Set<number>();

    function post_render(modal_unique_id: string): void {
        $(`#${CSS.escape(modal_unique_id)}`).on(
            "click",
            ".left-sidebar-topics-order-override-button",
            function (this: HTMLElement) {
                const $row = $(this).closest(".left-sidebar-topics-order-override");
                const stream_id = Number($row.attr("data-stream-id"));
                const will_reset = $(this).hasClass("reset-left-sidebar-topics-order");
                if (will_reset) {
                    stream_ids_to_reset.add(stream_id);
                } else {
                    stream_ids_to_reset.delete(stream_id);
                }
                $row.find(".left-sidebar-topics-order-override-value").toggleClass("hide");
                $row.find(".left-sidebar-topics-order-override-button").toggleClass("hide");
            },
        );
    }

    dialog_widget.launch({
        modal_title_html: $t_html({defaultMessage: "Change how resolved topics are shown?"}),
        modal_content_html: render_confirm_left_sidebar_topics_order_default({channels}),
        modal_submit_button_text: $t({defaultMessage: "Change default setting"}),
        id: "confirm_left_sidebar_topics_order_default",
        close_on_submit: true,
        post_render,
        on_click() {
            saved = true;
            if (stream_ids_to_reset.size === 0) {
                save();
                return;
            }
            const subscription_data = [...stream_ids_to_reset].map((stream_id) => ({
                stream_id,
                property: "left_sidebar_topics_order",
                value: settings_config.left_sidebar_topics_order_inherit,
            }));
            settings_ui.do_settings_change(
                channel.post,
                "/json/users/me/subscriptions/properties",
                {subscription_data: JSON.stringify(subscription_data)},
                $status_element,
                {success_continuation: save},
            );
        },
        on_hidden() {
            if (!saved) {
                cancel();
            }
        },
    });
}

export function set_up(settings_panel: SettingsPanel): void {
    meta.loaded = true;
    const $container = $(settings_panel.container);
    const settings_object = settings_panel.settings_object;
    const for_realm_settings = settings_panel.for_realm_settings;

    // Select current values for enum/select type fields. For boolean
    // fields, the current value is set automatically in the template.
    $container
        .find(".setting_demote_inactive_streams")
        .val(settings_object.demote_inactive_streams);
    $container
        .find(
            `.setting_color_scheme[value='${CSS.escape(settings_object.color_scheme.toString())}']`,
        )
        .prop("checked", true);
    $container.find(".setting_web_home_view").val(settings_object.web_home_view);
    $container
        .find(".setting_twenty_four_hour_time")
        .val(JSON.stringify(settings_object.twenty_four_hour_time));
    $container
        .find(".setting_web_mark_read_on_scroll_policy")
        .val(settings_object.web_mark_read_on_scroll_policy);
    $container
        .find(".setting_web_channel_default_view")
        .val(settings_object.web_channel_default_view);
    $container
        .find(`.setting_emojiset_choice[value="${CSS.escape(settings_object.emojiset)}"]`)
        .prop("checked", true);
    $container
        .find(`.setting_user_list_style_choice[value=${settings_object.user_list_style}]`)
        .prop("checked", true);
    $container
        .find(
            `.setting_web_left_sidebar_topics_order_choice[value=${settings_object.web_left_sidebar_topics_order}]`,
        )
        .prop("checked", true);

    $container
        .find(".setting_web_animate_image_previews")
        .val(settings_object.web_animate_image_previews);
    $container
        .find(".setting_web_stream_unreads_count_display_policy")
        .val(settings_object.web_stream_unreads_count_display_policy);

    information_density.enable_or_disable_control_buttons($container);

    if (for_realm_settings) {
        // For the realm-level defaults page, we use the common
        // settings_org.ts handlers, so we can return early here.
        return;
    }

    // Common handler for sending requests to the server when an input
    // element is changed.
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
        const data = {[changed_property]: new_value};

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
            {color_scheme: new_theme_code},
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
            success() {
                // We don't launch any success report, since it is currently handled
                // by function report_emojiset_change.
            },
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
            success() {
                // We don't launch any success report, since it is
                // currently handled by report_user_list_style_change.
            },
            error(xhr) {
                ui_report.error(
                    settings_ui.strings.failure_html,
                    xhr,
                    $container.find(".information-settings-status").expectOne(),
                );
            },
        });
    });

    $container.find(".setting_web_left_sidebar_topics_order_choice").on("change", function () {
        const value = Number($(this).val());
        if (value === settings_object.web_left_sidebar_topics_order) {
            return;
        }
        const $status_element = $container.find(".left-sidebar-settings-status").expectOne();
        const save = (): void => {
            change_display_setting({web_left_sidebar_topics_order: value}, $status_element);
        };
        const overriding_subs = stream_data
            .subscribed_subs()
            .filter(
                (sub) =>
                    sub.left_sidebar_topics_order !==
                    settings_config.left_sidebar_topics_order_inherit,
            );
        if (overriding_subs.length === 0) {
            save();
            return;
        }
        confirm_left_sidebar_topics_order_default_change(
            overriding_subs,
            $status_element,
            save,
            () => {
                $container
                    .find(
                        `.setting_web_left_sidebar_topics_order_choice[value=${settings_object.web_left_sidebar_topics_order}]`,
                    )
                    .prop("checked", true);
            },
        );
    });

    render_language_dropdown_widget();
}

export async function report_emojiset_change(settings_panel: SettingsPanel): Promise<void> {
    // TODO: Clean up how this works so we can use
    // change_display_setting.  The challenge is that we don't want to
    // report success before the server_events request returns that
    // causes the actual sprite sheet to change.  The current
    // implementation is wrong, though, in that it displays the UI
    // update in all active browser windows.
    await emojisets.select(settings_panel.settings_object.emojiset);

    const $spinner = $(settings_panel.container).find(".emoji-preferences-settings-status");
    if ($spinner.length > 0) {
        loading.destroy_indicator($spinner);
        ui_report.success(
            $t_html({defaultMessage: "Emoji set changed successfully!"}),
            $spinner.expectOne(),
            1000,
        );
        $spinner.expectOne();
        settings_ui.display_checkmark($spinner);
    }
}

export function report_user_list_style_change(settings_panel: SettingsPanel): void {
    // TODO: Clean up how this works so we can use
    // change_display_setting.  The challenge is that we don't want to
    // report success before the server_events request returns that
    // causes the actual sprite sheet to change.  The current
    // implementation is wrong, though, in that it displays the UI
    // update in all active browser windows.
    const $spinner = $(settings_panel.container).find(".information-settings-status");
    if ($spinner.length > 0) {
        loading.destroy_indicator($spinner);
        ui_report.success(
            $t_html({defaultMessage: "User list style changed successfully!"}),
            $spinner.expectOne(),
            1000,
        );
        $spinner.expectOne();
        settings_ui.display_checkmark($spinner);
    }
}

export function update_user_list_style_preview_name(full_name: string): void {
    $(".user_list_style_values .preview .user-name").text(full_name);
}

export function update_user_list_style_preview_avatar(avatar_url: string): void {
    $(".user_list_style_values .preview .user-profile-picture img").attr("src", avatar_url);
}

export function update_page(property: UserSettingsProperty): void {
    if (!overlays.settings_open()) {
        return;
    }
    const $container = $(user_settings_panel.container);
    let value = user_settings[property];

    // settings_org.set_input_element_value doesn't support radio
    // button widgets like these.
    if (property === "emojiset" || property === "user_list_style") {
        $container.find(`input[value=${CSS.escape(value.toString())}]`).prop("checked", true);
        return;
    }
    if (property === "web_left_sidebar_topics_order") {
        $container
            .find(`.setting_web_left_sidebar_topics_order_choice[value=${value}]`)
            .prop("checked", true);
        return;
    }

    // The twenty_four_hour_time setting is represented as a boolean
    // in the API, but a dropdown with "true"/"false" as strings in
    // the UI, so we need to convert its format here.
    if (property === "twenty_four_hour_time") {
        value = value.toString();
    }

    const $input_elem = $container.find(`[name=${CSS.escape(property)}]`);
    settings_components.set_input_element_value($input_elem, value);
}

function language_select_callback(
    event: JQuery.ClickEvent,
    dropdown: tippy.Instance,
    widget: dropdown_widget.DropdownWidget,
): void {
    dropdown.hide();
    event.preventDefault();
    event.stopPropagation();
    widget.render();

    const current_value = widget.current_value;
    assert(current_value !== undefined);
    const data = {default_language: current_value};
    const language_select_message_html = render_confirm_language_change();
    change_display_setting(
        data,
        $("#user-preferences").find(".general-settings-status"),
        undefined,
        undefined,
        language_select_message_html,
        true,
    );
}

export function set_default_language(default_language: string): void {
    if (!default_language_dropdown_widget) {
        return;
    }
    default_language_dropdown_widget.render(default_language);
}

function render_language_dropdown_widget(): void {
    default_language_dropdown_widget = new dropdown_widget.DropdownWidget({
        widget_name: "default_language",
        get_options: settings_components.language_options,
        item_click_callback: language_select_callback,
        default_id: user_settings.default_language,
        $events_container: $("#user-preferences .preferences-settings-form"),
        unique_id_type: "string",
    });
    default_language_dropdown_widget.setup();
}

export function initialize(): void {
    user_settings_panel = {
        container: "#user-preferences",
        settings_object: user_settings,
        for_realm_settings: false,
        notification_sound_elem: null,
    };
}
