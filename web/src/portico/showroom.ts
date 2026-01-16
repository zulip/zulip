import Handlebars from "handlebars/runtime.js";
import $ from "jquery";
import assert from "minimalistic-assert";

import render_banner from "../../templates/components/banner.hbs";
import render_filter_input from "../../templates/components/showroom/filter_input.hbs";
import {$t, $t_html} from "../i18n.ts";
import type {HTMLSelectOneElement} from "../types.ts";

type ComponentIntent = "neutral" | "brand" | "info" | "success" | "warning" | "danger";

type ActionButton = {
    variant: "solid" | "subtle" | "text";
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
            variant: "subtle",
            intent: "neutral",
            label: "Subtle Button",
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
                variant: "subtle",
                intent: "neutral",
                label: "Subtle Button",
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
                variant: "subtle",
                intent: "info",
                label: "Yes, please!",
            },
            {
                variant: "text",
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
                variant: "subtle",
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
                    "This demo organization will be automatically deactivated in 30 days, unless it's converted into a permanent organization.",
            }),
        ),
        buttons: [
            {
                variant: "text",
                intent: "info",
                label: $t({defaultMessage: "Learn more"}),
            },
            {
                variant: "subtle",
                intent: "info",
                label: $t({defaultMessage: "Convert"}),
            },
        ],
        close_button: true,
        custom_classes: "navbar-alert-banner",
    },
    notifications: {
        process: "desktop-notifications",
        intent: "brand",
        label: new Handlebars.SafeString(
            $t_html({
                defaultMessage:
                    "Zulip needs your permission to enable desktop notifications for important messages.",
            }),
        ),
        buttons: [
            {
                variant: "solid",
                intent: "brand",
                label: "Enable notifications",
            },
            {
                variant: "subtle",
                intent: "brand",
                label: "Ask me later",
            },
            {
                variant: "text",
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
                variant: "subtle",
                intent: "warning",
                label: "Edit your profile",
            },
        ],
        close_button: true,
        custom_classes: "navbar-alert-banner",
    },
    "insecure-desktop-app": {
        process: "insecure-desktop-app",
        intent: "warning",
        label: "Zulip Desktop is not updating automatically. Please upgrade for security updates and other improvements.",
        buttons: [
            {
                variant: "subtle",
                intent: "warning",
                label: "Download the latest version",
            },
        ],
        close_button: true,
        custom_classes: "navbar-alert-banner",
    },
    "unsupported-browser": {
        process: "unsupported-browser",
        intent: "warning",
        label: "Because you're using an unsupported or very old browser, Zulip may not work as expected.",
        buttons: [
            {
                variant: "text",
                intent: "warning",
                label: "Learn more",
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
                variant: "subtle",
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
                variant: "subtle",
                intent: "danger",
                label: "Learn more",
            },
            {
                variant: "text",
                intent: "danger",
                label: "Dismiss for a week",
            },
        ],
        close_button: true,
        custom_classes: "navbar-alert-banner",
    },
};

const sortButtons = (buttons: ActionButton[]): void => {
    const sortOrder: Record<ActionButton["variant"], number> = {
        solid: 1,
        subtle: 2,
        text: 3,
    };

    buttons.sort((a, b) => sortOrder[a.variant] - sortOrder[b.variant]);
};

