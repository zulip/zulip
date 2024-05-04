import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";

import whale_image from "../images/hotspots/whale.svg";
import render_hotspot_icon from "../templates/hotspot_icon.hbs";
import render_hotspot_overlay from "../templates/hotspot_overlay.hbs";

import * as blueslip from "./blueslip";
import * as message_viewport from "./message_viewport";
import * as onboarding_steps from "./onboarding_steps";
import * as overlays from "./overlays";
import {current_user} from "./state_data";
import type {Hotspot, HotspotLocation, Placement, RawHotspot} from "./state_data";

// popover orientations
const TOP = "top";
const LEFT = "left";
const RIGHT = "right";
const BOTTOM = "bottom";
const LEFT_BOTTOM = "left_bottom";
const VIEWPORT_CENTER = "viewport_center";

// popover orientation can optionally be fixed here to override the
// defaults calculated by compute_placement.
const HOTSPOT_LOCATIONS = new Map<string, HotspotLocation>([
    [
        "intro_streams",
        {
            element: "#streams_header .left-sidebar-title .streams-tooltip-target",
            offset_x: 1.3,
            offset_y: 0.44,
        },
    ],
    [
        "intro_topics",
        {
            element: ".topic-name",
            offset_x: 1,
            offset_y: 0.4,
        },
    ],
    [
        "intro_gear",
        {
            element: "#personal-menu",
            offset_x: 0.45,
            offset_y: 1.15,
            popover: LEFT_BOTTOM,
        },
    ],
    [
        "intro_compose",
        {
            element: "#new_conversation_button",
            offset_x: 0.5,
            offset_y: -0.7,
        },
    ],
]);

const meta: {
    opened_hotspot_name: null | string;
} = {
    opened_hotspot_name: null,
};

function compute_placement(
    $elt: JQuery,
    popover_height: number,
    popover_width: number,
    prefer_vertical_positioning: boolean,
): Placement {
    const client_rect = $elt.get(0)!.getBoundingClientRect();
    const distance_from_top = client_rect.top;
    const distance_from_bottom = message_viewport.height() - client_rect.bottom;
    const distance_from_left = client_rect.left;
    const distance_from_right = message_viewport.width() - client_rect.right;

    const element_width = $elt.width()!;
    const element_height = $elt.height()!;

    const elt_will_fit_horizontally =
        distance_from_left + element_width / 2 > popover_width / 2 &&
        distance_from_right + element_width / 2 > popover_width / 2;

    const elt_will_fit_vertically =
        distance_from_bottom + element_height / 2 > popover_height / 2 &&
        distance_from_top + element_height / 2 > popover_height / 2;

    // default to placing the popover in the center of the screen
    let placement: Placement = "viewport_center";

    // prioritize left/right over top/bottom
    if (distance_from_top > popover_height && elt_will_fit_horizontally) {
        placement = "top";
    }
    if (distance_from_bottom > popover_height && elt_will_fit_horizontally) {
        placement = "bottom";
    }

    if (prefer_vertical_positioning && placement !== "viewport_center") {
        // If vertical positioning is preferred and the popover fits in
        // either top or bottom position then return.
        return placement;
    }

    if (distance_from_left > popover_width && elt_will_fit_vertically) {
        placement = "left";
    }
    if (distance_from_right > popover_width && elt_will_fit_vertically) {
        placement = "right";
    }

    return placement;
}

export function post_hotspot_as_read(hotspot_name: string): void {
    onboarding_steps.post_onboarding_step_as_read(hotspot_name);
}

function place_icon(hotspot: Hotspot): boolean {
    const $element = $(hotspot.location.element);
    const $icon = $(`#hotspot_${CSS.escape(hotspot.name)}_icon`);

    if (
        $element.length === 0 ||
        $element.css("display") === "none" ||
        !$element.is(":visible") ||
        $element.is(":hidden")
    ) {
        $icon.css("display", "none");
        return false;
    }

    const offset = {
        top: $element.outerHeight()! * hotspot.location.offset_y,
        left: $element.outerWidth()! * hotspot.location.offset_x,
    };
    const client_rect = $element.get(0)!.getBoundingClientRect();
    const placement = {
        top: client_rect.top + offset.top,
        left: client_rect.left + offset.left,
    };
    $icon.css("display", "block");
    $icon.css(placement);
    return true;
}

