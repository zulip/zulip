import type Handlebars from "handlebars/runtime.js";
import $ from "jquery";

import render_banner from "../templates/components/banner.hbs";

type ComponentIntent = "neutral" | "brand" | "info" | "success" | "warning" | "danger";

type ActionButton = {
    type: "primary" | "quiet" | "borderless";
    intent?: ComponentIntent;
    label: string;
    icon?: string;
    custom_classes?: string;
};

export type Banner = {
    intent: ComponentIntent;
    label: string | Handlebars.SafeString;
    buttons: ActionButton[];
    close_button: boolean;
    custom_classes?: string;
};

export type AlertBanner = Banner & {
    process: string;
};

export function open(banner: Banner | AlertBanner, $banner_container: JQuery): void {
    const banner_html = render_banner(banner);
    $banner_container.html(banner_html);
    $(window).trigger("resize");
}

export function append(banner: Banner | AlertBanner, $banner_container: JQuery): void {
    const $banner_html = render_banner(banner);
    $banner_container.append($banner_html);
    $(window).trigger("resize");
}

export function close($banner: JQuery): void {
    $banner.remove();
    $(window).trigger("resize");
}

export function initialize(): void {
    $("body").on("click", ".banner .banner-close-action", function (this: HTMLElement, e) {
        e.preventDefault();
        e.stopPropagation();
        const $banner = $(this).closest(".banner");
        close($banner);
    });
}
