import {addDays} from "date-fns";
import $ from "jquery";

import render_navbar_alert from "../templates/navbar_alert.hbs";

import {$t} from "./i18n";
import {localstorage} from "./localstorage";
import * as notifications from "./notifications";
import {page_params} from "./page_params";
import * as unread_ops from "./unread_ops";
import * as unread_ui from "./unread_ui";
import * as util from "./util";

/* This is called by resize.js, and thus indirectly when we trigger
 * resize events in the logic below. */
export function resize_app() {
    const navbar_alerts_wrapper_height = $("#navbar_alerts_wrapper").height();
    $("body > .app").height("calc(100% - " + navbar_alerts_wrapper_height + "px)");

    // the floating recipient bar is usually positioned right below
    // the `.header` element (including padding).
    const frb_top =
        navbar_alerts_wrapper_height +
        $(".header").height() +
        Number.parseInt($(".header").css("paddingBottom"), 10);
    $("#floating_recipient_bar").css("top", frb_top + "px");
}

const show_step = function ($process, step) {
    $process
        .find("[data-step]")
        .hide()
        .filter("[data-step=" + step + "]")
        .show();
};

const get_step = function ($process) {
    return $process.find("[data-step]:visible").data("step");
};

export function should_show_notifications(ls) {
    // if the user said to never show banner on this computer again, it will
    // be stored as `true` so we want to negate that.
    if (localstorage.supported() && ls.get("dontAskForNotifications") === true) {
        return false;
    }

    return (
        // notifications *basically* don't work on any mobile platforms, so don't
        // event show the banners. This prevents trying to access things that
        // don't exist like `Notification.permission`.
        !util.is_mobile() &&
        // if permission has not been granted yet.
        !notifications.granted_desktop_notifications_permission() &&
        // if permission is allowed to be requested (e.g. not in "denied" state).
        notifications.permission_state() !== "denied"
    );
}

export function should_show_server_upgrade_notification(ls) {
    // We do not show the server upgrade nag for a week after the user
    // clicked "dismiss".
    if (!localstorage.supported() || ls.get("lastUpgradeNagDismissalTime") === undefined) {
        return true;
    }

    const last_notification_dismissal_time = ls.get("lastUpgradeNagDismissalTime");

    const upgrade_nag_dismissal_duration = addDays(new Date(last_notification_dismissal_time), 7);

    // show the notification only if the time duration is completed.
    return Date.now() > upgrade_nag_dismissal_duration;
}

export function dismiss_upgrade_nag(ls) {
    $(".alert[data-process='server-needs-upgrade'").hide();
    if (localstorage.supported()) {
        ls.set("lastUpgradeNagDismissalTime", Date.now());
    }
}

export function check_profile_incomplete() {
    if (!page_params.is_admin) {
        return false;
    }

    // Eventually, we might also check page_params.realm_icon_source,
    // but it feels too aggressive to ask users to do change that
    // since their organization might not have a logo yet.
    if (
        page_params.realm_description === "" ||
        /^Organization imported from [A-Za-z]+[!.]$/.test(page_params.realm_description)
    ) {
        return true;
    }
    return false;
}

export function show_profile_incomplete(is_profile_incomplete) {
    if (is_profile_incomplete) {
        $("[data-process='profile-incomplete']").show();
    } else {
        $("[data-process='profile-incomplete']").hide();
    }
}

function show_notification_alert() {
    open({
        data_process: "notifications",
        is_notification_alert: true,
        second_step_message: $t({
            defaultMessage:
                "We strongly recommend enabling desktop notifications. They help Zulip keep your team connected.",
        }),
        second_step_buttons: [
            {
                class_name: "request-desktop-notifications",
                text: $t({defaultMessage: "Enable notifications"}),
            },
            {
                class_name: "reject-notifications",
                text: $t({defaultMessage: "Never ask on this computer"}),
            },
        ],
    });
}

export function initialize() {
    const ls = localstorage();
    if (page_params.insecure_desktop_app) {
        show_notification_alert();
    } else if (page_params.server_needs_upgrade) {
        if (should_show_server_upgrade_notification(ls)) {
            open({
                data_process: "server-needs-upgrade",
                class_name: "red",
                first_step_message: $t({
                    defaultMessage:
                        "This Zulip server is running an old version and should be upgraded.",
                }),
                first_step_buttons: [
                    {
                        text: $t({defaultMessage: "Learn more"}),
                        link: "https://zulip.readthedocs.io/en/latest/overview/release-lifecycle.html#upgrade-nag",
                    },
                    {
                        class_name: "dismiss-upgrade-nag",
                        text: $t({defaultMessage: "Dismiss for a week"}),
                    },
                ],
            });
        }
    } else if (page_params.warn_no_email === true && page_params.is_admin) {
        // if email has not been set up and the user is the admin,
        // display a warning to tell them to set up an email server.
        open({
            data_process: "email-server",
            class_name: "red",
            first_step_message: $t({
                defaultMessage:
                    "Zulip needs to send email to confirm users' addresses and send notifications.",
            }),
            first_step_buttons: [
                {
                    text: $t({defaultMessage: "See how to configure email."}),
                    link: "https://zulip.readthedocs.io/en/latest/production/email.html",
                },
            ],
        });
    } else if (should_show_notifications(ls)) {
        show_notification_alert();
    } else if (unread_ui.should_display_bankruptcy_banner()) {
        open({
            data_process: "bankruptcy",
            class_name: "bankruptcy",
            is_bankruptcy_alert: true,
            unread_msgs_count: page_params.unread_msgs.count,
            first_step_buttons: [
                {
                    class_name: "accept-bankruptcy",
                    text: $t({defaultMessage: "Yes, please!"}),
                },
                {
                    class_name: "exit",
                    text: $t({defaultMessage: "No, I'll catch up"}),
                },
            ],
        });
    } else if (check_profile_incomplete()) {
        open({
            data_process: "profile-incomplete",
            is_profile_incomplete: true,
        });
    }

    // Configure click handlers.
    $(".request-desktop-notifications").on("click", function (e) {
        e.preventDefault();
        $(this).closest(".alert").hide();
        notifications.request_desktop_notifications_permission();
        $(window).trigger("resize");
    });

    $(".reject-notifications").on("click", function () {
        $(this).closest(".alert").hide();
        ls.set("dontAskForNotifications", true);
        $(window).trigger("resize");
    });

    $(".accept-bankruptcy").on("click", function (e) {
        e.preventDefault();
        $(this).closest(".alert").hide();
        $(".bankruptcy-loader").show();
        setTimeout(unread_ops.mark_all_as_read, 1000);
        $(window).trigger("resize");
    });

    $(".dismiss-upgrade-nag").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        dismiss_upgrade_nag(ls);
    });

    $("#navbar_alerts_wrapper").on("click", ".alert .close, .alert .exit", function (e) {
        e.stopPropagation();
        const $process = $(e.target).closest("[data-process]");
        if (get_step($process) === 1 && $process.data("process") === "notifications") {
            show_step($process, 2);
        } else {
            $(this).closest(".alert").hide();
        }
        $(window).trigger("resize");
    });

    // Treat Enter with links in the navbar alerts UI focused like a click.,
    $("#navbar_alerts_wrapper").on("keyup", ".alert-link[role=button]", function (e) {
        e.stopPropagation();
        if (e.key === "Enter") {
            $(this).trigger("click");
        }
    });
}

export function open(args) {
    const rendered_navbar_alert_html = render_navbar_alert(args);
    $("#navbar_alerts_wrapper").html(rendered_navbar_alert_html);
    $(window).trigger("resize");
}
