import {addDays} from "date-fns";
import $ from "jquery";
import assert from "minimalistic-assert";

import render_navbar_banners_testing_popover from "../templates/popovers/navbar_banners_testing_popover.hbs";

import * as banners from "./banners.ts";
import type {AlertBanner} from "./banners.ts";
import type {ActionButton} from "./buttons.ts";
import * as channel from "./channel.ts";
import * as demo_organizations_ui from "./demo_organizations_ui.ts";
import * as desktop_notifications from "./desktop_notifications.ts";
import * as feedback_widget from "./feedback_widget.ts";
import {$t} from "./i18n.ts";
import type {LocalStorage} from "./localstorage.ts";
import {localstorage} from "./localstorage.ts";
import {page_params} from "./page_params.ts";
import * as people from "./people.ts";
import * as popover_menus from "./popover_menus.ts";
import {current_user, realm} from "./state_data.ts";
import * as time_zone_util from "./time_zone_util.ts";
import * as timerender from "./timerender.ts";
import * as ui_util from "./ui_util.ts";
import * as unread from "./unread.ts";
import * as unread_ops from "./unread_ops.ts";
import {user_settings} from "./user_settings.ts";
import * as util from "./util.ts";

function open_navbar_banner_and_resize(banner: AlertBanner): void {
    banners.open(banner, $("#navbar_alerts_wrapper"));
    // Opening navbar banners requires a resize event to
    // recalculate the navbar-fixed-container height.
    $(window).trigger("resize");
}

function close_navbar_banner_and_resize($banner: JQuery): void {
    banners.close($banner);
    // Closing navbar banners requires a resize event to
    // recalculate the navbar-fixed-container height.
    $(window).trigger("resize");
}

export function should_show_desktop_notifications_banner(ls: LocalStorage): boolean {
    // if the user said to never show banner on this computer again, it will
    // be stored as `true` so we want to negate that.
    if (localstorage.supported() && ls.get("dontAskForNotifications") === true) {
        return false;
    }

    return (
        // Spectators cannot receive desktop notifications, so never
        // request permissions to send them.
        !page_params.is_spectator &&
        // notifications *basically* don't work on any mobile platforms, so don't
        // event show the banners. This prevents trying to access things that
        // don't exist like `Notification.permission`.
        !util.is_mobile() &&
        // if permission has not been granted yet.
        !desktop_notifications.granted_desktop_notifications_permission() &&
        // if permission is allowed to be requested (e.g. not in "denied" state).
        desktop_notifications.permission_state() !== "denied"
    );
}

export function should_show_bankruptcy_banner(): boolean {
    // Until we've handled possibly declaring bankruptcy, don't show
    // unread counts since they only consider messages that are loaded
    // client side and may be different from the numbers reported by
    // the server.

    if (!page_params.furthest_read_time) {
        // We've never read a message.
        return false;
    }

    const now = Date.now() / 1000;
    if (
        unread.get_unread_message_count() > 500 &&
        now - page_params.furthest_read_time > 60 * 60 * 24 * 2
    ) {
        // 2 days.
        return true;
    }

    return false;
}

export function should_show_server_upgrade_banner(ls: LocalStorage): boolean {
    // We do not show the server upgrade nag for a week after the user
    // clicked "dismiss".
    if (!localstorage.supported() || ls.get("lastUpgradeNagDismissalTime") === undefined) {
        return true;
    }
    const last_notification_dismissal_time = ls.get("lastUpgradeNagDismissalTime");
    assert(typeof last_notification_dismissal_time === "number");

    const upgrade_nag_dismissal_duration = addDays(
        new Date(last_notification_dismissal_time),
        7,
    ).getTime();

    // show the notification only if the time duration is completed.
    return Date.now() > upgrade_nag_dismissal_duration;
}

export function maybe_toggle_empty_required_profile_fields_banner(): void {
    const $banner = $("#navbar_alerts_wrapper").find(".banner");
    const empty_required_profile_fields_exist = realm.custom_profile_fields
        .map((f) => ({
            ...f,
            value: people.my_custom_profile_data(f.id)?.value,
        }))
        .find((f) => f.required && !f.value);
    if (empty_required_profile_fields_exist) {
        open_navbar_banner_and_resize(PROFILE_MISSING_REQUIRED_FIELDS_BANNER);
    } else if ($banner && $banner.attr("data-process") === "profile-missing-required-fields") {
        close_navbar_banner_and_resize($banner);
    }
}

export function set_last_upgrade_nag_dismissal_time(ls: LocalStorage): void {
    if (localstorage.supported()) {
        ls.set("lastUpgradeNagDismissalTime", Date.now());
    }
}

