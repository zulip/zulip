import {addDays} from "date-fns";
import Handlebars from "handlebars";
import $ from "jquery";
import assert from "minimalistic-assert";

import render_navbar_banners_testing_popover from "../templates/popovers/navbar_banners_testing_popover.hbs";

import * as banners from "./banners.ts";
import type {AlertBanner} from "./banners.ts";
import * as channel from "./channel.ts";
import * as desktop_notifications from "./desktop_notifications.ts";
import * as feedback_widget from "./feedback_widget.ts";
import {$t, $t_html} from "./i18n.ts";
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
        banners.open(PROFILE_MISSING_REQUIRED_FIELDS_BANNER, $("#navbar_alerts_wrapper"));
    } else if ($banner && $banner.attr("data-process") === "profile-missing-required-fields") {
        banners.close($banner);
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
        banners.close($banner);
        return;
    }
    if (
        is_organization_profile_incomplete() &&
        should_show_organization_profile_incomplete_banner(realm.realm_date_created)
    ) {
        // Note that this will be a noop unless we'd already displayed
        // the notice in this session.  This seems OK, given that
        // this is meant to be a one-time task for administrators.
        banners.open(ORGANIZATION_PROFILE_INCOMPLETE_BANNER, $("#navbar_alerts_wrapper"));
    }
}

export function get_demo_organization_deadline_days_remaining(): number {
    const now = Date.now();
    assert(realm.demo_organization_scheduled_deletion_date !== undefined);
    const deadline = realm.demo_organization_scheduled_deletion_date * 1000;
    const day = 24 * 60 * 60 * 1000; // hours * minutes * seconds * milliseconds
    const days_remaining = Math.round(Math.abs(deadline - now) / day);
    return days_remaining;
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
            type: "primary",
            label: $t({defaultMessage: "Enable notifications"}),
            custom_classes: "request-desktop-notifications",
        },
        {
            type: "quiet",
            label: $t({defaultMessage: "Customize notifications"}),
            custom_classes: "customize-desktop-notifications",
        },
        {
            type: "borderless",
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
            type: "quiet",
            label: $t({defaultMessage: "Configuration instructions"}),
            custom_classes: "configure-outgoing-mail-instructions",
        },
    ],
    close_button: true,
    custom_classes: "navbar-alert-banner",
};

const INSECURE_DESKTOP_APP_BANNER: AlertBanner = {
    process: "insecure-desktop-app",
    intent: "danger",
    label: $t({
        defaultMessage:
            "You are using an old version of the Zulip desktop app with known security bugs.",
    }),
    buttons: [
        {
            type: "quiet",
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
            type: "quiet",
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
            type: "quiet",
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
            type: "quiet",
            label: $t({defaultMessage: "Learn more"}),
            custom_classes: "server-upgrade-learn-more",
        },
        {
            type: "borderless",
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
                type: "quiet",
                label: $t({defaultMessage: "Yes, please!"}),
                custom_classes: "accept-bankruptcy",
            },
            {
                type: "borderless",
                label: $t({defaultMessage: "No, I'll catch up."}),
                custom_classes: "banner-close-action",
            },
        ],
        close_button: true,
        custom_classes: "navbar-alert-banner",
    };
};

