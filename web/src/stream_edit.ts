import ClipboardJS from "clipboard";
import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";
import * as z from "zod/mini";

import render_settings_deactivation_stream_modal from "../templates/confirm_dialog/confirm_deactivate_stream.hbs";
import render_settings_reactivation_stream_modal from "../templates/confirm_dialog/confirm_reactivate_stream.hbs";
import render_inline_decorated_channel_name from "../templates/inline_decorated_channel_name.hbs";
import render_change_stream_info_modal from "../templates/stream_settings/change_stream_info_modal.hbs";
import render_confirm_stream_privacy_change_modal from "../templates/stream_settings/confirm_stream_privacy_change_modal.hbs";
import render_copy_email_address_modal from "../templates/stream_settings/copy_email_address_modal.hbs";
import render_create_channel_folder_modal from "../templates/stream_settings/create_channel_folder_modal.hbs";
import render_stream_description from "../templates/stream_settings/stream_description.hbs";
import render_stream_settings from "../templates/stream_settings/stream_settings.hbs";

import * as blueslip from "./blueslip.ts";
import type {Bot} from "./bot_data.ts";
import * as browser_history from "./browser_history.ts";
import * as channel from "./channel.ts";
import * as channel_folders from "./channel_folders.ts";
import * as confirm_dialog from "./confirm_dialog.ts";
import {show_copied_confirmation} from "./copied_tooltip.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import {$t, $t_html} from "./i18n.ts";
import * as keydown_util from "./keydown_util.ts";
import * as narrow_state from "./narrow_state.ts";
import {page_params} from "./page_params.ts";
import type {User} from "./people.ts";
import * as people from "./people.ts";
import * as popovers from "./popovers.ts";
import {postprocess_content} from "./postprocess_content.ts";
import * as scroll_util from "./scroll_util.ts";
import * as settings_components from "./settings_components.ts";
import * as settings_config from "./settings_config.ts";
import * as settings_data from "./settings_data.ts";
import * as settings_notifications from "./settings_notifications.ts";
import * as settings_org from "./settings_org.ts";
import type {CurrentUser} from "./state_data.ts";
import {current_user, realm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_edit_subscribers from "./stream_edit_subscribers.ts";
import * as stream_edit_toggler from "./stream_edit_toggler.ts";
import * as stream_settings_api from "./stream_settings_api.ts";
import * as stream_settings_components from "./stream_settings_components.ts";
import * as stream_settings_containers from "./stream_settings_containers.ts";
import * as stream_settings_data from "./stream_settings_data.ts";
import type {SettingsSubscription} from "./stream_settings_data.ts";
import {
    stream_permission_group_settings_schema,
    stream_properties_schema,
    stream_specific_notification_settings_schema,
} from "./stream_types.ts";
import * as stream_ui_updates from "./stream_ui_updates.ts";
import * as sub_store from "./sub_store.ts";
import type {StreamSubscription} from "./sub_store.ts";
import * as ui_report from "./ui_report.ts";
import {user_settings} from "./user_settings.ts";
import * as util from "./util.ts";

type StreamSetting = {
    name: z.output<typeof settings_labels_schema>;
    label: string;
    disabled_realm_setting: boolean;
    is_disabled: boolean;
    has_global_notification_setting: boolean;
    is_checked: boolean;
};

const settings_labels_schema = z.keyof(z.omit(stream_properties_schema, {color: true}));

const realm_labels_schema = z.enum([
    "push_notifications",
    "enable_online_push_notifications",
    "message_content_in_email_notifications",
]);

const notification_labels_schema = z.keyof(stream_specific_notification_settings_schema);

export function setup_subscriptions_tab_hash(tab_key_value: string): void {
    if ($("#subscription_overlay .right").hasClass("show")) {
        return;
    }
    switch (tab_key_value) {
        case "all-streams": {
            browser_history.update("#channels/all");
            break;
        }
        case "subscribed": {
            browser_history.update("#channels/subscribed");
            break;
        }
        case "not-subscribed": {
            browser_history.update("#channels/notsubscribed");
            break;
        }
        default: {
            blueslip.debug("Unknown tab_key_value: " + tab_key_value);
        }
    }
}

export function get_display_text_for_realm_message_retention_setting(): string {
    const realm_message_retention_days = realm.realm_message_retention_days;
    if (realm_message_retention_days === settings_config.retain_message_forever) {
        return $t({defaultMessage: "(forever)"});
    }
    return $t(
        {defaultMessage: "({message_retention_days} days)"},
        {message_retention_days: realm_message_retention_days},
    );
}

function get_stream_id(target: HTMLElement): number {
    const $row = $(target).closest(
        ".stream-row, .stream_settings_header, .subscription_settings, .save-button",
    );
    return Number.parseInt($row.attr("data-stream-id")!, 10);
}

function get_sub_for_target(target: HTMLElement): StreamSubscription {
    const stream_id = get_stream_id(target);
    const sub = sub_store.get(stream_id);
    assert(sub !== undefined);
    return sub;
}

export function open_edit_panel_for_row(stream_row: HTMLElement): void {
    const sub = get_sub_for_target(stream_row);

    $(".stream-row.active").removeClass("active");
    stream_settings_components.show_subs_pane.settings(sub);
    $(stream_row).addClass("active");
    setup_stream_settings(stream_row);
}

export function empty_right_panel(): void {
    $(".stream-row.active").removeClass("active");
    $("#subscription_overlay .right").removeClass("show");
    stream_settings_components.show_subs_pane.nothing_selected();
}

export function open_edit_panel_empty(): void {
    const tab_key = stream_settings_components
        .get_active_data()
        .$tabs.first()
        .attr("data-tab-key")!;
    empty_right_panel();
    setup_subscriptions_tab_hash(tab_key);
}

export function update_stream_name(sub: StreamSubscription, new_name: string): void {
    const $edit_container = stream_settings_containers.get_edit_container(sub);
    $edit_container.find(".sub-stream-name").text(new_name);

    const active_data = stream_settings_components.get_active_data();
    if (active_data.id === sub.stream_id) {
        stream_settings_components.set_right_panel_title(sub);
    }
}

export function update_stream_description(sub: StreamSubscription): void {
    const $edit_container = stream_settings_containers.get_edit_container(sub);
    $edit_container.find("input.description").val(sub.description);
    const html = render_stream_description({
        rendered_description: postprocess_content(sub.rendered_description),
    });
    $edit_container.find(".stream-description").html(html);
}

function show_subscription_settings(sub: SettingsSubscription): void {
    const $edit_container = stream_settings_containers.get_edit_container(sub);
    stream_ui_updates.update_add_subscriptions_elements(sub);

    if (!sub.render_subscribers) {
        return;
    }

    if (!stream_data.can_toggle_subscription(sub)) {
        stream_ui_updates.initialize_cant_subscribe_popover();
    }

    const $subscriber_container = $edit_container.find(".edit_subscribers_for_stream");
    stream_edit_subscribers.enable_subscriber_management({
        sub,
        $parent_container: $subscriber_container,
    });
}

function is_notification_setting(setting_label: string): boolean {
    return (
        notification_labels_schema.safeParse(setting_label).success || setting_label === "is_muted"
    );
}

export function stream_settings(sub: StreamSubscription): StreamSetting[] {
    const settings_labels = settings_config.general_notifications_table_labels.stream;
    const check_realm_setting =
        settings_config.all_notifications(user_settings).disabled_notification_settings;

    return settings_labels.map(([setting, label]) => {
        const parsed_realm_setting = realm_labels_schema.safeParse(setting);
        const realm_setting = parsed_realm_setting.success
            ? check_realm_setting[parsed_realm_setting.data]
            : false;
        const notification_setting = notification_labels_schema.safeParse(setting);

        let is_checked;
        if (notification_setting.success) {
            // This block ensures we correctly display to users the
            // current state of stream-level notification settings
            // with a value of `null`, which inherit the user's global
            // notification settings for streams.
            is_checked =
                stream_data.receives_notifications(sub.stream_id, notification_setting.data) &&
                !realm_setting;
        } else {
            is_checked = Boolean(sub[setting]) && !realm_setting;
        }
        return {
            name: setting,
            label,
            disabled_realm_setting: realm_setting,
            is_disabled: realm_setting,
            has_global_notification_setting: notification_setting.success,
            is_checked,
        };
    });
}

function setup_group_setting_widgets(sub: StreamSubscription): void {
    for (const setting_name of Object.keys(realm.server_supported_permission_settings.stream)) {
        settings_components.create_stream_group_setting_widget({
            $pill_container: $("#id_" + setting_name),
            setting_name: stream_permission_group_settings_schema.parse(setting_name),
            sub,
        });
    }
}

export function show_settings_for(node: HTMLElement): void {
    // Hide any tooltips or popovers before we rerender / change
    // currently displayed stream settings.
    popovers.hide_all();
    const stream_id = get_stream_id(node);
    const slim_sub = sub_store.get(stream_id);
    assert(slim_sub !== undefined);
    stream_data.clean_up_description(slim_sub);
    const sub = stream_settings_data.get_sub_for_settings(slim_sub);
    const all_settings = stream_settings(sub);

    const other_settings: StreamSetting[] = [];
    const notification_settings = all_settings.filter((setting) => {
        if (is_notification_setting(setting.name)) {
            return true;
        }
        other_settings.push(setting);
        return false;
    });

    const html = render_stream_settings({
        sub,
        notification_settings,
        other_settings,
        stream_privacy_policy_values: settings_config.stream_privacy_policy_values,
        stream_privacy_policy: stream_data.get_stream_privacy_policy(stream_id),
        stream_topics_policy_values: settings_config.get_stream_topics_policy_values(),
        check_default_stream: stream_data.is_default_stream_id(stream_id),
        zulip_plan_is_not_limited: realm.zulip_plan_is_not_limited,
        upgrade_text_for_wide_organization_logo: realm.upgrade_text_for_wide_organization_logo,
        is_business_type_org:
            realm.realm_org_type === settings_config.all_org_type_values.business.code,
        is_admin: current_user.is_admin,
        org_level_message_retention_setting: get_display_text_for_realm_message_retention_setting(),
        can_access_stream_email: stream_data.can_access_stream_email(sub),
        group_setting_labels: settings_config.all_group_setting_labels.stream,
        has_billing_access: settings_data.user_has_billing_access(),
        is_development_environment: page_params.development_environment,
        empty_string_topic_display_name: util.get_final_topic_display_name(""),
    });
    scroll_util.get_content_element($("#stream_settings")).html(html);

    stream_edit_toggler.toggler.get().prependTo("#stream_settings .tab-container");
    stream_ui_updates.set_up_right_panel_section(sub);

    const $edit_container = stream_settings_containers.get_edit_container(sub);

    $(".nothing-selected").hide();
    $("#subscription_overlay .stream_change_property_info").hide();
    $("#id_topics_policy").val(sub.topics_policy);

    $edit_container.addClass("show");

    stream_ui_updates.update_settings_button_for_archive_and_unarchive(sub);
    show_subscription_settings(sub);
    settings_org.set_message_retention_setting_dropdown(sub);
    stream_ui_updates.enable_or_disable_permission_settings_in_edit_panel(sub);
    setup_group_setting_widgets(slim_sub);
    stream_ui_updates.update_can_subscribe_group_label($edit_container);
    settings_components.set_up_folder_dropdown_widget(sub);

    $("#channels_overlay_container").on(
        "click",
        ".stream-creation-confirmation-banner .main-view-banner-close-button",
        (e) => {
            e.preventDefault();
            $(e.target).parent().remove();
        },
    );
}

export function setup_stream_settings(node: HTMLElement): void {
    stream_edit_toggler.setup_toggler();
    show_settings_for(node);
}

export function update_muting_rendering(sub: StreamSubscription): void {
    const $edit_container = stream_settings_containers.get_edit_container(sub);
    const $is_muted_checkbox = $edit_container.find("#sub_is_muted_setting .sub_setting_control");

    $is_muted_checkbox.prop("checked", sub.is_muted);
    $edit_container.find(".mute-note").toggleClass("hide-mute-note", !sub.is_muted);
}

function stream_setting_changed(elem: HTMLInputElement): void {
    const sub = get_sub_for_target(elem);
    const $status_element = $(elem).closest(".subsection-parent").find(".alert-notification");
    const setting = settings_labels_schema.parse(elem.name);
    const notification_setting = notification_labels_schema.safeParse(setting);
    if (notification_setting.success && sub[setting] === null) {
        sub[setting] =
            user_settings[
                settings_config.generalize_stream_notification_setting[notification_setting.data]
            ];
    }
    stream_settings_api.set_stream_property(
        sub,
        {property: setting, value: elem.checked},
        $status_element,
    );
}

export function archive_stream(stream_id: number, $alert_element: JQuery): void {
    dialog_widget.show_dialog_spinner();
    channel.del({
        url: "/json/streams/" + stream_id,
        success() {
            dialog_widget.hide_dialog_spinner();
        },
        error(xhr) {
            ui_report.error($t_html({defaultMessage: "Failed"}), xhr, $alert_element);
            dialog_widget.hide_dialog_spinner();
        },
    });
}

export function get_stream_email_address(flags: string[], address: string): string {
    const clean_address = address
        .replace(".show-sender", "")
        .replace(".include-footer", "")
        .replace(".include-quotes", "")
        .replace(".prefer-html", "");

    const flag_string = flags.map((flag) => "." + flag).join("");

    return clean_address.replace("@", flag_string + "@");
}

function show_stream_email_address_modal(address: string, sub: StreamSubscription): void {
    const copy_email_address_modal_html = render_copy_email_address_modal({
        email_address: address,
        tags: [
            {
                name: "show-sender",
                description: $t({
                    defaultMessage: "The sender's email address",
                }),
            },
            {
                name: "include-footer",
                description: $t({defaultMessage: "Email footers (e.g., signature)"}),
            },
            {
                name: "include-quotes",
                description: $t({defaultMessage: "Quoted original email (in replies)"}),
            },
            {
                name: "prefer-html",
                description: $t({
                    defaultMessage: "Use html encoding (not recommended)",
                }),
            },
        ],
    });

    function get_checked_tags(): string[] {
        const flags: string[] = [];
        const $checked_checkboxes = $(".copy-email-modal").find("input:checked");
        $($checked_checkboxes).each(function () {
            flags.push($(this).attr("id")!);
        });
        return flags;
    }

    function enable_tag_checkbox_change_handler(): void {
        // Since channel email addresses encode a sender, we can only
        // continuously update the email address when we have a current
        // sender.
        $("#copy_email_address_modal .tag-checkbox").on("change", () => {
            const flags = get_checked_tags();
            address = get_stream_email_address(flags, address);
            $(".email-address").text(address);
        });
    }

    function generate_email_modal_post_render(): void {
        function update_option_label(sender: User | CurrentUser | Bot): string {
            if (sender.user_id === people.EMAIL_GATEWAY_BOT.user_id) {
                return "Email Gateway bot";
            } else if (sender.user_id === current_user.user_id) {
                return $t({defaultMessage: "You"});
            }
            return sender.full_name;
        }

        function get_options(): {
            name: string;
            unique_id: number;
        }[] {
            const senders: (User | CurrentUser | Bot)[] = [people.EMAIL_GATEWAY_BOT];
            senders.push(
                ...stream_data.get_current_user_and_their_bots_with_post_messages_permission(sub),
            );
            return senders.map((sender) => ({
                name: update_option_label(sender),
                unique_id: sender.user_id,
            }));
        }

        function item_click_callback(event: JQuery.ClickEvent, dropdown: tippy.Instance): void {
            sender_dropdown_widget.render();
            $(sender_dropdown_widget.widget_selector).trigger("input");
            dropdown.hide();

            // Since channel email addresses encode a sender, we can
            // only continuously update the email address when we have
            // a current sender.
            $("#copy_email_address_modal .tag-checkbox").off("change");
            $(".stream-email").children().css("visibility", "hidden");
            $("#copy_email_address_modal .dialog_submit_button").trigger("focus");

            event.stopPropagation();
            event.preventDefault();
        }

        const sender_dropdown_widget = new dropdown_widget.DropdownWidget({
            widget_name: "sender_channel_email_address",
            get_options,
            item_click_callback,
            $events_container: $("#copy_email_address_modal"),
            default_id: people.EMAIL_GATEWAY_BOT.user_id,
            unique_id_type: "number",
            hide_search_box: true,
        });
        sender_dropdown_widget.setup();
    }

    function generate_email_address(): void {
        const close_on_success = false;
        dialog_widget.submit_api_request(
            channel.get,
            "/json/streams/" + sub.stream_id + "/email_address",
            {},
            {
                success_continuation(response_data) {
                    const email = z.object({email: z.string()}).parse(response_data).email;
                    const flags = get_checked_tags();
                    address = get_stream_email_address(flags, email);
                    $(".email-address").text(address);
                    $(".stream-email").children().css("visibility", "visible");
                    enable_tag_checkbox_change_handler();
                },
            },
            close_on_success,
        );
    }

    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Generate channel email address"}),
        html_body: copy_email_address_modal_html,
        id: "copy_email_address_modal",
        html_submit_button: $t_html({defaultMessage: "Generate email address"}),
        html_exit_button: $t_html({defaultMessage: "Close"}),
        help_link: "/help/message-a-channel-by-email#configuration-options",
        post_render: generate_email_modal_post_render,
        on_click: generate_email_address,
        close_on_submit: false,
        always_visible_scrollbar: true,
    });
    $("#show-sender").prop("checked", true);

    const email_address_clipboard = new ClipboardJS(
        "#copy_email_address_modal .copy-email-address",
        {
            text() {
                return $(".email-address").text();
            },
        },
    );
    email_address_clipboard.on("success", (e) => {
        assert(e.trigger instanceof HTMLElement);
        show_copied_confirmation(e.trigger, {
            show_check_icon: true,
        });
    });

    enable_tag_checkbox_change_handler();
}

