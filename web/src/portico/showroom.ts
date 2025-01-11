import Handlebars from "handlebars/runtime.js";
import $ from "jquery";

import render_banner from "../../templates/components/banner.hbs";
import {$t, $t_html} from "../i18n.ts";

type ComponentIntent = "neutral" | "brand" | "info" | "success" | "warning" | "danger";

type ActionButton = {
    type: "primary" | "quiet" | "borderless";
    intent: ComponentIntent;
    label: string;
    icon?: string | undefined;
};

type Banner = {
    intent: ComponentIntent;
    label: string | Handlebars.SafeString;
    buttons: ActionButton[];
    close_button: boolean;
    custom_classes?: string;
};

type AlertBanner = Banner & {
    process: string;
};

const component_intents: ComponentIntent[] = [
    "neutral",
    "brand",
    "info",
    "success",
    "warning",
    "danger",
];

const banner_html = (banner: Banner | AlertBanner): string => render_banner(banner);

const custom_normal_banner: Banner = {
    intent: "neutral",
    label: "This is a normal banner. Use the controls below to modify this banner.",
    buttons: [
        {
            type: "quiet",
            intent: "neutral",
            label: "Quiet Button",
        },
    ],
    close_button: true,
};

const alert_banners: Record<string, AlertBanner> = {
    "custom-banner": {
        process: "custom-banner",
        intent: "neutral",
        label: "This is a navbar alerts banner. Use the controls below to modify this banner.",
        buttons: [
            {
                type: "quiet",
                intent: "neutral",
                label: "Quiet Button",
            },
        ],
        close_button: true,
        custom_classes: "navbar-alert-banner",
    },
    bankruptcy: {
        process: "bankruptcy",
        intent: "info",
        label: "Welcome back! You have 12 unread messages. Do you want to mark them all as read?",
        buttons: [
            {
                type: "quiet",
                intent: "info",
                label: "Yes, please!",
            },
            {
                type: "borderless",
                intent: "info",
                label: "No, I'll catch up.",
            },
        ],
        close_button: true,
        custom_classes: "navbar-alert-banner",
    },
    "email-server": {
        process: "email-server",
        intent: "warning",
        label: "Zulip needs to send email to confirm users' addresses and send notifications.",
        buttons: [
            {
                type: "quiet",
                intent: "warning",
                label: "Configuration instructions",
            },
        ],
        close_button: true,
        custom_classes: "navbar-alert-banner",
    },
    "demo-organization-deadline": {
        process: "demo-organization-deadline",
        intent: "info",
        label: new Handlebars.SafeString(
            $t_html(
                {
                    defaultMessage:
                        "This <demo_link>demo organization</demo_link> will be automatically deleted in 30 days, unless it's <convert_link>converted into a permanent organization</convert_link>.",
                },
                {
                    demo_link: (content_html) =>
                        `<a class="banner__link" href="https://zulip.com/help/demo-organizations" target="_blank" rel="noopener noreferrer">${content_html.join("")}</a>`,
                    convert_link: (content_html) =>
                        `<a class="banner__link" href="https://zulip.com/help/demo-organizations#convert-a-demo-organization-to-a-permanent-organization" target="_blank" rel="noopener noreferrer">${content_html.join("")}</a>`,
                },
            ),
        ),
        buttons: [],
        close_button: true,
        custom_classes: "navbar-alert-banner",
    },
    notifications: {
        process: "notifications",
        intent: "brand",
        label: new Handlebars.SafeString(
            $t_html(
                {
                    defaultMessage:
                        "Zulip needs your permission to enable desktop notifications for messages you receive. You can <z-link>customize</z-link> what kinds of messages trigger notifications.",
                },
                {
                    "z-link": (content_html) =>
                        `<a class="banner__link" href="https://zulip.com/help/desktop-notifications#desktop-notifications" target="_blank" rel="noopener noreferrer">${content_html.join("")}</a>`,
                },
            ),
        ),
        buttons: [
            {
                type: "primary",
                intent: "brand",
                label: "Enable notifications",
            },
            {
                type: "quiet",
                intent: "brand",
                label: "Ask me later",
            },
            {
                type: "borderless",
                intent: "brand",
                label: "Never ask on this computer",
            },
        ],
        close_button: true,
        custom_classes: "navbar-alert-banner",
    },
    "profile-missing-required": {
        process: "profile-missing-required",
        intent: "warning",
        label: "Your profile is missing required fields.",
        buttons: [
            {
                type: "quiet",
                intent: "warning",
                label: "Edit your profile",
            },
        ],
        close_button: true,
        custom_classes: "navbar-alert-banner",
    },
    "insecure-desktop-app": {
        process: "insecure-desktop-app",
        intent: "danger",
        label: "You are using an old version of the Zulip desktop app with known security bugs.",
        buttons: [
            {
                type: "quiet",
                intent: "danger",
                label: "Download the latest version",
            },
        ],
        close_button: true,
        custom_classes: "navbar-alert-banner",
    },
    "profile-incomplete": {
        process: "profile-incomplete",
        intent: "info",
        label: "Complete your organization profile, which is displayed on your organization's registration and login pages.",
        buttons: [
            {
                type: "quiet",
                intent: "info",
                label: "Edit profile",
            },
        ],
        close_button: true,
        custom_classes: "navbar-alert-banner",
    },
    "server-needs-upgrade": {
        process: "server-needs-upgrade",
        intent: "danger",
        label: "This Zulip server is running an old version and should be upgraded.",
        buttons: [
            {
                type: "quiet",
                intent: "danger",
                label: "Learn more",
            },
            {
                type: "borderless",
                intent: "danger",
                label: "Dismiss for a week",
            },
        ],
        close_button: true,
        custom_classes: "navbar-alert-banner",
    },
};