export function should_show_organization_profile_incomplete_banner(timestamp: number): boolean {
    if (!current_user.is_admin) {
        return false;
    }

    const today = new Date(Date.now());
    const time = new Date(timestamp * 1000);
    const days_old = time_zone_util.difference_in_calendar_days(
        today,
        time,
        timerender.display_time_zone,
    );

    if (days_old >= 15) {
        return true;
    }
    return false;
}

export function is_organization_profile_incomplete(): boolean {
    // Eventually, we might also check realm.realm_icon_source,
    // but it feels too aggressive to ask users to do change that
    // since their organization might not have a logo yet.
    if (
        realm.realm_description === "" ||
        /^Organization imported from [A-Za-z]+[!.]$/.test(realm.realm_description)
    ) {
        return true;
    }
    return false;
}

export function toggle_organization_profile_incomplete_banner(): void {
    const $banner = $("#navbar_alerts_wrapper").find(".banner");
    if ($banner && $banner.attr("data-process") === "organization-profile-incomplete") {
        close_navbar_banner_and_resize($banner);
        return;
    }
    if (
        is_organization_profile_incomplete() &&
        should_show_organization_profile_incomplete_banner(realm.realm_date_created)
    ) {
        // Note that this will be a noop unless we'd already displayed
        // the notice in this session.  This seems OK, given that
        // this is meant to be a one-time task for administrators.
        open_navbar_banner_and_resize(ORGANIZATION_PROFILE_INCOMPLETE_BANNER);
    }
}

export function should_offer_to_update_timezone(): boolean {
    // This offer is only for logged-in users with the setting enabled.
    return (
        !page_params.is_spectator &&
        user_settings.web_suggest_update_timezone &&
        !timerender.is_browser_timezone_same_as(user_settings.timezone)
    );
}

const DESKTOP_NOTIFICATIONS_BANNER: AlertBanner = {
    process: "desktop-notifications",
    intent: "brand",
    label: $t({
        defaultMessage:
            "Zulip needs your permission to enable desktop notifications for important messages.",
    }),
    buttons: [
        {
            attention: "primary",
            label: $t({defaultMessage: "Enable notifications"}),
            custom_classes: "request-desktop-notifications",
        },
        {
            attention: "quiet",
            label: $t({defaultMessage: "Customize notifications"}),
            custom_classes: "customize-desktop-notifications",
        },
        {
            attention: "borderless",
            label: $t({defaultMessage: "Never ask on this computer"}),
            custom_classes: "reject-desktop-notifications",
        },
    ],
    close_button: true,
    custom_classes: "navbar-alert-banner",
};

const CONFIGURE_OUTGOING_MAIL_BANNER: AlertBanner = {
    process: "configure-outgoing-mail",
    intent: "warning",
    label: $t({
        defaultMessage:
            "Zulip needs to send email to confirm users' addresses and send notifications.",
    }),
    buttons: [
        {
            attention: "quiet",
            label: $t({defaultMessage: "Configuration instructions"}),
            custom_classes: "configure-outgoing-mail-instructions",
        },
    ],
    close_button: true,
    custom_classes: "navbar-alert-banner",
};

const INSECURE_DESKTOP_APP_BANNER: AlertBanner = {
    process: "insecure-desktop-app",
    intent: "warning",
    label: $t({
        defaultMessage:
            "Zulip desktop is not updating automatically. Please upgrade for security updates and other improvements.",
    }),
    buttons: [
        {
            attention: "quiet",
            label: $t({defaultMessage: "Download the latest version"}),
            custom_classes: "download-latest-zulip-version",
        },
    ],
    close_button: true,
    custom_classes: "navbar-alert-banner",
};

const PROFILE_MISSING_REQUIRED_FIELDS_BANNER: AlertBanner = {
    process: "profile-missing-required-fields",
    intent: "warning",
    label: $t({defaultMessage: "Your profile is missing required fields."}),
    buttons: [
        {
            attention: "quiet",
            label: $t({defaultMessage: "Edit your profile"}),
            custom_classes: "edit-profile-required-fields",
        },
    ],
    close_button: true,
    custom_classes: "navbar-alert-banner",
};

const ORGANIZATION_PROFILE_INCOMPLETE_BANNER: AlertBanner = {
    process: "organization-profile-incomplete",
    intent: "info",
    label: $t({
        defaultMessage:
            "Complete your organization profile, which is displayed on your organization's registration and login pages.",
    }),
    buttons: [
        {
            attention: "quiet",
            label: $t({
                defaultMessage: "Edit profile",
            }),
            custom_classes: "edit-organization-profile",
        },
    ],
    close_button: true,
    custom_classes: "navbar-alert-banner",
};

