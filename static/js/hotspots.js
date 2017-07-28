var hotspots = (function () {

var exports = {};

// icon placements (relative to element):
var TOP_LEFT = 'TOP_LEFT';
var TOP_RIGHT = 'TOP_RIGHT';
var BOTTOM_RIGHT = 'BOTTOM_RIGHT';
var BOTTOM_LEFT = 'BOTTOM_LEFT';
var CENTER = 'CENTER';

var HOTSPOT_LOCATIONS = {
    click_to_reply: {
        element: '.selected_message .messagebox-content',
        icon: CENTER,
    },
    new_topic_button: {
        element: '#left_bar_compose_stream_button_big',
        icon: TOP_LEFT,
    },
    stream_settings: {
        element: '#streams_inline_cog',
        icon: CENTER,
    },
};

exports.map_hotspots_to_DOM = function (hotspots, locations) {
    hotspots.forEach(function (hotspot) {
        hotspot.location = locations[hotspot.name];
    });
};

exports.post_hotspot_as_read = function (hotspot_name) {
    channel.post({
        url: '/json/users/me/hotspots',
        data: { hotspot: JSON.stringify(hotspot_name) },
        error: function (err) {
            blueslip.error(err.responseText);
        },
    });
};

function place_icon(hotspot) {
    if (!$(hotspot.location.element).length === 0) {
        $('#hotspot_' + hotspot.name + '_icon').css('display', 'none');
        return;
    }

    var el_width = $(hotspot.location.element).outerWidth();
    var el_height = $(hotspot.location.element).outerHeight();

    var offset;
    switch (hotspot.location.icon) {
        case TOP_LEFT:
            offset = {
                top: 0,
                left: 0,
            };
            break;

        case TOP_RIGHT:
            offset = {
                top: 0,
                left: el_width,
            };
            break;

        case BOTTOM_RIGHT:
            offset = {
                top: el_height,
                left: el_width,
            };
            break;

        case BOTTOM_LEFT:
            offset = {
                top: el_height,
                left: 0,
            };
            break;

        case CENTER:
            offset = {
                top: (el_height / 2),
                left: (el_width / 2),
            };
            break;

        default:
            blueslip.error(
                'Invalid icon placement value for hotspot \'' +
                hotspot.name + '\''
            );
            break;
    }

    var client_rect = $(hotspot.location.element).get(0).getBoundingClientRect();
    var placement = {
        top: client_rect.top + offset.top,
        left: client_rect.left + offset.left,
    };

    if ($(hotspot.location.element).css('display') === 'none' ||
        !$(hotspot.location.element).is(':visible') ||
        $(hotspot.location.element).is(':hidden')) {
        $('#hotspot_' + hotspot.name + '_icon').css('display', 'none');
    } else {
        $('#hotspot_' + hotspot.name + '_icon').css('display', 'block');
        $('#hotspot_' + hotspot.name + '_icon').css(placement);
    }
}

function place_popover(hotspot) {
    if (!hotspot.location.element) {

        return;
    }

    var popover_width = $('#hotspot_' + hotspot.name + '_overlay .hotspot-popover').outerWidth();
    var popover_height = $('#hotspot_' + hotspot.name + '_overlay .hotspot-popover').outerHeight();
    var el_width = $(hotspot.location.element).outerWidth();
    var el_height = $(hotspot.location.element).outerHeight();
    var arrow_offset = 20;

    var popover_offset;
    var arrow_placement;
    switch (popovers.compute_placement($(hotspot.location.element))) {
        case 'top':
            popover_offset = {
                top: -(popover_height + arrow_offset),
                left: (el_width / 2) - (popover_width / 2),
            };
            arrow_placement = 'bottom';
            break;

        case 'left':
            popover_offset = {
                top: (el_height / 2) - (popover_height / 2),
                left: -(popover_width + arrow_offset),
            };
            arrow_placement = 'right';
            break;

        case 'bottom':
            popover_offset = {
                top: el_height + arrow_offset,
                left: (el_width / 2) - (popover_width / 2),
            };
            arrow_placement = 'top';
            break;

        case 'right':
            popover_offset = {
                top: (el_height / 2) - (popover_height / 2),
                left: el_width + arrow_offset,
            };
            arrow_placement = 'left';
            break;

        default:
            blueslip.error(
                'Invalid popover placement value for hotspot \'' +
                hotspot.name + '\''
            );
            break;
    }

    // position arrow
    arrow_placement = 'arrow-' + arrow_placement;
    $('#hotspot_' + hotspot.name + '_overlay .hotspot-popover')
        .removeClass('arrow-top arrow-left arrow-bottom arrow-right')
        .addClass(arrow_placement);

    // position popover
    var client_rect = $(hotspot.location.element).get(0).getBoundingClientRect();
    var popover_placement = {
        top: client_rect.top + popover_offset.top,
        left: client_rect.left + popover_offset.left,
    };

    $('#hotspot_' + hotspot.name + '_overlay .hotspot-popover')
        .css(popover_placement);
}

function insert_hotspot_into_DOM(hotspot) {
    var hotspot_overlay_HTML = templates.render('hotspot_overlay', {
        name: hotspot.name,
        title: hotspot.title,
        description: hotspot.description,
    });

    var hotspot_icon_HTML =
        '<div class="hotspot-icon" id="hotspot_' + hotspot.name + '_icon">' +
            '<span class="dot"></span>' +
            '<span class="pulse"></span>' +
        '</div>';

    setTimeout(function () {
        $('body').prepend(hotspot_icon_HTML);
        place_icon(hotspot);

        $('body').prepend(hotspot_overlay_HTML);
        place_popover(hotspot);

        // reposition on any event that might update the UI
        ['resize', 'scroll', 'onkeydown', 'click']
        .forEach(function (event_name) {
            window.addEventListener(event_name, function () {
                place_icon(hotspot);
                place_popover(hotspot);
            }, true);
        });
    }, (hotspot.delay * 100));
}

exports.load_new = function (new_hotspots) {
    exports.map_hotspots_to_DOM(new_hotspots, HOTSPOT_LOCATIONS);
    new_hotspots.forEach(insert_hotspot_into_DOM);
};

exports.initialize = function () {
    exports.load_new(page_params.hotspots);
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = hotspots;
}
