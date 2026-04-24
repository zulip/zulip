import type Handlebars from "handlebars/runtime.js";
import $ from "jquery";

import render_banner from "../templates/components/banner.hbs";

import type {ActionButton} from "./buttons.ts";
import type {ComponentIntent} from "./types.ts";

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

export function open(banner: Banner | AlertBanner, $banner_container: JQuery): JQuery {
    const banner_html = render_banner(banner);
    const $banner = $(banner_html);
    $banner_container.empty().append($banner);

    return $banner;
}

export function append(banner: Banner | AlertBanner, $banner_container: JQuery): void {
    const $banner_html = render_banner(banner);
    $banner_container.append($banner_html);
}

export function open_and_close(
    banner: Banner | AlertBanner,
    $banner_container: JQuery,
    remove_after: number,
): void {
    const $banner = open(banner, $banner_container);

    setTimeout(() => {
        close($banner);
    }, remove_after);
}

export function close($banner: JQuery): void {
    $banner.remove();
}

export function initialize(): void {
    $("body").on("click", ".banner .banner-close-action", function (this: HTMLElement, e) {
        e.preventDefault();
        e.stopPropagation();
        const $banner = $(this).closest(".banner");
        close($banner);
    });
}
