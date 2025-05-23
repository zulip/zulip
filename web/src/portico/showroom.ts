import Handlebars from "handlebars/runtime.js";
import $ from "jquery";
import assert from "minimalistic-assert";

import render_banner from "../../templates/components/banner.hbs";
import render_filter_input from "../../templates/components/showroom/filter_input.hbs";
import {$t, $t_html} from "../i18n.ts";
import type {HTMLSelectOneElement} from "../types.ts";

type ComponentIntent = "neutral" | "brand" | "info" | "success" | "warning" | "danger";

type ActionButton = {
    attention: "primary" | "quiet" | "borderless";
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
            attention: "quiet",
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
                attention: "quiet",
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
                attention: "quiet",
                intent: "info",
                label: "Yes, please!",
            },
            {
                attention: "borderless",
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
                attention: "quiet",
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
            $t_html({
                defaultMessage:
                    "This demo organization will be automatically deleted in 30 days, unless it's converted into a permanent organization.",
            }),
        ),
        buttons: [
            {
                attention: "borderless",
                intent: "info",
                label: $t({defaultMessage: "Learn more"}),
            },
            {
                attention: "quiet",
                intent: "info",
                label: $t({defaultMessage: "Convert"}),
            },
        ],
        close_button: true,
        custom_classes: "navbar-alert-banner",
    },
    notifications: {
        process: "notifications",
        intent: "brand",
        label: new Handlebars.SafeString(
            $t_html({
                defaultMessage:
                    "Zulip needs your permission to enable desktop notifications for important messages.",
            }),
        ),
        buttons: [
            {
                attention: "primary",
                intent: "brand",
                label: "Enable notifications",
            },
            {
                attention: "quiet",
                intent: "brand",
                label: "Ask me later",
            },
            {
                attention: "borderless",
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
                attention: "quiet",
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
        label: "Zulip desktop is not updating automatically. Please upgrade for security updates and other improvements.",
        buttons: [
            {
                attention: "quiet",
                intent: "warning",
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
                attention: "quiet",
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
                attention: "quiet",
                intent: "danger",
                label: "Learn more",
            },
            {
                attention: "borderless",
                intent: "danger",
                label: "Dismiss for a week",
            },
        ],
        close_button: true,
        custom_classes: "navbar-alert-banner",
    },
};

const sortButtons = (buttons: ActionButton[]): void => {
    const sortOrder: Record<ActionButton["attention"], number> = {
        primary: 1,
        quiet: 2,
        borderless: 3,
    };

    buttons.sort((a, b) => sortOrder[a.attention] - sortOrder[b.attention]);
};

const update_buttons = (buttons: ActionButton[]): void => {
    const primary_button = buttons.find((button) => button.attention === "primary");
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
    const quiet_button = buttons.find((button) => button.attention === "quiet");
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
    const borderless_button = buttons.find((button) => button.attention === "borderless");
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

    $<HTMLInputElement>("input#button_text").on("input", function () {
        const button_text = this.value;
        $(".action-button-label").text(button_text);
    });

    $("#clear_button_text").on("click", () => {
        $("#button_text").val("");
        $(".action-button-label").text($t({defaultMessage: "Button joy"}));
    });

    $<HTMLSelectOneElement>("select:not([multiple])#button_select_icon").on("change", function () {
        const icon_name = this.value;
        $(".action-button .zulip-icon, .icon-button .zulip-icon").attr(
            "class",
            (_index, className) =>
                className.replaceAll(/zulip-icon-[^\s]+/g, `zulip-icon-${icon_name}`),
        );
    });

    $<HTMLSelectOneElement>("select:not([multiple]).select_background").on("change", function () {
        const background_var = this.value;
        $("body").css("background-color", `var(${background_var})`);
    });

    // Code for /devtools/banners design testing page.
    update_banner();

    // Populate banner type select options
    const $banner_select = $<HTMLSelectOneElement>("select:not([multiple])#banner_select_type");
    for (const key of Object.keys(alert_banners)) {
        $banner_select.append($("<option>").val(key).text(key));
    }

    const $banner_intent_select = $("#showroom_component_banner_select_intent");
    for (const intent of component_intents) {
        $banner_intent_select.append($("<option>").val(intent).text(intent));
    }

    $<HTMLSelectOneElement>("select:not([multiple])#showroom_component_banner_select_intent").on(
        "change",
        function () {
            const selected_intent = this.value;
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
                $("#showroom_component_banner_default_wrapper").html(
                    banner_html(custom_normal_banner),
                );
            }
            $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        },
    );

    $banner_select.on("change", function () {
        const banner_type = this.value;
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

    $<HTMLInputElement>("input#banner_label").on("input", function () {
        const banner_label = this.value;
        current_banner.label = banner_label;
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.label = banner_label;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $("input[name='primary-button-select']").on("change", (e) => {
        if ($(e.target).attr("id") === "enable_primary_button") {
            if (current_banner.buttons.some((button) => button.attention === "primary")) {
                return;
            }
            let label = $<HTMLInputElement>("input#primary_button_text").val();
            assert(label !== undefined);
            if (label === "") {
                label = "Primary Button";
            }
            const is_icon_enabled = $("#enable_primary_button_icon").prop("checked") === true;
            current_banner.buttons.push({
                attention: "primary",
                intent: current_banner.intent,
                label,
                icon: is_icon_enabled
                    ? $<HTMLSelectOneElement>(
                          "select:not([multiple])#primary_button_select_icon",
                      ).val()
                    : undefined,
            });
            $("#primary_button_text").val(label);
        } else {
            current_banner.buttons = current_banner.buttons.filter(
                (button) => button.attention !== "primary",
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
        const primary_button = current_banner.buttons.find(
            (button) => button.attention === "primary",
        );
        if (primary_button === undefined) {
            return;
        }
        if ($(e.target).attr("id") === "enable_primary_button_icon") {
            primary_button.icon =
                $<HTMLSelectOneElement>(
                    "select:not([multiple])#primary_button_select_icon",
                ).val() ?? "";
        } else {
            delete primary_button.icon;
        }
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.buttons = current_banner.buttons;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $<HTMLSelectOneElement>("select:not([multiple])#primary_button_select_icon").on(
        "change",
        function () {
            const primary_button = current_banner.buttons.find(
                (button) => button.attention === "primary",
            );
            if (primary_button === undefined) {
                return;
            }
            if (!primary_button.icon) {
                return;
            }
            primary_button.icon = this.value;
            $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
            if (current_banner.process === "custom-banner") {
                custom_normal_banner.buttons = current_banner.buttons;
                $("#showroom_component_banner_default_wrapper").html(
                    banner_html(custom_normal_banner),
                );
            }
        },
    );

    $<HTMLInputElement>("input#primary_button_text").on("input", function () {
        const primary_button = current_banner.buttons.find(
            (button) => button.attention === "primary",
        );
        if (primary_button === undefined) {
            return;
        }
        primary_button.label = this.value;
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.buttons = current_banner.buttons;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $("input[name='quiet-button-select']").on("change", (e) => {
        if ($(e.target).attr("id") === "enable_quiet_button") {
            if (current_banner.buttons.some((button) => button.attention === "quiet")) {
                return;
            }
            let label = $<HTMLInputElement>("input#quiet_button_text").val();
            assert(label !== undefined);
            if (label === "") {
                label = "Quiet Button";
            }
            const is_icon_enabled = $("#enable_quiet_button_icon").prop("checked") === true;
            current_banner.buttons.push({
                attention: "quiet",
                intent: current_banner.intent,
                label,
                icon: is_icon_enabled
                    ? $<HTMLSelectOneElement>(
                          "select:not([multiple])#quiet_button_select_icon",
                      ).val()
                    : undefined,
            });
            $("#quiet_button_text").val(label);
            sortButtons(current_banner.buttons);
        } else {
            current_banner.buttons = current_banner.buttons.filter(
                (button) => button.attention !== "quiet",
            );
        }
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.buttons = current_banner.buttons;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $("input[name='quiet-button-icon-select']").on("change", (e) => {
        const quiet_button = current_banner.buttons.find((button) => button.attention === "quiet");
        if (quiet_button === undefined) {
            return;
        }
        if ($(e.target).attr("id") === "enable_quiet_button_icon") {
            quiet_button.icon =
                $<HTMLSelectOneElement>("select:not([multiple])#quiet_button_select_icon").val() ??
                "";
        } else {
            delete quiet_button.icon;
        }
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.buttons = current_banner.buttons;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $<HTMLSelectOneElement>("select:not([multiple])#quiet_button_select_icon").on(
        "change",
        function () {
            const quiet_button = current_banner.buttons.find(
                (button) => button.attention === "quiet",
            );
            if (quiet_button === undefined) {
                return;
            }
            if (!quiet_button.icon) {
                return;
            }
            quiet_button.icon = this.value;
            $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
            if (current_banner.process === "custom-banner") {
                custom_normal_banner.buttons = current_banner.buttons;
                $("#showroom_component_banner_default_wrapper").html(
                    banner_html(custom_normal_banner),
                );
            }
        },
    );

    $<HTMLInputElement>("input#quiet_button_text").on("input", function () {
        const quiet_button = current_banner.buttons.find((button) => button.attention === "quiet");
        if (quiet_button === undefined) {
            return;
        }
        quiet_button.label = this.value;
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.buttons = current_banner.buttons;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $("input[name='borderless-button-select']").on("change", function (this: HTMLElement) {
        if (this.id === "enable_borderless_button") {
            if (current_banner.buttons.some((button) => button.attention === "borderless")) {
                return;
            }
            let label = $<HTMLInputElement>("input#borderless_button_text").val();
            assert(label !== undefined);
            if (label === "") {
                label = "Borderless Button";
            }
            const is_icon_enabled = $("#enable_borderless_button_icon").prop("checked") === true;
            current_banner.buttons.push({
                attention: "borderless",
                intent: current_banner.intent,
                label,
                icon: is_icon_enabled
                    ? $<HTMLSelectOneElement>(
                          "select:not([multiple])#borderless_button_select_icon",
                      ).val()
                    : undefined,
            });
            $("#borderless_button_text").val(label);
            sortButtons(current_banner.buttons);
        } else {
            current_banner.buttons = current_banner.buttons.filter(
                (button) => button.attention !== "borderless",
            );
        }
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.buttons = current_banner.buttons;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $("input[name='borderless-button-icon-select']").on("change", function () {
        const borderless_button = current_banner.buttons.find(
            (button) => button.attention === "borderless",
        );
        if (borderless_button === undefined) {
            return;
        }
        if (this.id === "enable_borderless_button_icon") {
            borderless_button.icon =
                $<HTMLSelectOneElement>(
                    "select:not([multiple])#borderless_button_select_icon",
                ).val() ?? "";
        } else {
            delete borderless_button.icon;
        }
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.buttons = current_banner.buttons;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $<HTMLSelectOneElement>("select:not([multiple])#borderless_button_select_icon").on(
        "change",
        function () {
            const borderless_button = current_banner.buttons.find(
                (button) => button.attention === "borderless",
            );
            if (borderless_button === undefined) {
                return;
            }
            if (!borderless_button.icon) {
                return;
            }
            borderless_button.icon = this.value;
            $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
            if (current_banner.process === "custom-banner") {
                custom_normal_banner.buttons = current_banner.buttons;
                $("#showroom_component_banner_default_wrapper").html(
                    banner_html(custom_normal_banner),
                );
            }
        },
    );

    $<HTMLInputElement>("input#borderless_button_text").on("input", function () {
        const borderless_button = current_banner.buttons.find(
            (button) => button.attention === "borderless",
        );
        if (borderless_button === undefined) {
            return;
        }
        borderless_button.label = this.value;
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.buttons = current_banner.buttons;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    if (window.location.pathname === "/devtools/inputs/") {
        const $filter_input_container = $<HTMLInputElement>(".showroom-filter-input-container");
        $filter_input_container.html(render_filter_input());
    }
});