const sortButtons = (buttons: ActionButton[]): void => {
    const sortOrder: Record<ActionButton["type"], number> = {
        primary: 1,
        quiet: 2,
        borderless: 3,
    };

    buttons.sort((a, b) => sortOrder[a.type] - sortOrder[b.type]);
};

const update_buttons = (buttons: ActionButton[]): void => {
    const primary_button = buttons.find((button) => button.type === "primary");
    if (primary_button) {
        $("#enable_primary_button").prop("checked", true);
        $("#primary_button_text").val(primary_button.label);
        if (primary_button.icon) {
            $("#primary_button_select_icon").val(primary_button.icon);
            $("#enable_primary_button_icon").prop("checked", true);
        } else {
            $("#disable_primary_button_icon").prop("checked", true);
        }
    } else {
        $("#disable_primary_button").prop("checked", true);
        $("#primary_button_text").val("");
        $("#disable_primary_button_icon").prop("checked", true);
    }
    const quiet_button = buttons.find((button) => button.type === "quiet");
    if (quiet_button) {
        $("#enable_quiet_button").prop("checked", true);
        $("#quiet_button_text").val(quiet_button.label);
        if (quiet_button.icon) {
            $("#quiet_button_select_icon").val(quiet_button.icon);
            $("#enable_quiet_button_icon").prop("checked", true);
        } else {
            $("#disable_quiet_button_icon").prop("checked", true);
        }
    } else {
        $("#disable_quiet_button").prop("checked", true);
        $("#quiet_button_text").val("");
        $("#disable_quiet_button_icon").prop("checked", true);
    }
    const borderless_button = buttons.find((button) => button.type === "borderless");
    if (borderless_button) {
        $("#enable_borderless_button").prop("checked", true);
        $("#borderless_button_text").val(borderless_button.label);
        if (borderless_button.icon) {
            $("#borderless_button_select_icon").val(borderless_button.icon);
            $("#enable_borderless_button_icon").prop("checked", true);
        } else {
            $("#disable_borderless_button_icon").prop("checked", true);
        }
    } else {
        $("#disable_borderless_button").prop("checked", true);
        $("#borderless_button_text").val("");
        $("#disable_borderless_button_icon").prop("checked", true);
    }
};

function update_banner(): void {
    $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
    $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));

    $("#showroom_component_banner_select_intent").val(current_banner.intent);
    $("#banner_label").val(current_banner.label.toString());
    update_buttons(current_banner.buttons);
    if (current_banner.close_button) {
        $("#enable_banner_close_button").prop("checked", true);
    } else {
        $("#disable_banner_close_button").prop("checked", true);
    }
}

let current_banner = alert_banners["custom-banner"]!;

