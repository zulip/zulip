var resize = (function () {

var exports = {};

var narrow_window = false;

function confine_to_range(lo, val, hi) {
    if (val < lo) {
        return lo;
    }
    if (val > hi) {
        return hi;
    }
    return val;
}

function size_blocks(blocks, usable_height) {
    var sum_height = 0;
    _.each(blocks, function (block) {
        sum_height += block.real_height;
    });

    _.each(blocks, function (block) {
        var ratio = block.real_height / sum_height;
        ratio = confine_to_range(0.05, ratio, 0.85);
        block.max_height = confine_to_range(80, usable_height * ratio, 1.2 * block.real_height);
    });
}

function set_user_list_heights(res, usable_height, user_presences, group_pms) {
    // Calculate these heights:
    //    res.user_presences_max_height
    //    res.group_pms_max_height
    var blocks = [
        {
            real_height: user_presences.prop('scrollHeight'),
        },
        {
            real_height: group_pms.prop('scrollHeight'),
        },
    ];

    size_blocks(blocks, usable_height);

    res.user_presences_max_height = blocks[0].max_height;
    res.group_pms_max_height = blocks[1].max_height;
}

function get_new_heights() {
    var res = {};
    var viewport_height = message_viewport.height();
    var top_navbar_height = $("#top_navbar").safeOuterHeight(true);
    var invite_user_link_height = $("#invite-user-link").safeOuterHeight(true) || 0;

    res.bottom_whitespace_height = viewport_height * 0.4;

    res.main_div_min_height = viewport_height - top_navbar_height;

    res.bottom_sidebar_height = viewport_height - top_navbar_height;

    res.right_sidebar_height = viewport_height - parseInt($("#right-sidebar").css("marginTop"), 10);

    res.stream_filters_max_height =
        res.bottom_sidebar_height
        - $("#global_filters").safeOuterHeight(true)
        - $("#streams_header").safeOuterHeight(true)
        - 10; // stream_filters margin-bottom

    // Don't let us crush the stream sidebar completely out of view
    res.stream_filters_max_height = Math.max(80, res.stream_filters_max_height);

    // RIGHT SIDEBAR
    var user_presences = $('#user_presences').expectOne();
    var group_pms = $('#group-pms').expectOne();

    var usable_height =
        res.right_sidebar_height
        - $("#feedback_section").safeOuterHeight(true)
        - parseInt(user_presences.css("marginTop"),10)
        - parseInt(user_presences.css("marginBottom"), 10)
        - $("#userlist-header").safeOuterHeight(true)
        - $(".user-list-filter").safeOuterHeight(true)
        - invite_user_link_height
        - parseInt(group_pms.css("marginTop"),10)
        - parseInt(group_pms.css("marginBottom"), 10)
        - $("#group-pm-header").safeOuterHeight(true);

    // set these
    // res.user_presences_max_height
    // res.group_pms_max_height
    set_user_list_heights(
        res,
        usable_height,
        user_presences,
        group_pms
    );

    return res;
}

function left_userlist_get_new_heights() {

    var res = {};
    var viewport_height = message_viewport.height();
    var viewport_width = message_viewport.width();
    var top_navbar_height = $(".header").safeOuterHeight(true);

    var stream_filters = $('#stream_filters').expectOne();
    var user_presences = $('#user_presences').expectOne();
    var group_pms = $('#group-pms').expectOne();

    var stream_filters_real_height = stream_filters.prop("scrollHeight");
    var user_list_real_height = user_presences.prop("scrollHeight");
    var group_pms_real_height = group_pms.prop("scrollHeight");

    res.bottom_whitespace_height = viewport_height * 0.4;

    res.main_div_min_height = viewport_height - top_navbar_height;

    res.bottom_sidebar_height = viewport_height
                                - parseInt($("#left-sidebar").css("marginTop"),10)
                                - parseInt($(".bottom_sidebar").css("marginTop"),10);


    res.total_leftlist_height = res.bottom_sidebar_height
                                - $("#global_filters").safeOuterHeight(true)
                                - $("#streams_header").safeOuterHeight(true)
                                - $("#userlist-header").safeOuterHeight(true)
                                - $(".user-list-filter").safeOuterHeight(true)
                                - $("#group-pm-header").safeOuterHeight(true)
                                - parseInt(stream_filters.css("marginBottom"),10)
                                - parseInt(user_presences.css("marginTop"), 10)
                                - parseInt(user_presences.css("marginBottom"), 10)
                                - parseInt(group_pms.css("marginTop"), 10)
                                - parseInt(group_pms.css("marginBottom"), 10)
                                - 15;

    var blocks = [
        {
            real_height: stream_filters_real_height,
        },
        {
            real_height: user_list_real_height,
        },
        {
            real_height: group_pms_real_height,
        },
    ];

    size_blocks(blocks, res.total_leftlist_height);

    res.stream_filters_max_height = blocks[0].max_height;
    res.user_presences_max_height = blocks[1].max_height;
    res.group_pms_max_height = blocks[2].max_height;

    res.viewport_height = viewport_height;
    res.viewport_width = viewport_width;

    return res;
}

exports.watch_manual_resize = function (element) {
    return (function on_box_resize(cb) {
        var box = document.querySelector(element);

        if (!box) {
            blueslip.error('Bad selector in watch_manual_resize: ' + element);
            return;
        }

        var meta = {
            box: box,
            height: null,
            mousedown: false,
        };

        var box_handler = function () {
            meta.mousedown = true;
            meta.height = meta.box.clientHeight;
        };
        meta.box.addEventListener("mousedown", box_handler);

        // If the user resizes the textarea manually, we use the
        // callback to stop autosize from adjusting the height.
        var body_handler = function () {
            if (meta.mousedown === true) {
                meta.mousedown = false;
                if (meta.height !== meta.box.clientHeight) {
                    meta.height = meta.box.clientHeight;
                    cb.call(meta.box, meta.height);
                }
            }
        };
        document.body.addEventListener("mouseup", body_handler);

        return [box_handler, body_handler];
    }(function (height) {
        // This callback disables autosize on the textarea.  It
        // will be re-enabled when this component is next opened.
        $(element).trigger("autosize.destroy")
            .height(height + "px");
    }));
};

exports.resize_bottom_whitespace = function (h) {
    if (page_params.autoscroll_forever) {
        $("#bottom_whitespace").height($("#compose-container")[0].offsetHeight);
    } else if (h !== undefined) {
        $("#bottom_whitespace").height(h.bottom_whitespace_height);
    }
};

exports.resize_stream_filters_container = function (h) {
    h = narrow_window ? left_userlist_get_new_heights() : get_new_heights();
    exports.resize_bottom_whitespace(h);
    $("#stream-filters-container").css('max-height', h.stream_filters_max_height);
    $('#stream-filters-container').perfectScrollbar('update');
};

exports.resize_page_components = function () {
    var h;
    var sidebar;

    if (page_params.left_side_userlist) {
        var css_narrow_mode = message_viewport.is_narrow();

        $("#top_navbar").removeClass("rightside-userlist");

        if (css_narrow_mode && !narrow_window) {
            // move stuff to the left sidebar (skinny mode)
            narrow_window = true;
            popovers.set_userlist_placement("left");
            sidebar = $(".bottom_sidebar").expectOne();
            sidebar.append($("#user-list").expectOne());
            sidebar.append($("#group-pm-list").expectOne());
            $("#user_presences").css("margin", "0px");
            $("#group-pms").css("margin", "0px");
            $("#userlist-toggle").css("display", "none");
            $("#invite-user-link").hide();
        } else if (!css_narrow_mode && narrow_window) {
            // move stuff to the right sidebar (wide mode)
            narrow_window = false;
            popovers.set_userlist_placement("right");
            sidebar = $("#right-sidebar").expectOne();
            sidebar.append($("#user-list").expectOne());
            sidebar.append($("#group-pm-list").expectOne());
            $("#user_presences").css("margin", '');
            $("#group-pms").css("margin", '');
            $("#userlist-toggle").css("display", '');
            $("#invite-user-link").show();
        }
    }

    h = narrow_window ? left_userlist_get_new_heights() : get_new_heights();

    exports.resize_bottom_whitespace(h);
    $("#stream-filters-container").css('max-height', h.stream_filters_max_height);
    $("#user_presences").css('max-height', h.user_presences_max_height);
    $("#group-pms").css('max-height', h.group_pms_max_height);

    $('#stream-filters-container').perfectScrollbar('update');
};

var _old_width = $(window).width();

exports.handler = function () {
    var new_width = $(window).width();

    if (new_width !== _old_width) {
        _old_width = new_width;
        condense.clear_message_content_height_cache();
    }

    popovers.hide_all();
    exports.resize_page_components();

    // This function might run onReady (if we're in a narrow window),
    // but before we've loaded in the messages; in that case, don't
    // try to scroll to one.
    if (current_msg_list.selected_id() !== -1) {
        navigate.scroll_to_selected();
    }
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = resize;
}