const SERVER_NEEDS_UPGRADE_BANNER: AlertBanner = {
    process: "server-needs-upgrade",
    intent: "danger",
    label: $t({
        defaultMessage: "This Zulip server is running an old version and should be upgraded.",
    }),
    buttons: [
        {
            attention: "quiet",
            label: $t({defaultMessage: "Learn more"}),
            custom_classes: "server-upgrade-learn-more",
        },
        {
            attention: "borderless",
            label: $t({defaultMessage: "Dismiss for a week"}),
            custom_classes: "server-upgrade-nag-dismiss",
        },
    ],
    close_button: true,
    custom_classes: "navbar-alert-banner",
};

const bankruptcy_banner = (): AlertBanner => {
    const old_unreads_missing = unread.old_unreads_missing;
    const unread_msgs_count = unread.get_unread_message_count();
    let label = "";
    if (old_unreads_missing) {
        label = $t(
            {
                defaultMessage:
                    "Welcome back! You have at least {unread_msgs_count} unread messages. Do you want to mark them all as read?",
            },
            {
                unread_msgs_count,
            },
        );
    } else {
        label = $t(
            {
                defaultMessage:
                    "Welcome back! You have {unread_msgs_count} unread messages. Do you want to mark them all as read?",
            },
            {
                unread_msgs_count,
            },
        );
    }
    return {
        process: "bankruptcy",
        intent: "info",
        label,
        buttons: [
            {
                attention: "quiet",
                label: $t({defaultMessage: "Yes, please!"}),
                custom_classes: "accept-bankruptcy",
            },
            {
                attention: "borderless",
                label: $t({defaultMessage: "No, I'll catch up."}),
                custom_classes: "banner-close-action",
            },
        ],
        close_button: true,
        custom_classes: "navbar-alert-banner",
    };
};

const demo_organization_deadline_banner = (): AlertBanner => {
    const days_remaining = demo_organizations_ui.get_demo_organization_deadline_days_remaining();
    let buttons: ActionButton[] = [
        {
            attention: "borderless",
            label: $t({defaultMessage: "Learn more"}),
            custom_classes: "demo-organizations-help",
        },
    ];
    if (current_user.is_owner) {
        buttons = [
            ...buttons,
            {
                attention: "quiet",
                label: $t({defaultMessage: "Convert"}),
                custom_classes: "convert-demo-organization",
            },
        ];
    }
    return {
        process: "demo-organization-deadline",
        intent: days_remaining <= 7 ? "danger" : "info",
        label: $t(
            {
                defaultMessage:
                    "This demo organization will be automatically deleted in {days_remaining} days, unless it's converted into a permanent organization.",
            },
            {
                days_remaining,
            },
        ),
        buttons,
        close_button: true,
        custom_classes: "navbar-alert-banner",
    };
};

const time_zone_update_offer_banner = (): AlertBanner => {
    const browser_time_zone = timerender.browser_time_zone();
    return {
        process: "time_zone_update_offer",
        intent: "info",
        label: $t(
            {
                defaultMessage:
                    "Your computer's time zone differs from your Zulip profile. Update your time zone to {browser_time_zone}?",
            },
            {
                browser_time_zone,
            },
        ),
        buttons: [
            {
                attention: "quiet",
                label: $t({defaultMessage: "Yes, please!"}),
                custom_classes: "accept-update-time-zone",
            },
            {
                attention: "borderless",
                label: $t({defaultMessage: "No, don't ask again."}),
                custom_classes: "decline-time-zone-update",
            },
        ],
        close_button: true,
        custom_classes: "navbar-alert-banner",
    };
};

