import $ from "jquery";
import _ from "lodash";

import whale_image from "../images/hotspots/whale.svg";
import render_hotspot_icon from "../templates/hotspot_icon.hbs";
import render_hotspot_overlay from "../templates/hotspot_overlay.hbs";

import * as blueslip from "./blueslip";
import * as channel from "./channel";
import * as message_viewport from "./message_viewport";
import * as overlays from "./overlays";
import {page_params} from "./page_params";

// popover orientations
const TOP = "top";
const LEFT = "left";
const RIGHT = "right";
const BOTTOM = "bottom";
const LEFT_BOTTOM = "left_bottom";
const VIEWPORT_CENTER = "viewport_center";

// popover orientation can optionally be fixed here to override the
// defaults calculated by compute_placement.
const HOTSPOT_LOCATIONS = new Map([
    [
        "intro_streams",
        {
            element: "#streams_header .left-sidebar-title",
            offset_x: 1.35,
            offset_y: 0.39,
        },
    ],
    [
        "intro_topics",
        {
            element: ".topic-name",
            offset_x: 0.8,
            offset_y: 0.39,
        },
    ],
    [
        "intro_gear",
        {
            element: "#settings-dropdown",
            offset_x: -0.4,
            offset_y: 1.2,
            popover: LEFT_BOTTOM,
        },
    ],
    [
        "intro_compose",
        {
            element: "#new_conversation_button",
            offset_x: 0,
            offset_y: 0,
        },
    ],
]);

const meta = {
    opened_hotspot_name: null,
};

function compute_placement($elt, popover_height, popover_width, prefer_vertical_positioning) {
    const client_rect = $elt.get(0).getBoundingClientRect();
    const distance_from_top = client_rect.top;
    const distance_from_bottom = message_viewport.height() - client_rect.bottom;
    const distance_from_left = client_rect.left;
    const distance_from_right = message_viewport.width() - client_rect.right;

    const elt_will_fit_horizontally =
        distance_from_left + $elt.width() / 2 > popover_width / 2 &&
        distance_from_right + $elt.width() / 2 > popover_width / 2;

    const elt_will_fit_vertically =
        distance_from_bottom + $elt.height() / 2 > popover_height / 2 &&
        distance_from_top + $elt.height() / 2 > popover_height / 2;

    // default to placing the popover in the center of the screen
    let placement = "viewport_center";

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

export function post_hotspot_as_read(hotspot_name) {
    channel.post({
        url: "/json/users/me/hotspots",
        data: {hotspot: hotspot_name},
        error(err) {
            if (err.readyState !== 0) {
                blueslip.error("Failed to fetch hotspots", {
                    readyState: err.readyState,
                    status: err.status,
                    body: err.responseText,
                });
            }
        },
    });
}

function place_icon(hotspot) {
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
        top: $element.outerHeight() * hotspot.location.offset_y,
        left: $element.outerWidth() * hotspot.location.offset_x,
    };
    const client_rect = $element.get(0).getBoundingClientRect();
    const placement = {
        top: client_rect.top + offset.top,
        left: client_rect.left + offset.left,
    };
    $icon.css("display", "block");
    $icon.css(placement);
    return true;
}

function place_popover(hotspot) {
    if (!hotspot.location.element) {
        return;
    }

    const popover_width = $(
        `#hotspot_${CSS.escape(hotspot.name)}_overlay .hotspot-popover`,
    ).outerWidth();
    const popover_height = $(
        `#hotspot_${CSS.escape(hotspot.name)}_overlay .hotspot-popover`,
    ).outerHeight();
    const el_width = $(hotspot.location.element).outerWidth();
    const el_height = $(hotspot.location.element).outerHeight();
    const arrow_offset = 20;

    let popover_offset;
    let arrow_placement;
    const orientation =
        hotspot.location.popover ||
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
            break;
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
        const client_rect = $(hotspot.location.element).get(0).getBoundingClientRect();
        popover_placement = {
            top: client_rect.top + popover_offset.top,
            left: client_rect.left + popover_offset.left,
            transform: "",
        };
    }

    $(`#hotspot_${CSS.escape(hotspot.name)}_overlay .hotspot-popover`).css(popover_placement);
}

function insert_hotspot_into_DOM(hotspot) {
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
            $("body").prepend(hotspot_icon_HTML);
        }
        $("body").prepend(hotspot_overlay_HTML);
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

export function is_open() {
    return meta.opened_hotspot_name !== null;
}

function is_hotspot_displayed(hotspot_name) {
    return $(`#hotspot_${hotspot_name}_overlay`).length;
}

export function close_hotspot_icon(elem) {
    $(elem).animate(
        {opacity: 0},
        {
            duration: 300,
            done: function () {
                $(elem).css({display: "none"});
            }.bind(elem),
        },
    );
}

function close_read_hotspots(new_hotspots) {
    const unwanted_hotspots = _.difference(
        [...HOTSPOT_LOCATIONS.keys()],
        new_hotspots.map((hotspot) => hotspot.name),
    );

    for (const hotspot_name of unwanted_hotspots) {
        close_hotspot_icon($(`#hotspot_${CSS.escape(hotspot_name)}_icon`));
        $(`#hotspot_${CSS.escape(hotspot_name)}_overlay`).remove();
    }
}

export function open_popover_if_hotspot_exist(hotspot_name, bind_element = null) {
    const overlay_name = "hotspot_" + hotspot_name + "_overlay";

    if (is_hotspot_displayed(hotspot_name)) {
        overlays.open_overlay({
            name: overlay_name,
            $overlay: $(`#${CSS.escape(overlay_name)}`),
            on_close: function () {
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

export function load_new(new_hotspots) {
    close_read_hotspots(new_hotspots);
    for (const hotspot of new_hotspots) {
        hotspot.location = HOTSPOT_LOCATIONS.get(hotspot.name);
        if (!is_hotspot_displayed(hotspot.name) && hotspot.location) {
            insert_hotspot_into_DOM(hotspot);
        }
    }
}

export function initialize() {
    load_new(page_params.hotspots);

    // open
    $("body").on("click", ".hotspot-icon", function (e) {
        // hide icon
        close_hotspot_icon(this);

        // show popover
        const [, hotspot_name] = /^hotspot_(.*)_icon$/.exec(
            $(e.target).closest(".hotspot-icon").attr("id"),
        );

        open_popover_if_hotspot_exist(hotspot_name, this);

        meta.opened_hotspot_name = hotspot_name;
        e.preventDefault();
        e.stopPropagation();
    });

    // confirm
    $("body").on("click", ".hotspot.overlay .hotspot-confirm", function (e) {
        e.preventDefault();
        e.stopPropagation();

        const overlay_name = $(this).closest(".hotspot.overlay").attr("id");

        const [, hotspot_name] = /^hotspot_(.*)_overlay$/.exec(overlay_name);

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
