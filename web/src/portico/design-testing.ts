import $ from "jquery";

import {$t} from "../i18n.ts";

$(window).on("load", () => {
    $("input[name='dark-theme-select']").on("change", (e) => {
        if ($(e.target).attr("id") === "enable_dark_theme") {
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
        $(".action-button .zulip-icon").attr("class", (_index, className) =>
            className.replaceAll(/zulip-icon-[^\s]+/g, `zulip-icon-${icon_name}`),
        );
    });

    $("#button_select_background").on("change", function (this: HTMLElement) {
        const background_var = $(this).val()?.toString() ?? "";
        $("body").css("background-color", `var(${background_var})`);
    });
});