export function initialize(): void {
    const ls = localstorage();
    const browser_time_zone = timerender.browser_time_zone();
    if (realm.demo_organization_scheduled_deletion_date) {
        open_navbar_banner_and_resize(demo_organization_deadline_banner());
    } else if (page_params.insecure_desktop_app) {
        open_navbar_banner_and_resize(INSECURE_DESKTOP_APP_BANNER);
    } else if (should_offer_to_update_timezone()) {
        open_navbar_banner_and_resize(time_zone_update_offer_banner());
    } else if (realm.server_needs_upgrade) {
        if (should_show_server_upgrade_banner(ls)) {
            open_navbar_banner_and_resize(SERVER_NEEDS_UPGRADE_BANNER);
        }
    } else if (page_params.warn_no_email === true && current_user.is_admin) {
        // if email has not been set up and the user is the admin,
        // display a warning to tell them to set up an email server.
        open_navbar_banner_and_resize(CONFIGURE_OUTGOING_MAIL_BANNER);
    } else if (should_show_desktop_notifications_banner(ls)) {
        open_navbar_banner_and_resize(DESKTOP_NOTIFICATIONS_BANNER);
    } else if (should_show_bankruptcy_banner()) {
        open_navbar_banner_and_resize(bankruptcy_banner());
    } else if (
        is_organization_profile_incomplete() &&
        should_show_organization_profile_incomplete_banner(realm.realm_date_created)
    ) {
        open_navbar_banner_and_resize(ORGANIZATION_PROFILE_INCOMPLETE_BANNER);
    } else {
        maybe_toggle_empty_required_profile_fields_banner();
    }

    // Configure click handlers.

    $("#navbar_alerts_wrapper").on(
        "click",
        ".banner-close-action",
        function (this: HTMLElement, e) {
            // Override the banner close event listener in web/src/banners.ts,
            // to trigger a window resize event which is necessary to
            // recalculate the navbar-fixed-container height.
            e.preventDefault();
            e.stopPropagation();
            const $banner = $(this).closest(".banner");
            banners.close($banner);
            $(window).trigger("resize");
        },
    );

    $("#navbar_alerts_wrapper").on(
        "click",
        ".request-desktop-notifications",
        function (this: HTMLElement): void {
            void (async () => {
                const $banner = $(this).closest(".banner");
                const permission =
                    await desktop_notifications.request_desktop_notifications_permission();
                if (permission === "granted" || permission === "denied") {
                    close_navbar_banner_and_resize($banner);
                }
            })();
        },
    );

    $("#navbar_alerts_wrapper").on("click", ".customize-desktop-notifications", () => {
        window.location.hash = "#settings/notifications";
    });

    $("#navbar_alerts_wrapper").on(
        "click",
        ".reject-desktop-notifications",
        function (this: HTMLElement) {
            const $banner = $(this).closest(".banner");
            close_navbar_banner_and_resize($banner);
            ls.set("dontAskForNotifications", true);
        },
    );

    $("#navbar_alerts_wrapper").on("click", ".accept-bankruptcy", function (this: HTMLElement) {
        const $accept_button = $(this);
        $accept_button.prop("disabled", true).css("pointer-events", "none");
        const $banner = $(this).closest(".banner");
        unread_ops.mark_all_as_read();
        setTimeout(() => {
            close_navbar_banner_and_resize($banner);
        }, 2000);
    });

    $("#navbar_alerts_wrapper").on("click", ".convert-demo-organization", (e) => {
        e.stopPropagation();
        e.preventDefault();
        demo_organizations_ui.show_convert_demo_organization_modal();
    });

    $("#navbar_alerts_wrapper").on("click", ".demo-organizations-help", () => {
        window.open("https://zulip.com/help/demo-organizations", "_blank", "noopener,noreferrer");
    });

    $("#navbar_alerts_wrapper").on("click", ".configure-outgoing-mail-instructions", () => {
        window.open(
            "https://zulip.readthedocs.io/en/latest/production/email.html",
            "_blank",
            "noopener,noreferrer",
        );
    });

    $("#navbar_alerts_wrapper").on("click", ".download-latest-zulip-version", () => {
        window.open("https://zulip.com/download", "_blank", "noopener,noreferrer");
    });

    $("#navbar_alerts_wrapper").on("click", ".edit-profile-required-fields", () => {
        window.location.hash = "#settings/profile";
    });

    $("#navbar_alerts_wrapper").on("click", ".edit-organization-profile", () => {
        window.location.hash = "#organization/organization-profile";
    });

    $("#navbar_alerts_wrapper").on("click", ".server-upgrade-learn-more", () => {
        window.open(
            "https://zulip.readthedocs.io/en/latest/overview/release-lifecycle.html#upgrade-nag",
            "_blank",
            "noopener,noreferrer",
        );
    });

    $("#navbar_alerts_wrapper").on(
        "click",
        ".server-upgrade-nag-dismiss",
        function (this: HTMLElement) {
            const $banner = $(this).closest(".banner");
            close_navbar_banner_and_resize($banner);
            set_last_upgrade_nag_dismissal_time(ls);
        },
    );

    $("#navbar_alerts_wrapper").on(
        "click",
        ".accept-update-time-zone",
        function (this: HTMLElement) {
            const $banner = $(this).closest(".banner");
            void channel.patch({
                url: "/json/settings",
                data: {timezone: browser_time_zone},
                success() {
                    close_navbar_banner_and_resize($banner);
                    feedback_widget.show({
                        title_text: $t({defaultMessage: "Time zone updated"}),
                        populate($container) {
                            $container.text(
                                $t(
                                    {
                                        defaultMessage:
                                            "Your time zone was updated to {time_zone}.",
                                    },
                                    {time_zone: browser_time_zone},
                                ),
                            );
                        },
                    });
                },
                error() {
                    feedback_widget.show({
                        title_text: $t({defaultMessage: "Could not update time zone"}),
                        populate($container) {
                            $container.text(
                                $t({defaultMessage: "Unexpected error updating the timezone."}),
                            );
                        },
                    });
                },
            });
        },
    );

    $("#navbar_alerts_wrapper").on(
        "click",
        ".decline-time-zone-update",
        function (this: HTMLElement) {
            const $banner = $(this).closest(".banner");
            void channel.patch({
                url: "/json/settings",
                data: {web_suggest_update_timezone: false},
                success() {
                    close_navbar_banner_and_resize($banner);
                    feedback_widget.show({
                        title_text: $t({defaultMessage: "Setting updated"}),
                        populate($container) {
                            $container.text(
                                $t({
                                    defaultMessage:
                                        "You will no longer be prompted to update your time zone.",
                                }),
                            );
                        },
                    });
                },
                error() {
                    feedback_widget.show({
                        title_text: $t({defaultMessage: "Unable to update setting"}),
                        populate($container) {
                            $container.text(
                                $t({defaultMessage: "There was an error updating the setting."}),
                            );
                        },
                    });
                },
            });
        },
    );

    $("body").on("click", ".top_left_change_navbar_banners", function (this: HTMLElement) {
        popover_menus.toggle_popover_menu(this, {
            theme: "popover-menu",
            placement: "right",
            popperOptions: {
                modifiers: [
                    {
                        name: "flip",
                        options: {
                            fallbackPlacements: ["bottom", "left"],
                        },
                    },
                ],
            },
            onShow(instance) {
                instance.setContent(ui_util.parse_html(render_navbar_banners_testing_popover()));
            },
            onMount(instance) {
                const $popper = $(instance.popper);
                $popper.on("click", ".desktop-notifications", () => {
                    open_navbar_banner_and_resize(DESKTOP_NOTIFICATIONS_BANNER);
                    popover_menus.hide_current_popover_if_visible(instance);
                });
                $popper.on("click", ".configure-outgoing-mail", () => {
                    open_navbar_banner_and_resize(CONFIGURE_OUTGOING_MAIL_BANNER);
                    popover_menus.hide_current_popover_if_visible(instance);
                });
                $popper.on("click", ".insecure-desktop-app", () => {
                    open_navbar_banner_and_resize(INSECURE_DESKTOP_APP_BANNER);
                    popover_menus.hide_current_popover_if_visible(instance);
                });
                $popper.on("click", ".profile-missing-required-fields", () => {
                    open_navbar_banner_and_resize(PROFILE_MISSING_REQUIRED_FIELDS_BANNER);
                    popover_menus.hide_current_popover_if_visible(instance);
                });
                $popper.on("click", ".organization-profile-incomplete", () => {
                    open_navbar_banner_and_resize(ORGANIZATION_PROFILE_INCOMPLETE_BANNER);
                    popover_menus.hide_current_popover_if_visible(instance);
                });
                $popper.on("click", ".server-needs-upgrade", () => {
                    open_navbar_banner_and_resize(SERVER_NEEDS_UPGRADE_BANNER);
                    popover_menus.hide_current_popover_if_visible(instance);
                });
                $popper.on("click", ".bankruptcy", () => {
                    open_navbar_banner_and_resize(bankruptcy_banner());
                    popover_menus.hide_current_popover_if_visible(instance);
                });
                $popper.on("click", ".demo-organization-deadline", () => {
                    realm.demo_organization_scheduled_deletion_date =
                        new Date("2025-01-30T10:00:00.000Z").getTime() / 1000;
                    open_navbar_banner_and_resize(demo_organization_deadline_banner());
                    popover_menus.hide_current_popover_if_visible(instance);
                });
                $popper.on("click", ".time_zone_update_offer", () => {
                    open_navbar_banner_and_resize(time_zone_update_offer_banner());
                    popover_menus.hide_current_popover_if_visible(instance);
                });
            },
            onHidden(instance) {
                instance.destroy();
            },
        });
    });
}