function place_popover(hotspot: Hotspot): void {
    const popover_width = $(
        `#hotspot_${CSS.escape(hotspot.name)}_overlay .hotspot-popover`,
    ).outerWidth()!;
    const popover_height = $(
        `#hotspot_${CSS.escape(hotspot.name)}_overlay .hotspot-popover`,
    ).outerHeight()!;
    const el_width = $(hotspot.location.element).outerWidth()!;
    const el_height = $(hotspot.location.element).outerHeight()!;

    const arrow_offset = 20;

    let popover_offset;
    let arrow_placement;
    const orientation =
        hotspot.location.popover ??
        compute_placement($(hotspot.location.element), popover_height, popover_width, false);

    switch (orientation) {
        case TOP:
            popover_offset = {
                top: -(popover_height + arrow_offset),
                left: el_width / 2 - popover_width / 2,
            };
            arrow_placement = "bottom";
            break;

        case LEFT:
            popover_offset = {
                top: el_height / 2 - popover_height / 2,
                left: -(popover_width + arrow_offset),
            };
            arrow_placement = "right";
            break;

        case BOTTOM:
            popover_offset = {
                top: el_height + arrow_offset,
                left: el_width / 2 - popover_width / 2,
            };
            arrow_placement = "top";
            break;

        case RIGHT:
            popover_offset = {
                top: el_height / 2 - popover_height / 2,
                left: el_width + arrow_offset,
            };
            arrow_placement = "left";
            break;

        case LEFT_BOTTOM:
            popover_offset = {
                top: 0,
                left: -(popover_width + arrow_offset / 2),
            };
            arrow_placement = "";
            break;

        case VIEWPORT_CENTER:
            popover_offset = {
                top: el_height / 2,
                left: el_width / 2,
            };
            arrow_placement = "";
            break;

        default:
            blueslip.error("Invalid popover placement value for hotspot", {name: hotspot.name});
            return;
    }

    // position arrow
    arrow_placement = "arrow-" + arrow_placement;
    $(`#hotspot_${CSS.escape(hotspot.name)}_overlay .hotspot-popover`)
        .removeClass("arrow-top arrow-left arrow-bottom arrow-right")
        .addClass(arrow_placement);

    // position popover
    let popover_placement;
    if (orientation === VIEWPORT_CENTER) {
        popover_placement = {
            top: "45%",
            left: "50%",
            transform: "translate(-50%, -50%)",
        };
    } else {
        const client_rect = $(hotspot.location.element).get(0)!.getBoundingClientRect();
        popover_placement = {
            top: client_rect.top + popover_offset.top,
            left: client_rect.left + popover_offset.left,
            transform: "",
        };
    }

    $(`#hotspot_${CSS.escape(hotspot.name)}_overlay .hotspot-popover`).css(popover_placement);
}

function insert_hotspot_into_DOM(hotspot: Hotspot): void {
    const hotspot_overlay_HTML = render_hotspot_overlay({
        name: hotspot.name,
        title: hotspot.title,
        description: hotspot.description,
        img: whale_image,
    });

    const hotspot_icon_HTML = render_hotspot_icon({
        name: hotspot.name,
    });

    setTimeout(() => {
        if (!hotspot.has_trigger) {
            $("body").prepend($(hotspot_icon_HTML));
        }
        $("body").prepend($(hotspot_overlay_HTML));
        if (hotspot.has_trigger || place_icon(hotspot)) {
            place_popover(hotspot);
        }

        // reposition on any event that might update the UI
        for (const event_name of ["resize", "scroll", "onkeydown", "click"]) {
            window.addEventListener(
                event_name,
                _.debounce(() => {
                    if (hotspot.has_trigger || place_icon(hotspot)) {
                        place_popover(hotspot);
                    }
                }, 10),
                true,
            );
        }
    }, hotspot.delay * 1000);
}