const demo_organization_deadline_banner = (): AlertBanner => {
    const days_remaining = get_demo_organization_deadline_days_remaining();
    return {
        process: "demo-organization-deadline",
        intent: days_remaining <= 7 ? "danger" : "info",
        label: new Handlebars.SafeString(
            $t_html(
                {
                    defaultMessage:
                        "This <z-demo-link>demo organization</z-demo-link> will be automatically deleted in {days_remaining} days, unless it's <z-convert-link>converted into a permanent organization</z-convert-link>.",
                },
                {
                    "z-demo-link": (content_html) =>
                        `<a class="banner-link" href="https://zulip.com/help/demo-organizations" target="_blank" rel="noopener noreferrer">${content_html.join("")}</a>`,
                    "z-convert-link": (content_html) =>
                        `<a class="banner-link" href="https://zulip.com/help/demo-organizations#convert-a-demo-organization-to-a-permanent-organization" target="_blank" rel="noopener noreferrer">${content_html.join("")}</a>`,
                    days_remaining,
                },
            ),
        ),
        buttons: [],
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
                type: "quiet",
                label: $t({defaultMessage: "Yes, please!"}),
                custom_classes: "accept-update-time-zone",
            },
            {
                type: "borderless",
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
        banners.open(demo_organization_deadline_banner(), $("#navbar_alerts_wrapper"));
    } else if (page_params.insecure_desktop_app) {
        banners.open(INSECURE_DESKTOP_APP_BANNER, $("#navbar_alerts_wrapper"));
    } else if (should_offer_to_update_timezone()) {
        banners.open(time_zone_update_offer_banner(), $("#navbar_alerts_wrapper"));
    } else if (realm.server_needs_upgrade) {
        if (should_show_server_upgrade_banner(ls)) {
            banners.open(SERVER_NEEDS_UPGRADE_BANNER, $("#navbar_alerts_wrapper"));
        }
    } else if (page_params.warn_no_email === true && current_user.is_admin) {
        // if email has not been set up and the user is the admin,
        // display a warning to tell them to set up an email server.
        banners.open(CONFIGURE_OUTGOING_MAIL_BANNER, $("#navbar_alerts_wrapper"));
    } else if (should_show_desktop_notifications_banner(ls)) {
        banners.open(DESKTOP_NOTIFICATIONS_BANNER, $("#navbar_alerts_wrapper"));
    } else if (should_show_bankruptcy_banner()) {
        banners.open(bankruptcy_banner(), $("#navbar_alerts_wrapper"));
    } else if (
        is_organization_profile_incomplete() &&
        should_show_organization_profile_incomplete_banner(realm.realm_date_created)
    ) {
        banners.open(ORGANIZATION_PROFILE_INCOMPLETE_BANNER, $("#navbar_alerts_wrapper"));
    } else {
        maybe_toggle_empty_required_profile_fields_banner();
    }

    // Configure click handlers.
    $("#navbar_alerts_wrapper").on(
        "click",
        ".request-desktop-notifications",
        function (this: HTMLElement): void {
            void (async () => {
                const $banner = $(this).closest(".banner");
                const permission =
                    await desktop_notifications.request_desktop_notifications_permission();
                if (permission === "granted" || permission === "denied") {
                    banners.close($banner);
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
            banners.close($banner);
            ls.set("dontAskForNotifications", true);
        },
    );

    $("#navbar_alerts_wrapper").on("click", ".accept-bankruptcy", function (this: HTMLElement) {
        const $accept_button = $(this);
        $accept_button.prop("disabled", true).css("pointer-events", "none");
        const $banner = $(this).closest(".banner");
        unread_ops.mark_all_as_read();
        setTimeout(() => {
            banners.close($banner);
        }, 2000);
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
            banners.close($banner);
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
                    banners.close($banner);
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
                    banners.close($banner);
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
                    banners.open(DESKTOP_NOTIFICATIONS_BANNER, $("#navbar_alerts_wrapper"));
                    popover_menus.hide_current_popover_if_visible(instance);
                });
                $popper.on("click", ".configure-outgoing-mail", () => {
                    banners.open(CONFIGURE_OUTGOING_MAIL_BANNER, $("#navbar_alerts_wrapper"));
                    popover_menus.hide_current_popover_if_visible(instance);
                });
                $popper.on("click", ".insecure-desktop-app", () => {
                    banners.open(INSECURE_DESKTOP_APP_BANNER, $("#navbar_alerts_wrapper"));
                    popover_menus.hide_current_popover_if_visible(instance);
                });
                $popper.on("click", ".profile-missing-required-fields", () => {
                    banners.open(
                        PROFILE_MISSING_REQUIRED_FIELDS_BANNER,
                        $("#navbar_alerts_wrapper"),
                    );
                    popover_menus.hide_current_popover_if_visible(instance);
                });
                $popper.on("click", ".organization-profile-incomplete", () => {
                    banners.open(
                        ORGANIZATION_PROFILE_INCOMPLETE_BANNER,
                        $("#navbar_alerts_wrapper"),
                    );
                    popover_menus.hide_current_popover_if_visible(instance);
                });
                $popper.on("click", ".server-needs-upgrade", () => {
                    banners.open(SERVER_NEEDS_UPGRADE_BANNER, $("#navbar_alerts_wrapper"));
                    popover_menus.hide_current_popover_if_visible(instance);
                });
                $popper.on("click", ".bankruptcy", () => {
                    banners.open(bankruptcy_banner(), $("#navbar_alerts_wrapper"));
                    popover_menus.hide_current_popover_if_visible(instance);
                });
                $popper.on("click", ".demo-organization-deadline", () => {
                    realm.demo_organization_scheduled_deletion_date =
                        new Date("2025-01-30T10:00:00.000Z").getTime() / 1000;
                    banners.open(demo_organization_deadline_banner(), $("#navbar_alerts_wrapper"));
                    popover_menus.hide_current_popover_if_visible(instance);
                });
                $popper.on("click", ".time_zone_update_offer", () => {
                    banners.open(time_zone_update_offer_banner(), $("#navbar_alerts_wrapper"));
                    popover_menus.hide_current_popover_if_visible(instance);
                });
            },
            onHidden(instance) {
                instance.destroy();
            },
        });
    });
}