$(window).on("load", () => {
    // Code for /devtools/buttons design testing page.
    $("input[name='showroom-dark-theme-select']").on("change", (e) => {
        if ($(e.target).data("theme") === "dark") {
            $(":root").addClass("dark-theme");
        } else {
            $(":root").removeClass("dark-theme");
        }
    });

    $("input[name='button-icon-select']").on("change", (e) => {
        if ($(e.target).attr("id") === "enable_button_icon") {
            $(".action-button .zulip-icon").removeClass("hidden");
        } else {
            $(".action-button .zulip-icon").addClass("hidden");
        }
    });

    $("#button_text").on("input", function (this: HTMLElement) {
        const button_text = $(this).val()?.toString() ?? "";
        $(".action-button-label").text(button_text);
    });

    $("#clear_button_text").on("click", () => {
        $("#button_text").val("");
        $(".action-button-label").text($t({defaultMessage: "Button joy"}));
    });

    $("#button_select_icon").on("change", function (this: HTMLElement) {
        const icon_name = $(this).val()?.toString() ?? "";
        $(".action-button .zulip-icon, .icon-button .zulip-icon").attr(
            "class",
            (_index, className) =>
                className.replaceAll(/zulip-icon-[^\s]+/g, `zulip-icon-${icon_name}`),
        );
    });

    $(".select_background").on("change", function (this: HTMLElement) {
        const background_var = $(this).val()?.toString() ?? "";
        $("body").css("background-color", `var(${background_var})`);
    });

    // Code for /devtools/banners design testing page.
    update_banner();

    // Populate banner type select options
    const $banner_select = $("#banner_select_type");
    for (const key of Object.keys(alert_banners)) {
        $banner_select.append($("<option>").val(key).text(key));
    }

    const $banner_intent_select = $("#showroom_component_banner_select_intent");
    for (const intent of component_intents) {
        $banner_intent_select.append($("<option>").val(intent).text(intent));
    }

    $("#showroom_component_banner_select_intent").on("change", function (this: HTMLElement) {
        const selected_intent = $(this).val()?.toString();
        if (selected_intent === undefined) {
            return;
        }
        current_banner.intent =
            component_intents.find((intent) => intent === selected_intent) ?? "neutral";
        for (const button of current_banner.buttons) {
            button.intent = current_banner.intent;
        }
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.intent = current_banner.intent;
            for (const button of custom_normal_banner.buttons) {
                button.intent = custom_normal_banner.intent;
            }
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
    });

    $banner_select.on("change", function (this: HTMLElement) {
        const banner_type = $(this).val()?.toString();
        if (banner_type === undefined) {
            return;
        }
        current_banner = alert_banners[banner_type]!;
        update_banner();
    });

    $("input[name='banner-close-button-select']").on("change", (e) => {
        if ($(e.target).attr("id") === "enable_banner_close_button") {
            current_banner.close_button = true;
        } else {
            current_banner.close_button = false;
        }
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.close_button = current_banner.close_button;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $("#banner_label").on("input", function (this: HTMLElement) {
        const banner_label = $(this).val()?.toString() ?? "";
        current_banner.label = banner_label;
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.label = banner_label;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $("input[name='primary-button-select']").on("change", (e) => {
        if ($(e.target).attr("id") === "enable_primary_button") {
            if (current_banner.buttons.some((button) => button.type === "primary")) {
                return;
            }
            let label = $("#primary_button_text").val()?.toString();
            if (!label) {
                label = "Primary Button";
            }
            const is_icon_enabled = $("#enable_primary_button_icon").prop("checked") === true;
            current_banner.buttons.push({
                type: "primary",
                intent: current_banner.intent,
                label,
                icon: is_icon_enabled
                    ? $("#primary_button_select_icon").val()?.toString()
                    : undefined,
            });
            $("#primary_button_text").val(label);
        } else {
            current_banner.buttons = current_banner.buttons.filter(
                (button) => button.type !== "primary",
            );
        }
        sortButtons(current_banner.buttons);
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.buttons = current_banner.buttons;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $("input[name='primary-button-icon-select']").on("change", (e) => {
        const primary_button = current_banner.buttons.find((button) => button.type === "primary");
        if (primary_button === undefined) {
            return;
        }
        if ($(e.target).attr("id") === "enable_primary_button_icon") {
            primary_button.icon = $("#primary_button_select_icon").val()?.toString() ?? "";
        } else {
            delete primary_button.icon;
        }
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.buttons = current_banner.buttons;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $("#primary_button_select_icon").on("change", function (this: HTMLElement) {
        const primary_button = current_banner.buttons.find((button) => button.type === "primary");
        if (primary_button === undefined) {
            return;
        }
        if (!primary_button.icon) {
            return;
        }
        primary_button.icon = $(this).val()?.toString() ?? "";
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.buttons = current_banner.buttons;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $("#primary_button_text").on("input", function (this: HTMLElement) {
        const primary_button = current_banner.buttons.find((button) => button.type === "primary");
        if (primary_button === undefined) {
            return;
        }
        primary_button.label = $(this).val()?.toString() ?? "";
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.buttons = current_banner.buttons;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $("input[name='quiet-button-select']").on("change", (e) => {
        if ($(e.target).attr("id") === "enable_quiet_button") {
            if (current_banner.buttons.some((button) => button.type === "quiet")) {
                return;
            }
            let label = $("#quiet_button_text").val()?.toString();
            if (!label) {
                label = "Quiet Button";
            }
            const is_icon_enabled = $("#enable_quiet_button_icon").prop("checked") === true;
            current_banner.buttons.push({
                type: "quiet",
                intent: current_banner.intent,
                label,
                icon: is_icon_enabled
                    ? $("#quiet_button_select_icon").val()?.toString()
                    : undefined,
            });
            $("#quiet_button_text").val(label);
            sortButtons(current_banner.buttons);
        } else {
            current_banner.buttons = current_banner.buttons.filter(
                (button) => button.type !== "quiet",
            );
        }
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.buttons = current_banner.buttons;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $("input[name='quiet-button-icon-select']").on("change", (e) => {
        const quiet_button = current_banner.buttons.find((button) => button.type === "quiet");
        if (quiet_button === undefined) {
            return;
        }
        if ($(e.target).attr("id") === "enable_quiet_button_icon") {
            quiet_button.icon = $("#quiet_button_select_icon").val()?.toString() ?? "";
        } else {
            delete quiet_button.icon;
        }
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.buttons = current_banner.buttons;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $("#quiet_button_select_icon").on("change", function (this: HTMLElement) {
        const quiet_button = current_banner.buttons.find((button) => button.type === "quiet");
        if (quiet_button === undefined) {
            return;
        }
        if (!quiet_button.icon) {
            return;
        }
        quiet_button.icon = $(this).val()?.toString() ?? "";
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.buttons = current_banner.buttons;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $("#quiet_button_text").on("input", function (this: HTMLElement) {
        const quiet_button = current_banner.buttons.find((button) => button.type === "quiet");
        if (quiet_button === undefined) {
            return;
        }
        quiet_button.label = $(this).val()?.toString() ?? "";
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.buttons = current_banner.buttons;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $("input[name='borderless-button-select']").on("change", function (this: HTMLElement) {
        if ($(this).attr("id") === "enable_borderless_button") {
            if (current_banner.buttons.some((button) => button.type === "borderless")) {
                return;
            }
            let label = $("#borderless_button_text").val()?.toString();
            if (!label) {
                label = "Borderless Button";
            }
            const is_icon_enabled = $("#enable_borderless_button_icon").prop("checked") === true;
            current_banner.buttons.push({
                type: "borderless",
                intent: current_banner.intent,
                label,
                icon: is_icon_enabled
                    ? $("#borderless_button_select_icon").val()?.toString()
                    : undefined,
            });
            $("#borderless_button_text").val(label);
            sortButtons(current_banner.buttons);
        } else {
            current_banner.buttons = current_banner.buttons.filter(
                (button) => button.type !== "borderless",
            );
        }
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.buttons = current_banner.buttons;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $("input[name='borderless-button-icon-select']").on("change", function (this: HTMLElement) {
        const borderless_button = current_banner.buttons.find(
            (button) => button.type === "borderless",
        );
        if (borderless_button === undefined) {
            return;
        }
        if ($(this).attr("id") === "enable_borderless_button_icon") {
            borderless_button.icon = $("#borderless_button_select_icon").val()?.toString() ?? "";
        } else {
            delete borderless_button.icon;
        }
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.buttons = current_banner.buttons;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $("#borderless_button_select_icon").on("change", function (this: HTMLElement) {
        const borderless_button = current_banner.buttons.find(
            (button) => button.type === "borderless",
        );
        if (borderless_button === undefined) {
            return;
        }
        if (!borderless_button.icon) {
            return;
        }
        borderless_button.icon = $(this).val()?.toString() ?? "";
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.buttons = current_banner.buttons;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $("#borderless_button_text").on("input", function (this: HTMLElement) {
        const borderless_button = current_banner.buttons.find(
            (button) => button.type === "borderless",
        );
        if (borderless_button === undefined) {
            return;
        }
        borderless_button.label = $(this).val()?.toString() ?? "";
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.buttons = current_banner.buttons;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });
});