export function is_open(): boolean {
    return meta.opened_hotspot_name !== null;
}

function is_hotspot_displayed(hotspot_name: string): number {
    return $(`#hotspot_${hotspot_name}_overlay`).length;
}

export function close_hotspot_icon($elem: JQuery): void {
    $elem.animate(
        {opacity: 0},
        {
            duration: 300,
            done() {
                $elem.css({display: "none"});
            },
        },
    );
}

function close_read_hotspots(new_hotspots: RawHotspot[]): void {
    const unwanted_hotspots = _.difference(
        [...HOTSPOT_LOCATIONS.keys()],
        new_hotspots.map((hotspot) => hotspot.name),
    );

    for (const hotspot_name of unwanted_hotspots) {
        close_hotspot_icon($(`#hotspot_${CSS.escape(hotspot_name)}_icon`));
        $(`#hotspot_${CSS.escape(hotspot_name)}_overlay`).remove();
    }
}

export function open_popover_if_hotspot_exist(
    hotspot_name: string,
    bind_element: HTMLElement,
): void {
    const overlay_name = "hotspot_" + hotspot_name + "_overlay";

    if (is_hotspot_displayed(hotspot_name)) {
        overlays.open_overlay({
            name: overlay_name,
            $overlay: $(`#${CSS.escape(overlay_name)}`),
            on_close: function (this: HTMLElement) {
                // close popover
                $(this).css({display: "block"});
                $(this).animate(
                    {opacity: 1},
                    {
                        duration: 300,
                    },
                );
            }.bind(bind_element),
        });
    }
}

export function load_new(new_hotspots: RawHotspot[]): void {
    close_read_hotspots(new_hotspots);

    let hotspot_with_location: Hotspot;
    for (const hotspot of new_hotspots) {
        hotspot_with_location = {
            ...hotspot,
            location: HOTSPOT_LOCATIONS.get(hotspot.name)!,
        };
        if (!is_hotspot_displayed(hotspot.name)) {
            insert_hotspot_into_DOM(hotspot_with_location);
        }
    }
}

export function initialize(): void {
    load_new(onboarding_steps.filter_new_hotspots(current_user.onboarding_steps));

    // open
    $("body").on("click", ".hotspot-icon", function (this: HTMLElement, e) {
        // hide icon
        close_hotspot_icon($(this));

        // show popover
        const match_array = /^hotspot_(.*)_icon$/.exec(
            $(e.target).closest(".hotspot-icon").attr("id")!,
        );

        assert(match_array !== null);
        const [, hotspot_name] = match_array;
        open_popover_if_hotspot_exist(hotspot_name, this);

        meta.opened_hotspot_name = hotspot_name;
        e.preventDefault();
        e.stopPropagation();
    });

    // confirm
    $("body").on("click", ".hotspot.overlay .hotspot-confirm", function (e) {
        e.preventDefault();
        e.stopPropagation();

        const overlay_name = $(this).closest(".hotspot.overlay").attr("id")!;

        const match_array = /^hotspot_(.*)_overlay$/.exec(overlay_name);
        assert(match_array !== null);
        const [, hotspot_name] = match_array;

        // Comment below to disable marking hotspots as read in production
        post_hotspot_as_read(hotspot_name);

        overlays.close_overlay(overlay_name);
        $(`#hotspot_${CSS.escape(hotspot_name)}_icon`).remove();

        // We are removing the hotspot overlay after it's read as it will help us avoid
        // multiple copies of the hotspots when ALWAYS_SEND_ALL_HOTSPOTS is set to true.
        $(`#${overlay_name}`).remove();
    });

    // stop propagation
    $("body").on("click", ".hotspot.overlay .hotspot-popover", (e) => {
        e.stopPropagation();
    });
}