export function initialize(): void {
    $("#main_div").on("click", ".stream_sub_unsub_button", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const sub = narrow_state.stream_sub();
        if (sub === undefined) {
            return;
        }

        stream_settings_components.sub_or_unsub(sub);
    });

    $("#channels_overlay_container").on(
        "click",
        "#open_stream_info_modal",
        function (this: HTMLElement, e) {
            e.preventDefault();
            e.stopPropagation();
            const stream_id = get_stream_id(this);
            const stream = sub_store.get(stream_id);
            assert(stream !== undefined);
            const template_data = {
                stream_name: stream.name,
                stream_description: stream.description,
                max_stream_name_length: realm.max_stream_name_length,
                max_stream_description_length: realm.max_stream_description_length,
            };
            const change_stream_info_modal = render_change_stream_info_modal(template_data);
            dialog_widget.launch({
                html_heading: $t_html(
                    {defaultMessage: "Edit #{channel_name}"},
                    {channel_name: stream.name},
                ),
                html_body: change_stream_info_modal,
                id: "change_stream_info_modal",
                loading_spinner: true,
                on_click: save_stream_info,
                post_render() {
                    $("#change_stream_info_modal .dialog_submit_button")
                        .addClass("save-button")
                        .attr("data-stream-id", stream_id);
                },
                update_submit_disabled_state_on_change: true,
            });
        },
    );

    $("#channels_overlay_container").on("keydown", "#change_stream_description", (e) => {
        // Stream descriptions cannot be multiline, so disable enter key
        // to prevent new line
        if (keydown_util.is_enter_event(e)) {
            return false;
        }
        return true;
    });

    $("#channels_overlay_container").on(
        "click",
        ".stream-permissions-warning-banner .main-view-banner-close-button",
        (event) => {
            event.preventDefault();
            $("#stream_settings .stream-permissions-warning-banner").empty();
        },
    );

    $("#channels_overlay_container").on(
        "click",
        ".stream-permissions-warning-banner .main-view-banner-action-button",
        (event) => {
            event.preventDefault();
            event.stopPropagation();

            const $target = $(event.target).parents(".main-view-banner");
            const stream_id = Number.parseInt($target.attr("data-stream-id")!, 10);
            // Makes sure we take the correct stream_row.
            const $stream_row = $(
                `#channels_overlay_container div.stream-row[data-stream-id='${CSS.escape(
                    stream_id.toString(),
                )}']`,
            );
            const sub = sub_store.get(stream_id);
            assert(sub !== undefined);
            stream_settings_components.sub_or_unsub(sub, $stream_row);
            $("#stream_settings .stream-permissions-warning-banner").empty();
        },
    );

    function save_stream_info(): void {
        const sub = get_sub_for_target(
            util.the($("#change_stream_info_modal .dialog_submit_button")),
        );
        const url = `/json/streams/${sub.stream_id}`;
        const data: {new_name?: string; description?: string} = {};
        const new_name = $<HTMLInputElement>("input#change_stream_name").val()!.trim();
        const new_description = $<HTMLTextAreaElement>("textarea#change_stream_description")
            .val()!
            .trim();

        if (new_name !== sub.name) {
            data.new_name = new_name;
        }
        if (new_description !== sub.description) {
            data.description = new_description;
        }

        dialog_widget.submit_api_request(channel.patch, url, data);
    }

    $("#channels_overlay_container").on(
        "click",
        ".copy_email_button",
        function (this: HTMLElement, e) {
            e.preventDefault();
            e.stopPropagation();

            const stream_id = get_stream_id(this);

            channel.get({
                url: "/json/streams/" + stream_id + "/email_address",
                success(data) {
                    const address = z.object({email: z.string()}).parse(data).email;
                    const sub = sub_store.get(stream_id);
                    assert(sub !== undefined);
                    show_stream_email_address_modal(address, sub);
                },
                error(xhr) {
                    ui_report.error(
                        $t_html({defaultMessage: "Failed"}),
                        xhr,
                        $(".stream_email_address_error"),
                    );
                },
            });
        },
    );

    $("#channels_overlay_container").on(
        "click",
        ".subsection-parent .reset-stream-notifications-button",
        function on_click(this: HTMLElement) {
            const sub = get_sub_for_target(this);
            settings_notifications.do_reset_stream_notifications(this, sub);
        },
    );

    $("#channels_overlay_container").on(
        "change",
        ".sub_setting_checkbox input.sub_setting_control",
        function on_change(this: HTMLInputElement, _event: JQuery.Event) {
            stream_setting_changed(this);
        },
    );

    // This handler isn't part of the normal edit interface; it's the convenient
    // checkmark in the subscriber list.
    $("#channels_overlay_container").on(
        "click",
        ".sub_unsub_button",
        function (this: HTMLElement, e) {
            if ($(this).hasClass("disabled")) {
                // We do not allow users to subscribe themselves to private streams.
                return;
            }

            const sub = get_sub_for_target(this);
            // Makes sure we take the correct stream_row.
            const $stream_row = $(
                `#channels_overlay_container div.stream-row[data-stream-id='${CSS.escape(
                    sub.stream_id.toString(),
                )}']`,
            );
            stream_settings_components.sub_or_unsub(sub, $stream_row);

            if (!sub.subscribed) {
                open_edit_panel_for_row(util.the($stream_row));
            }
            stream_ui_updates.update_regular_sub_settings(sub);

            e.preventDefault();
            e.stopPropagation();
        },
    );

    $("#channels_overlay_container").on("click", ".deactivate", function (this: HTMLElement, e) {
        e.preventDefault();
        e.stopPropagation();

        function do_archive_stream(): void {
            const stream_id = Number($(".dialog_submit_button").attr("data-stream-id"));
            archive_stream(stream_id, $(".stream_change_property_info"));
        }

        const stream_id = get_stream_id(this);
        const stream = sub_store.get(stream_id);

        const stream_name_with_privacy_symbol_html = render_inline_decorated_channel_name({stream});

        const is_new_stream_announcements_stream =
            stream_id === realm.realm_new_stream_announcements_stream_id;
        const is_signup_announcements_stream =
            stream_id === realm.realm_signup_announcements_stream_id;
        const is_zulip_update_announcements_stream =
            stream_id === realm.realm_zulip_update_announcements_stream_id;
        const is_announcement_stream =
            is_new_stream_announcements_stream ||
            is_signup_announcements_stream ||
            is_zulip_update_announcements_stream;

        const html_body = render_settings_deactivation_stream_modal({
            stream_name_with_privacy_symbol_html,
            is_new_stream_announcements_stream,
            is_signup_announcements_stream,
            is_zulip_update_announcements_stream,
            is_announcement_stream,
        });

        confirm_dialog.launch({
            html_heading: $t_html(
                {defaultMessage: "Archive <z-link></z-link>?"},
                {"z-link": () => stream_name_with_privacy_symbol_html},
            ),
            id: "archive-stream-modal",
            help_link: "/help/archive-a-channel",
            html_body,
            on_click: do_archive_stream,
        });

        $(".dialog_submit_button").attr("data-stream-id", stream_id);
    });

    $("#channels_overlay_container").on("click", ".reactivate", function (this: HTMLElement, e) {
        e.preventDefault();
        e.stopPropagation();
        const stream_id = get_stream_id(this);
        function do_unarchive_stream(): void {
            dialog_widget.show_dialog_spinner();
            channel.patch({
                url: `/json/streams/${stream_id}`,
                data: {is_archived: false},
                success() {
                    dialog_widget.hide_dialog_spinner();
                },
                error(xhr) {
                    ui_report.error(
                        $t_html({defaultMessage: "Failed"}),
                        xhr,
                        $(".stream_change_property_info"),
                    );
                    dialog_widget.hide_dialog_spinner();
                },
            });
        }

        const stream = sub_store.get(stream_id);
        const stream_name_with_privacy_symbol_html = render_inline_decorated_channel_name({stream});
        const html_body = render_settings_reactivation_stream_modal();

        confirm_dialog.launch({
            html_heading: $t_html(
                {defaultMessage: "Unarchive <z-link></z-link>?"},
                {"z-link": () => stream_name_with_privacy_symbol_html},
            ),
            id: "unarchive-stream-modal",
            html_body,
            on_click: do_unarchive_stream,
        });

        $(".dialog_submit_button").attr("data-stream-id", stream_id);
    });

    $("#channels_overlay_container").on("click", ".stream-row", function (this: HTMLElement, e) {
        e.preventDefault();
        e.stopPropagation();
        open_edit_panel_for_row(this);
    });

    $("#channels_overlay_container").on(
        "click",
        ".subscriber-count",
        function (this: HTMLElement, e) {
            e.preventDefault();
            e.stopPropagation();
            stream_edit_toggler.set_select_tab("subscribers");
            open_edit_panel_for_row(this);
        },
    );

    $<HTMLSelectElement>("#channels_overlay_container").on(
        "change",
        "select.stream_message_retention_setting",
        function (this: HTMLSelectElement) {
            const message_retention_setting_dropdown_value = this.value;
            settings_components.change_element_block_display_property(
                "id_stream_message_retention_custom_input",
                message_retention_setting_dropdown_value === "custom_period",
            );
        },
    );

    $("#channels_overlay_container").on(
        "change input",
        "input, select, textarea",
        function (this: HTMLElement, e): boolean {
            e.preventDefault();
            e.stopPropagation();

            if ($(this).hasClass("no-input-change-detection")) {
                // This is to prevent input changes detection in elements
                // within a subsection whose changes should not affect the
                // visibility of the discard button
                return false;
            }

            const stream_id = get_stream_id(this);
            const sub = sub_store.get(stream_id);
            const $subsection = $(this).closest(".settings-subsection-parent");
            settings_components.save_discard_stream_settings_widget_status_handler(
                $subsection,
                sub,
            );
            if (sub && $subsection.hasClass("stream-permissions")) {
                stream_ui_updates.update_default_stream_and_stream_privacy_state(
                    $("#stream_settings"),
                );
                const $edit_container = stream_settings_containers.get_edit_container(sub);
                stream_ui_updates.update_can_subscribe_group_label($edit_container);
            }
            return true;
        },
    );

    $("#channels_overlay_container").on(
        "click",
        ".subsection-header .subsection-changes-save .save-button[data-status='unsaved']",
        function (this: HTMLElement, e) {
            e.preventDefault();
            e.stopPropagation();
            const $save_button = $(this);
            const $subsection_elem = $save_button.closest(".settings-subsection-parent");

            const stream_id = Number(
                $save_button.closest(".subscription_settings.show").attr("data-stream-id"),
            );
            const sub = sub_store.get(stream_id);
            assert(sub !== undefined);
            const data = settings_components.populate_data_for_stream_settings_request(
                $subsection_elem,
                sub,
            );

            const url = "/json/streams/" + stream_id;
            if (
                data.is_private === undefined ||
                stream_data.get_stream_privacy_policy(stream_id) !== "invite-only"
            ) {
                settings_org.save_organization_settings(data, $save_button, url);
                return;
            }
            dialog_widget.launch({
                html_heading: $t_html({defaultMessage: "Confirm changing access permissions"}),
                html_body: render_confirm_stream_privacy_change_modal(),
                id: "confirm_stream_privacy_change",
                html_submit_button: $t_html({defaultMessage: "Confirm"}),
                on_click() {
                    settings_org.save_organization_settings(data, $save_button, url);
                },
                close_on_submit: true,
            });
        },
    );

    $("#channels_overlay_container").on(
        "click",
        ".subsection-header .subsection-changes-discard button",
        function (e) {
            e.preventDefault();
            e.stopPropagation();

            const stream_id = Number(
                $(this).closest(".subscription_settings.show").attr("data-stream-id"),
            );
            const sub = sub_store.get(stream_id);
            assert(sub !== undefined);

            const $subsection = $(this).closest(".settings-subsection-parent");
            settings_org.discard_stream_settings_subsection_changes($subsection, sub);
            if ($subsection.hasClass("stream-permissions")) {
                stream_ui_updates.update_default_stream_and_stream_privacy_state(
                    $("#stream_settings"),
                );
                const $edit_container = stream_settings_containers.get_edit_container(sub);
                stream_ui_updates.update_can_subscribe_group_label($edit_container);
            }
        },
    );

    $("#channels_overlay_container").on("click", ".create-channel-folder-button", () => {
        const html_body = render_create_channel_folder_modal({
            max_channel_folder_name_length: channel_folders.MAX_CHANNEL_FOLDER_NAME_LENGTH,
            max_channel_folder_description_length:
                channel_folders.MAX_CHANNEL_FOLDER_DESCRIPTION_LENGTH,
        });

        function create_channel_folder(): void {
            const close_on_success = true;
            const data = {
                name: $<HTMLInputElement>("input#new_channel_folder_name").val()!.trim(),
                description: $<HTMLTextAreaElement>("textarea#new_channel_folder_description")
                    .val()!
                    .trim(),
            };
            dialog_widget.submit_api_request(
                channel.post,
                "/json/channel_folders/create",
                data,
                {
                    success_continuation(response_data) {
                        const id = z
                            .object({channel_folder_id: z.number()})
                            .parse(response_data).channel_folder_id;
                        // This is a temporary channel folder object added
                        // to channel folders data, so that the folder is
                        // immediately visible in the dropdown.
                        // This will be replaced with the actual object once
                        // the client receives channel_folder/add event.
                        const channel_folder = {
                            id,
                            name: data.name,
                            description: data.description,
                            is_archived: false,
                            rendered_description: "",
                            date_created: 0,
                            creator_id: people.my_current_user_id(),
                        };
                        channel_folders.add(channel_folder);
                    },
                },
                close_on_success,
            );
        }
        dialog_widget.launch({
            html_heading: $t_html({defaultMessage: "Create channel folder"}),
            html_body,
            id: "create_channel_folder",
            html_submit_button: $t_html({defaultMessage: "Create"}),
            on_click: create_channel_folder,
            loading_spinner: true,
        });
    });
}