const update_buttons = (buttons: ActionButton[]): void => {
    const solid_button = buttons.find((button) => button.variant === "solid");
    if (solid_button) {
        $("#enable_solid_button").prop("checked", true);
        $("#solid_button_text").val(solid_button.label);
        if (solid_button.icon) {
            $("#solid_button_select_icon").val(solid_button.icon);
            $("#enable_solid_button_icon").prop("checked", true);
        } else {
            $("#disable_solid_button_icon").prop("checked", true);
        }
    } else {
        $("#disable_solid_button").prop("checked", true);
        $("#solid_button_text").val("");
        $("#disable_solid_button_icon").prop("checked", true);
    }
    const subtle_button = buttons.find((button) => button.variant === "subtle");
    if (subtle_button) {
        $("#enable_subtle_button").prop("checked", true);
        $("#subtle_button_text").val(subtle_button.label);
        if (subtle_button.icon) {
            $("#subtle_button_select_icon").val(subtle_button.icon);
            $("#enable_subtle_button_icon").prop("checked", true);
        } else {
            $("#disable_subtle_button_icon").prop("checked", true);
        }
    } else {
        $("#disable_subtle_button").prop("checked", true);
        $("#subtle_button_text").val("");
        $("#disable_subtle_button_icon").prop("checked", true);
    }
    const text_button = buttons.find((button) => button.variant === "text");
    if (text_button) {
        $("#enable_text_button").prop("checked", true);
        $("#text_button_text").val(text_button.label);
        if (text_button.icon) {
            $("#text_button_select_icon").val(text_button.icon);
            $("#enable_text_button_icon").prop("checked", true);
        } else {
            $("#disable_text_button_icon").prop("checked", true);
        }
    } else {
        $("#disable_text_button").prop("checked", true);
        $("#text_button_text").val("");
        $("#disable_text_button_icon").prop("checked", true);
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

    $("input[name='solid-button-select']").on("change", (e) => {
        if ($(e.target).attr("id") === "enable_solid_button") {
            if (current_banner.buttons.some((button) => button.variant === "solid")) {
                return;
            }
            let label = $<HTMLInputElement>("input#solid_button_text").val();
            assert(label !== undefined);
            if (label === "") {
                label = "Solid Button";
            }
            const is_icon_enabled = $("#enable_solid_button_icon").prop("checked") === true;
            current_banner.buttons.push({
                variant: "solid",
                intent: current_banner.intent,
                label,
                icon: is_icon_enabled
                    ? $<HTMLSelectOneElement>(
                          "select:not([multiple])#solid_button_select_icon",
                      ).val()
                    : undefined,
            });
            $("#solid_button_text").val(label);
        } else {
            current_banner.buttons = current_banner.buttons.filter(
                (button) => button.variant !== "solid",
            );
        }
        sortButtons(current_banner.buttons);
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.buttons = current_banner.buttons;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $("input[name='solid-button-icon-select']").on("change", (e) => {
        const solid_button = current_banner.buttons.find((button) => button.variant === "solid");
        if (solid_button === undefined) {
            return;
        }
        if ($(e.target).attr("id") === "enable_solid_button_icon") {
            solid_button.icon =
                $<HTMLSelectOneElement>("select:not([multiple])#solid_button_select_icon").val() ??
                "";
        } else {
            delete solid_button.icon;
        }
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.buttons = current_banner.buttons;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $<HTMLSelectOneElement>("select:not([multiple])#solid_button_select_icon").on(
        "change",
        function () {
            const solid_button = current_banner.buttons.find(
                (button) => button.variant === "solid",
            );
            if (solid_button === undefined) {
                return;
            }
            if (!solid_button.icon) {
                return;
            }
            solid_button.icon = this.value;
            $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
            if (current_banner.process === "custom-banner") {
                custom_normal_banner.buttons = current_banner.buttons;
                $("#showroom_component_banner_default_wrapper").html(
                    banner_html(custom_normal_banner),
                );
            }
        },
    );

    $<HTMLInputElement>("input#solid_button_text").on("input", function () {
        const solid_button = current_banner.buttons.find((button) => button.variant === "solid");
        if (solid_button === undefined) {
            return;
        }
        solid_button.label = this.value;
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.buttons = current_banner.buttons;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $("input[name='subtle-button-select']").on("change", (e) => {
        if ($(e.target).attr("id") === "enable_subtle_button") {
            if (current_banner.buttons.some((button) => button.variant === "subtle")) {
                return;
            }
            let label = $<HTMLInputElement>("input#subtle_button_text").val();
            assert(label !== undefined);
            if (label === "") {
                label = "Subtle Button";
            }
            const is_icon_enabled = $("#enable_subtle_button_icon").prop("checked") === true;
            current_banner.buttons.push({
                variant: "subtle",
                intent: current_banner.intent,
                label,
                icon: is_icon_enabled
                    ? $<HTMLSelectOneElement>(
                          "select:not([multiple])#subtle_button_select_icon",
                      ).val()
                    : undefined,
            });
            $("#subtle_button_text").val(label);
            sortButtons(current_banner.buttons);
        } else {
            current_banner.buttons = current_banner.buttons.filter(
                (button) => button.variant !== "subtle",
            );
        }
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.buttons = current_banner.buttons;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $("input[name='subtle-button-icon-select']").on("change", (e) => {
        const subtle_button = current_banner.buttons.find((button) => button.variant === "subtle");
        if (subtle_button === undefined) {
            return;
        }
        if ($(e.target).attr("id") === "enable_subtle_button_icon") {
            subtle_button.icon =
                $<HTMLSelectOneElement>("select:not([multiple])#subtle_button_select_icon").val() ??
                "";
        } else {
            delete subtle_button.icon;
        }
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.buttons = current_banner.buttons;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $<HTMLSelectOneElement>("select:not([multiple])#subtle_button_select_icon").on(
        "change",
        function () {
            const subtle_button = current_banner.buttons.find(
                (button) => button.variant === "subtle",
            );
            if (subtle_button === undefined) {
                return;
            }
            if (!subtle_button.icon) {
                return;
            }
            subtle_button.icon = this.value;
            $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
            if (current_banner.process === "custom-banner") {
                custom_normal_banner.buttons = current_banner.buttons;
                $("#showroom_component_banner_default_wrapper").html(
                    banner_html(custom_normal_banner),
                );
            }
        },
    );

    $<HTMLInputElement>("input#subtle_button_text").on("input", function () {
        const subtle_button = current_banner.buttons.find((button) => button.variant === "subtle");
        if (subtle_button === undefined) {
            return;
        }
        subtle_button.label = this.value;
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.buttons = current_banner.buttons;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $("input[name='text-button-select']").on("change", function (this: HTMLElement) {
        if (this.id === "enable_text_button") {
            if (current_banner.buttons.some((button) => button.variant === "text")) {
                return;
            }
            let label = $<HTMLInputElement>("input#text_button_text").val();
            assert(label !== undefined);
            if (label === "") {
                label = "Text Button";
            }
            const is_icon_enabled = $("#enable_text_button_icon").prop("checked") === true;
            current_banner.buttons.push({
                variant: "text",
                intent: current_banner.intent,
                label,
                icon: is_icon_enabled
                    ? $<HTMLSelectOneElement>(
                          "select:not([multiple])#text_button_select_icon",
                      ).val()
                    : undefined,
            });
            $("#text_button_text").val(label);
            sortButtons(current_banner.buttons);
        } else {
            current_banner.buttons = current_banner.buttons.filter(
                (button) => button.variant !== "text",
            );
        }
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.buttons = current_banner.buttons;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $("input[name='text-button-icon-select']").on("change", function () {
        const text_button = current_banner.buttons.find((button) => button.variant === "text");
        if (text_button === undefined) {
            return;
        }
        if (this.id === "enable_text_button_icon") {
            text_button.icon =
                $<HTMLSelectOneElement>("select:not([multiple])#text_button_select_icon").val() ??
                "";
        } else {
            delete text_button.icon;
        }
        $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
        if (current_banner.process === "custom-banner") {
            custom_normal_banner.buttons = current_banner.buttons;
            $("#showroom_component_banner_default_wrapper").html(banner_html(custom_normal_banner));
        }
    });

    $<HTMLSelectOneElement>("select:not([multiple])#text_button_select_icon").on(
        "change",
        function () {
            const text_button = current_banner.buttons.find((button) => button.variant === "text");
            if (text_button === undefined) {
                return;
            }
            if (!text_button.icon) {
                return;
            }
            text_button.icon = this.value;
            $("#showroom_component_banner_navbar_alerts_wrapper").html(banner_html(current_banner));
            if (current_banner.process === "custom-banner") {
                custom_normal_banner.buttons = current_banner.buttons;
                $("#showroom_component_banner_default_wrapper").html(
                    banner_html(custom_normal_banner),
                );
            }
        },
    );

    $<HTMLInputElement>("input#text_button_text").on("input", function () {
        const text_button = current_banner.buttons.find((button) => button.variant === "text");
        if (text_button === undefined) {
            return;
        }
        text_button.label = this.value;
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
