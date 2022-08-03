import {addDays} from "date-fns";
import $ from "jquery";

import render_bankruptcy_alert_content from "../templates/navbar_alerts/bankruptcy.hbs";
import render_configure_email_alert_content from "../templates/navbar_alerts/configure_outgoing_email.hbs";
import render_demo_organization_deadline_content from "../templates/navbar_alerts/demo_organization_deadline.hbs";
import render_desktop_notifications_alert_content from "../templates/navbar_alerts/desktop_notifications.hbs";
import render_insecure_desktop_app_alert_content from "../templates/navbar_alerts/insecure_desktop_app.hbs";
import render_navbar_alert_wrapper from "../templates/navbar_alerts/navbar_alert_wrapper.hbs";
import render_profile_incomplete_alert_content from "../templates/navbar_alerts/profile_incomplete.hbs";
import render_server_needs_upgrade_alert_content from "../templates/navbar_alerts/server_needs_upgrade.hbs";

import * as compose_ui from "./compose_ui";
import * as keydown_util from "./keydown_util";
import {localstorage} from "./localstorage";
import * as notifications from "./notifications";
import {page_params} from "./page_params";
import {should_display_profile_incomplete_alert} from "./timerender";
import * as unread from "./unread";
import * as unread_ops from "./unread_ops";
import * as unread_ui from "./unread_ui";
import * as util from "./util";

/* This is called by resize.js, and thus indirectly when we trigger
 * resize events in the logic below. */
export function resize_app() {
    const navbar_alerts_height = $("#navbar_alerts_wrapper").height();
    document.documentElement.style.setProperty(
        "--navbar-alerts-wrapper-height",
        navbar_alerts_height + "px",
    );

    // If the compose-box is in expanded state,
    // reset its height as well.
    if (compose_ui.is_full_size()) {
        compose_ui.set_compose_box_top(true);
    }
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
        // Spectators cannot receive desktop notifications, so never
        // request permissions to send them.
        !page_params.is_spectator &&
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
    if (!should_display_profile_incomplete_alert(page_params.realm_date_created)) {
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
        // Note that this will be a noop unless we'd already displayed
        // the notice in this session.  This seems OK, given that
        // this is meant to be a one-time task for administrators.
        $("[data-process='profile-incomplete']").show();
    } else {
        $("[data-process='profile-incomplete']").hide();
    }
}

export function get_demo_organization_deadline_days_remaining() {
    const now = new Date(Date.now());
    const deadline = new Date(page_params.demo_organization_scheduled_deletion_date * 1000);
    const day = 24 * 60 * 60 * 1000; // hours * minutes * seconds * milliseconds
    const days_remaining = Math.round(Math.abs(deadline - now) / day);
    return days_remaining;
}

export function initialize() {
    const ls = localstorage();

    if (page_params.demo_organization_scheduled_deletion_date) {
        const days_remaining = get_demo_organization_deadline_days_remaining();
        open({
            data_process: "demo-organization-deadline",
            custom_class: days_remaining <= 7 ? "red" : "",
            rendered_alert_content_html: render_demo_organization_deadline_content({
                days_remaining,
            }),
        });
    } else if (page_params.insecure_desktop_app) {
        open({
            data_process: "insecure-desktop-app",
            custom_class: "red",
            rendered_alert_content_html: render_insecure_desktop_app_alert_content(),
        });
    } else if (page_params.server_needs_upgrade) {
        if (should_show_server_upgrade_notification(ls)) {
            open({
                data_process: "server-needs-upgrade",
                custom_class: "red",
                rendered_alert_content_html: render_server_needs_upgrade_alert_content(),
            });
        }
    } else if (page_params.warn_no_email === true && page_params.is_admin) {
        // if email has not been set up and the user is the admin,
        // display a warning to tell them to set up an email server.
        open({
            data_process: "email-server",
            custom_class: "red",
            rendered_alert_content_html: render_configure_email_alert_content(),
        });
    } else if (should_show_notifications(ls)) {
        open({
            data_process: "notifications",
            rendered_alert_content_html: render_desktop_notifications_alert_content(),
        });
    } else if (unread_ui.should_display_bankruptcy_banner()) {
        const unread_msgs_count = unread.get_unread_message_count();
        open({
            data_process: "bankruptcy",
            custom_class: "bankruptcy",
            rendered_alert_content_html: render_bankruptcy_alert_content({unread_msgs_count}),
        });
    } else if (check_profile_incomplete()) {
        open({
            data_process: "profile-incomplete",
            rendered_alert_content_html: render_profile_incomplete_alert_content(),
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

    $(".hide-demo-organization-notice").on("click", function () {
        $(this).closest(".alert").hide();
        $(window).trigger("resize");
    });

    $(".accept-bankruptcy").on("click", function (e) {
        e.preventDefault();
        const $process = $(this).closest("[data-process]");
        show_step($process, 2);
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
        if (keydown_util.is_enter_event(e)) {
            $(this).trigger("click");
        }
    });
}

export function open(args) {
    const rendered_alert_wrapper_html = render_navbar_alert_wrapper(args);

    // Note: We only support one alert being rendered at a time; as a
    // result, we just replace the alert area in the DOM with the
    // indicated alert. We do this to avoid bad UX, as it'd look weird
    // to have more than one alert visible at a time.
    $("#navbar_alerts_wrapper").html(rendered_alert_wrapper_html);
    $(window).trigger("resize");
}
