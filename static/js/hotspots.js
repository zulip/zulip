"use strict";

const _ = require("lodash");

const render_hotspot_icon = require("../templates/hotspot_icon.hbs");
const render_hotspot_overlay = require("../templates/hotspot_overlay.hbs");
const render_intro_reply_hotspot = require("../templates/intro_reply_hotspot.hbs");

// popover orientations
const TOP = "top";
const LEFT = "left";
const RIGHT = "right";
const BOTTOM = "bottom";
const LEFT_BOTTOM = "left_bottom";
const VIEWPORT_CENTER = "viewport_center";

// popover orientation can optionally be fixed here (property: popover),
// otherwise popovers.compute_placement is used to compute orientation
const HOTSPOT_LOCATIONS = new Map([
    [
        "intro_reply",
        {
            element: ".selected_message .messagebox-content",
            offset_x: 0.85,
            offset_y: 0.7,
            popover: BOTTOM,
        },
    ],
    [
        "intro_streams",
        {
            element: "#streams_header .sidebar-title",
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
            element: "#left_bar_compose_stream_button_big",
            offset_x: 0,
            offset_y: 0,
        },
    ],
]);

// popover illustration url(s)
const WHALE = "/static/images/hotspots/whale.svg";

exports.post_hotspot_as_read = function (hotspot_name) {
    channel.post({
        url: "/json/users/me/hotspots",
        data: {hotspot: JSON.stringify(hotspot_name)},
        error(err) {
            blueslip.error(err.responseText);
        },
    });
};

function place_icon(hotspot) {
    const element = $(hotspot.location.element);
    const icon = $(`#hotspot_${CSS.escape(hotspot.name)}_icon`);

    if (
        element.length === 0 ||
        element.css("display") === "none" ||
        !element.is(":visible") ||
        element.is(":hidden")
    ) {
        icon.css("display", "none");
        return false;
    }

    const offset = {
        top: element.outerHeight() * hotspot.location.offset_y,
        left: element.outerWidth() * hotspot.location.offset_x,
    };
    const client_rect = element.get(0).getBoundingClientRect();
    const placement = {
        top: client_rect.top + offset.top,
        left: client_rect.left + offset.left,
    };
    icon.css("display", "block");
    icon.css(placement);
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
        popovers.compute_placement(
            $(hotspot.location.element),
            popover_height,
            popover_width,
            false,
        );

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
            blueslip.error("Invalid popover placement value for hotspot '" + hotspot.name + "'");
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
    if (hotspot.name === "intro_reply") {
        $("#bottom_whitespace").append(render_intro_reply_hotspot({}));
        return;
    }

    const hotspot_overlay_HTML = render_hotspot_overlay({
        name: hotspot.name,
        title: hotspot.title,
        description: hotspot.description,
        img: WHALE,
    });

    const hotspot_icon_HTML = render_hotspot_icon({
        name: hotspot.name,
    });

    setTimeout(() => {
        $("body").prepend(hotspot_icon_HTML);
        $("body").prepend(hotspot_overlay_HTML);
        if (place_icon(hotspot)) {
            place_popover(hotspot);
        }

        // reposition on any event that might update the UI
        for (const event_name of ["resize", "scroll", "onkeydown", "click"]) {
            window.addEventListener(
                event_name,
                _.debounce(() => {
                    if (place_icon(hotspot)) {
                        place_popover(hotspot);
                    }
                }, 10),
                true,
            );
        }
    }, hotspot.delay * 1000);
}

exports.is_open = function () {
    return $(".hotspot.overlay").hasClass("show");
};

exports.close_hotspot_icon = function (elem) {
    $(elem).animate(
        {opacity: 0},
        {
            duration: 300,
            done: function () {
                $(elem).css({display: "none"});
            }.bind(elem),
        },
    );
};

function close_read_hotspots(new_hotspots) {
    const unwanted_hotspots = _.difference(
        Array.from(HOTSPOT_LOCATIONS.keys()),
        new_hotspots.map((hotspot) => hotspot.name),
    );

    for (const hotspot_name of unwanted_hotspots) {
        exports.close_hotspot_icon($(`#hotspot_${CSS.escape(hotspot_name)}_icon`));
    }
}

exports.load_new = function (new_hotspots) {
    close_read_hotspots(new_hotspots);
    for (const hotspot of new_hotspots) {
        hotspot.location = HOTSPOT_LOCATIONS.get(hotspot.name);
        insert_hotspot_into_DOM(hotspot);
    }
};

exports.initialize = function () {
    exports.load_new(page_params.hotspots);
};

window.hotspots = exports;
