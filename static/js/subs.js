var subs = (function () {

var exports = {};

exports.show_subs_pane = {
    nothing_selected: function () {
        $(".nothing-selected, #stream_settings_title").show();
        $("#add_new_stream_title, .settings, #stream-creation").hide();
    },
    settings: function () {
        $(".settings, #stream_settings_title").show();
        $("#add_new_stream_title, #stream-creation, .nothing-selected").hide();
    },
};

function check_button_for_sub(sub) {
    var id = parseInt(sub.stream_id, 10);
    return $(".stream-row[data-stream-id='" + id + "'] .check");
}

function row_for_stream_id(stream_id) {
    return $(".stream-row[data-stream-id='" + stream_id + "']");
}

function settings_button_for_sub(sub) {
    // We don't do expectOne() here, because this button is only
    // visible if the user has that stream selected in the streams UI.
    var id = parseInt(sub.stream_id, 10);
    return $(".subscription_settings[data-stream-id='" + id + "'] .subscribe-button");
}

function get_row_data(row) {
    var row_id = row.attr('data-stream-id');
    if (row_id) {
        var row_object = stream_data.get_sub_by_id(row_id);
        return {
            id: row_id,
            object: row_object,
        };
    }
}

function get_active_data() {
    var active_row = $('div.stream-row.active');
    var valid_active_id = active_row.attr('data-stream-id');
    var active_tab = $('.subscriptions-container').find('div.ind-tab.selected');
    return {
        row: active_row,
        id: valid_active_id,
        tab: active_tab,
    };
}

function get_hash_safe() {
    if (typeof window !== "undefined" && typeof window.location.hash === "string") {
        return window.location.hash.substr(1);
    }

    return "";
}

function selectText(element) {
    var range;
    var sel;
    if (window.getSelection) {
        sel = window.getSelection();
        range = document.createRange();
        range.selectNodeContents(element);

        sel.removeAllRanges();
        sel.addRange(range);
    } else if (document.body.createTextRange) {
        range = document.body.createTextRange();
        range.moveToElementText(element);
        range.select();
    }
}

function should_list_all_streams() {
    return !page_params.realm_is_zephyr_mirror_realm;
}

// this finds the stream that is actively open in the settings and focused in
// the left side.
exports.active_stream = function () {
    var hash_components = window.location.hash.substr(1).split(/\//);

    // if the string casted to a number is valid, and another component
    // after exists then it's a stream name/id pair.
    if (typeof parseFloat(hash_components[1]) === "number" && hash_components[2]) {
        return {
            id: parseFloat(hash_components[1]),
            name: hash_components[2],
        };
    }
};

exports.toggle_home = function (sub) {
    stream_muting.update_in_home_view(sub, !sub.in_home_view);
    stream_edit.set_stream_property(sub, 'in_home_view', sub.in_home_view);
};

exports.toggle_pin_to_top_stream = function (sub) {
    stream_edit.set_stream_property(sub, 'pin_to_top', !sub.pin_to_top);
};

exports.maybe_update_realm_default_stream_name  = function (stream_id, new_name) {
    var idx = _.findIndex(page_params.realm_default_streams, function (stream) {
        return stream.stream_id === stream_id;
    });
    if (idx === -1) {
        return;
    }
    page_params.realm_default_streams[idx].name = new_name;
};

exports.update_stream_name = function (sub, new_name) {
    // Rename the stream internally.
    stream_data.rename_sub(sub, new_name);
    var stream_id = sub.stream_id;

    // Update the left sidebar.
    stream_list.rename_stream(sub, new_name);

    // Update the default streams page in organization settings.
    exports.maybe_update_realm_default_stream_name(stream_id, new_name);

    // Update the stream settings
    stream_edit.update_stream_name(sub, new_name);

    // Update the subscriptions page
    var sub_row = row_for_stream_id(stream_id);
    sub_row.find(".stream-name").text(new_name);

    // Update the message feed.
    message_live_update.update_stream_name(stream_id, new_name);
};

exports.update_stream_description = function (sub, description, rendered_description) {
    sub.description = description;
    sub.rendered_description = rendered_description.replace('<p>', '').replace('</p>', '');

    // Update stream row
    var sub_row = row_for_stream_id(sub.stream_id);
    sub_row.find(".description").html(sub.rendered_description);

    // Update stream settings
    stream_edit.update_stream_description(sub);
};

exports.set_color = function (stream_id, color) {
    var sub = stream_data.get_sub_by_id(stream_id);
    stream_edit.set_stream_property(sub, 'color', color);
};

exports.rerender_subscribers_count = function (sub, just_subscribed) {
    if (!overlays.streams_open()) {
        // If the streams overlay isn't open, we don't need to rerender anything.
        return;
    }
    var stream_row = row_for_stream_id(sub.stream_id);
    stream_data.update_subscribers_count(sub);
    if (!sub.can_access_subscribers || just_subscribed && sub.invite_only) {
        var rendered_sub_count = templates.render("subscription_count", sub);
        stream_row.find('.subscriber-count').expectOne().html(rendered_sub_count);
    } else {
        stream_row.find(".subscriber-count-text").expectOne().text(sub.subscriber_count);
    }
};

exports.rerender_subscriptions_settings = function (sub) {
    // This rerendes the subscriber data for a given sub object
    // where it might have already been rendered in the subscriptions UI.
    if (typeof sub === "undefined") {
        blueslip.error('Undefined sub passed to function rerender_subscriptions_settings');
        return;
    }

    if (overlays.streams_open()) {
        // Render subscriptions templates only if subscription tab is open
        exports.rerender_subscribers_count(sub);
        if (stream_edit.is_sub_settings_active(sub)) {
            // Render subscriptions only if stream settings is open
            stream_edit.rerender_subscribers_list(sub);
        }
    }
};

function add_email_hint_handler() {
    // Add a popover explaining stream e-mail addresses on hover.

    $("body").on("mouseover", '.stream-email-hint', function (e) {
        var email_address_hint_content = templates.render('email_address_hint', { page_params: page_params });
        $(e.target).popover({
            placement: "right",
            title: "Email integration",
            content: email_address_hint_content,
            trigger: "manual",
            animation: false});
        $(e.target).popover('show');
        e.stopPropagation();
    });
    $("body").on("mouseout", '.stream-email-hint', function (e) {
        $(e.target).popover('hide');
        e.stopPropagation();
    });
}

exports.add_sub_to_table = function (sub) {
    if (exports.is_sub_already_present(sub)) {
        // If a stream is already listed/added in subscription modal,
        // return.  This can happen in some corner cases (which might
        // be backend bugs) where a realm adminsitrator is subscribed
        // to a private stream, in which case they might get two
        // stream-create events.
        return;
    }

    var html = templates.render('subscription', sub);
    var settings_html = templates.render('subscription_settings', sub);
    if (stream_create.get_name() === sub.name) {
        $(".streams-list").prepend(html).scrollTop(0);
    } else {
        $(".streams-list").append(html);
    }
    $(".subscriptions .settings").append($(settings_html));

    if (stream_create.get_name() === sub.name) {
        // This `stream_create.get_name()` check tells us whether the
        // stream was just created in this browser window; it's a hack
        // to work around the server_events code flow not having a
        // good way to associate with this request because the stream
        // ID isn't known yet.  These are appended to the top of the
        // list, so they are more visible.
        row_for_stream_id(sub.stream_id).click();
        stream_create.reset_created_stream();
    }
};

exports.is_sub_already_present = function (sub) {
    // This checks if a stream is already listed the "Manage streams"
    // UI, by checking for its subscribe/unsubscribe checkmark button.
    var button = check_button_for_sub(sub);
    if (button.length !== 0) {
        return true;
    }
    return false;
};

exports.remove_stream = function (stream_id) {
    // It is possible that row is empty when we deactivate a
    // stream, but we let jQuery silently handle that.
    var row = row_for_stream_id(stream_id);
    row.remove();
    var sub = stream_data.get_sub_by_id(stream_id);
    if (stream_edit.is_sub_settings_active(sub)) {
        exports.show_subs_pane.nothing_selected();
    }
};

exports.update_settings_for_subscribed = function (sub) {
    var button = check_button_for_sub(sub);
    var settings_button = settings_button_for_sub(sub).removeClass("unsubscribed").show();
    exports.update_add_subscriptions_elements(sub.can_add_subscribers);
    $(".subscription_settings[data-stream-id='" + sub.stream_id + "'] #preview-stream-button").show();

    if (button.length !== 0) {
        exports.rerender_subscribers_count(sub, true);

        button.toggleClass("checked");
        settings_button.text(i18n.t("Unsubscribe"));

        if (sub.can_change_stream_permissions) {
            $(".change-stream-privacy").show();
        }
    } else {
        exports.add_sub_to_table(sub);
    }

    if (stream_edit.is_sub_settings_active(sub)) {
        stream_edit.rerender_subscribers_list(sub);
    }

    // Display the swatch and subscription stream_settings
    stream_edit.show_sub_settings(sub);
};

exports.show_active_stream_in_left_panel = function () {
    var selected_row = get_hash_safe().split(/\//)[1];

    if (parseFloat(selected_row)) {
        var sub_row = row_for_stream_id(selected_row);
        sub_row.addClass("active");
    }
};

exports.add_tooltips_to_left_panel = function () {
    _.each($("#subscriptions_table .stream-row"), function (row) {
        $(row).find('.sub-info-box [class$="-bar"] [class$="-count"]').tooltip({
            placement: 'left', animation: false,
        });
    });
};

exports.update_add_subscriptions_elements = function (allow_user_to_add_subs) {
    if (page_params.is_guest) {
        // For guest users, we just hide the add_subscribers feature.
        $('.add_subscribers_container').hide();
        return;
    }

    // Otherwise, we adjust whether the widgets are disabled based on
    // whether this user is authorized to add subscribers.
    var input_element = $('.add_subscribers_container').find('input[name="principal"]').expectOne();
    var button_element = $('.add_subscribers_container').find('button[name="add_subscriber"]').expectOne();

    if (allow_user_to_add_subs) {
        input_element.removeAttr("disabled");
        button_element.removeAttr("disabled");
        button_element.css('pointer-events', "");
        $('.add_subscriber_btn_wrapper').popover('destroy');
    } else {
        input_element.attr("disabled", "disabled");
        button_element.attr("disabled", "disabled");

        // Disabled button blocks mouse events(hover) from reaching
        // to it's parent div element, so popover don't get triggered.
        // Add css to prevent this.
        button_element.css("pointer-events", "none");

        $('.add_subscribers_container input').popover({
            placement: "bottom",
            content: "<div class='cant_add_subs_hint'>%s</div>".replace(
                '%s', i18n.t('Only stream subscribers can add users to a private stream.')),
            trigger: "manual",
            html: true,
            animation: false});
        $('.add_subscribers_container').on('mouseover', function (e) {
            $('.add_subscribers_container input').popover('show');
            e.stopPropagation();
        });
        $('.add_subscribers_container').on('mouseout', function (e) {
            $('.add_subscribers_container input').popover('hide');
            e.stopPropagation();
        });
    }
};

exports.update_settings_for_unsubscribed = function (sub) {
    var button = check_button_for_sub(sub);
    var settings_button = settings_button_for_sub(sub).addClass("unsubscribed").show();

    button.toggleClass("checked");
    settings_button.text(i18n.t("Subscribe"));
    stream_edit.hide_sub_settings(sub);
    exports.rerender_subscriptions_settings(sub);

    stream_data.update_stream_email_address(sub, "");
    if (stream_edit.is_sub_settings_active(sub)) {
        // If user unsubscribed from private stream then user cannot subscribe to
        // stream without invitation and cannot add subscribers to stream.
        if (!sub.should_display_subscription_button) {
            settings_button.hide();
            exports.update_add_subscriptions_elements(sub.can_add_subscribers);
        }
    }

    // Remove private streams from subscribed streams list.
    if ($("#subscriptions_table .search-container .tab-switcher .first").hasClass("selected")
        && sub.invite_only) {
        var sub_row = row_for_stream_id(sub.stream_id);
        sub_row.addClass("notdisplayed");
    }
};

function triage_stream(query, sub) {
    if (query.subscribed_only) {
        // reject non-subscribed streams
        if (!sub.subscribed) {
            return 'rejected';
        }
    }

    var search_terms = search_util.get_search_terms(query.input);

    function match(attr) {
        var val = sub[attr];

        return search_util.vanilla_match({
            val: val,
            search_terms: search_terms,
        });
    }

    if (match('name')) {
        return 'name_match';
    }

    if (match('description')) {
        return 'desc_match';
    }

    return 'rejected';
}

function get_stream_id_buckets(stream_ids, query) {
    // When we simplify the settings UI, we can get
    // rid of the "others" bucket.

    var buckets = {
        name: [],
        desc: [],
        other: [],
    };

    _.each(stream_ids, function (stream_id) {
        var sub = stream_data.get_sub_by_id(stream_id);
        var match_status = triage_stream(query, sub);

        if (match_status === 'name_match') {
            buckets.name.push(stream_id);
        } else if (match_status === 'desc_match') {
            buckets.desc.push(stream_id);
        } else {
            buckets.other.push(stream_id);
        }
    });

    stream_data.sort_for_stream_settings(buckets.name);
    stream_data.sort_for_stream_settings(buckets.desc);

    return buckets;
}

exports.populate_stream_settings_left_panel = function () {
    var sub_rows = stream_data.get_updated_unsorted_subs();
    var template_data = {
        subscriptions: sub_rows,
    };
    var html = templates.render('subscriptions', template_data);
    $('#subscriptions_table .streams-list').html(html);
};

// query is now an object rather than a string.
// Query { input: String, subscribed_only: Boolean }
exports.filter_table = function (query) {
    exports.show_active_stream_in_left_panel();

    var widgets = {};
    var streams_list_scrolltop = $(".streams-list").scrollTop();

    var stream_ids = [];
    _.each($("#subscriptions_table .stream-row"), function (row) {
        var stream_id = $(row).attr('data-stream-id');
        stream_ids.push(stream_id);
    });

    var buckets = get_stream_id_buckets(stream_ids, query);

    // If we just re-built the DOM from scratch we wouldn't need
    // all this hidden/notdisplayed logic.
    var hidden_ids = {};
    _.each(buckets.other, function (stream_id) {
        hidden_ids[stream_id] = true;
    });

    _.each($("#subscriptions_table .stream-row"), function (row) {
        var stream_id = $(row).attr('data-stream-id');

        // Below code goes away if we don't do sort-DOM-in-place.
        if (hidden_ids[stream_id]) {
            $(row).addClass('notdisplayed');
        } else {
            $(row).removeClass('notdisplayed');
        }

        widgets[stream_id] = $(row).detach();
    });

    exports.add_tooltips_to_left_panel();

    ui.reset_scrollbar($("#subscription_overlay .streams-list"));

    var all_stream_ids = [].concat(
        buckets.name,
        buckets.desc,
        buckets.other
    );

    _.each(all_stream_ids, function (stream_id) {
        $('#subscriptions_table .streams-list').append(widgets[stream_id]);
    });

    exports.maybe_reset_right_panel();

    // this puts the scrollTop back to what it was before the list was updated again.
    $(".streams-list").scrollTop(streams_list_scrolltop);
};

var subscribed_only = true;

exports.get_search_params = function () {
    var search_box = $("#add_new_subscription input[type='text']");
    var input = search_box.expectOne().val().trim();
    var params = {
        input: input,
        subscribed_only: subscribed_only,
    };
    return params;
};

exports.maybe_reset_right_panel = function () {
    if ($(".stream-row.active").hasClass("notdisplayed")) {
        $(".right .settings").hide();
        $(".nothing-selected").show();
        $(".stream-row.active").removeClass("active");
    }
};

exports.actually_filter_streams = function () {
    var search_params = exports.get_search_params();
    exports.filter_table(search_params);
};

var filter_streams = _.throttle(exports.actually_filter_streams, 50);

// Make it explicit that our toggler is not created right away.
exports.toggler = undefined;

exports.switch_stream_tab = function (tab_name) {
    /*
        This switches the stream tab, but it doesn't update
        the toggler widget.  You may instead want to
        use `toggler.goto`.
    */

    if (tab_name === "all-streams") {
        subscribed_only = false;
    } else if (tab_name === "subscribed") {
        subscribed_only = true;
    }

    exports.actually_filter_streams();

    if (tab_name === "all-streams") {
        hashchange.update_browser_history('#streams/all');
    } else if (tab_name === "subscribed") {
        hashchange.update_browser_history('#streams/subscribed');
    }
};

exports.setup_page = function (callback) {
    // We should strongly consider only setting up the page once,
    // but I am writing these comments write before a big release,
    // so it's too risky a change for now.
    //
    // The history behind setting up the page from scratch every
    // time we go into "Manage Streams" is that we used to have
    // some live-update issues, so being able to re-launch the
    // streams page is kind of a workaround for those bugs, since
    // we will re-populate the widget.
    //
    // For now, every time we go back into the widget we'll
    // continue the strategy that we re-render everything from scratch.
    // Also, we'll always go back to the "Subscribed" tab.
    function initialize_components() {
        exports.toggler = components.toggle({
            child_wants_focus: true,
            values: [
                { label: i18n.t("Subscribed"), key: "subscribed" },
                { label: i18n.t("All streams"), key: "all-streams" },
            ],
            callback: function (value, key) {
                exports.switch_stream_tab(key);
            },
        });

        if (should_list_all_streams()) {
            var toggler_elem = exports.toggler.get();
            $("#subscriptions_table .search-container").prepend(toggler_elem);
        }

        // show the "Stream settings" header by default.
        $(".display-type #stream_settings_title").show();
    }

    function populate_and_fill() {

        $('#subscriptions_table').empty();

        var template_data = {
            can_create_streams: page_params.can_create_streams,
            hide_all_streams: !should_list_all_streams(),
            max_name_length: page_params.stream_name_max_length,
            max_description_length: page_params.stream_description_max_length,
            is_admin: page_params.is_admin,
        };

        var rendered = templates.render('subscription_table_body', template_data);
        $('#subscriptions_table').append(rendered);

        exports.populate_stream_settings_left_panel();
        initialize_components();
        exports.actually_filter_streams();
        stream_create.set_up_handlers();

        $("#add_new_subscription input[type='text']").on("input", function () {
            // Debounce filtering in case a user is typing quickly
            filter_streams();
        });

        if (callback) {
            callback();
        }
    }

    populate_and_fill();

    if (!should_list_all_streams()) {
        $('.create_stream_button').val(i18n.t("Subscribe"));
    }
};

exports.switch_to_stream_row = function (stream_id) {
    var stream_row = row_for_stream_id(stream_id);

    get_active_data().row.removeClass("active");
    stream_row.addClass("active");

    scroll_util.scroll_element_into_container(stream_row, stream_row.parent());

    // It's dubious that we need this timeout any more.
    setTimeout(function () {
        if (stream_id === get_active_data().id) {
            stream_row.click();
        }
    }, 100);
};

exports.change_state = function (section) {
    // if in #streams/new form.
    if (section === "new") {
        exports.do_open_create_stream();
        return;
    }

    if (section === "all") {
        exports.toggler.goto('all-streams');
        return;
    }

    if (section === "subscribed") {
        exports.toggler.goto('subscribed');
        return;
    }

    // if the section is a valid number.
    if (/\d+/.test(section)) {
        var stream_id = section;
        exports.switch_to_stream_row(stream_id);
        return;
    }

    blueslip.warn('invalid section for streams: ' + section);
    exports.toggler.goto('subscribed');
};

exports.launch = function (section) {
    exports.setup_page(function () {
        overlays.open_overlay({
            name: 'subscriptions',
            overlay: $("#subscription_overlay"),
            on_close: exports.close,
        });
        exports.change_state(section);

        ui.set_up_scrollbar($("#subscription_overlay .streams-list"));
        ui.set_up_scrollbar($("#subscription_overlay .settings"));

    });
    if (!get_active_data().id) {
        $('#search_stream_name').focus();
    }
};

exports.close = function () {
    hashchange.exit_overlay();
};

exports.switch_rows = function (event) {
    var active_data = get_active_data();
    var switch_row;
    if (window.location.hash === '#streams/new') {
        // Prevent switching stream rows when creating a new stream
        return false;
    } else if (!active_data.id || active_data.row.hasClass('notdisplayed')) {
        switch_row = $('div.stream-row:not(.notdisplayed):first');
        if ($('#search_stream_name').is(":focus")) {
            $('#search_stream_name').blur();
        }
    } else {
        if (event === 'up_arrow') {
            switch_row = active_data.row.prevAll().not('.notdisplayed').first();
        } else if (event === 'down_arrow') {
            switch_row = active_data.row.nextAll().not('.notdisplayed').first();
        }
        if ($('#search_stream_name').is(":focus")) {
            // remove focus from Filter streams input instead of switching rows
            // if Filter streams input is focused
            return $('#search_stream_name').blur();
        }
    }

    var row_data = get_row_data(switch_row);
    if (row_data) {
        var stream_id = row_data.id;
        exports.switch_to_stream_row(stream_id);
    } else if (event === 'up_arrow' && !row_data) {
        $('#search_stream_name').focus();
    }
    return true;
};

exports.keyboard_sub = function () {
    var active_data = get_active_data();
    var row_data = get_row_data(active_data.row);
    if (row_data) {
        subs.sub_or_unsub(row_data.object);
        if (row_data.object.subscribed && active_data.tab.text() === 'Subscribed') {
            active_data.row.addClass('notdisplayed');
            active_data.row.removeClass('active');
        }
    }
};

exports.toggle_view = function (event) {
    var active_data = get_active_data();

    if (event === 'right_arrow' && active_data.tab.text() === 'Subscribed') {
        exports.toggler.goto('all-streams');
    } else if (event === 'left_arrow' && active_data.tab.text() === 'All streams') {
        exports.toggler.goto('subscribed');
    }
};

exports.view_stream = function () {
    var active_data = get_active_data();
    var row_data = get_row_data(active_data.row);
    if (row_data) {
        var stream_narrow_hash = '#narrow/stream/' + hash_util.encode_stream_name(row_data.object.name);
        hashchange.go_to_location(stream_narrow_hash);
    }
};

function ajaxSubscribe(stream, color) {
    // Subscribe yourself to a single stream.
    var true_stream_name;

    return channel.post({
        url: "/json/users/me/subscriptions",
        data: {subscriptions: JSON.stringify([{name: stream, color: color}]) },
        success: function (resp, statusText, xhr) {
            if (overlays.streams_open()) {
                $("#create_stream_name").val("");
            }

            var res = JSON.parse(xhr.responseText);
            if (!$.isEmptyObject(res.already_subscribed)) {
                // Display the canonical stream capitalization.
                true_stream_name = res.already_subscribed[people.my_current_email()][0];
                ui_report.success(i18n.t("Already subscribed to __stream__", {stream: true_stream_name}),
                                  $(".stream_change_property_info"));
            }
            // The rest of the work is done via the subscribe event we will get
        },
        error: function (xhr) {
            ui_report.error(i18n.t("Error adding subscription"), xhr,
                            $(".stream_change_property_info"));
        },
    });
}

function ajaxUnsubscribe(sub) {
    // TODO: use stream_id when backend supports it
    return channel.del({
        url: "/json/users/me/subscriptions",
        data: {subscriptions: JSON.stringify([sub.name]) },
        success: function () {
            $(".stream_change_property_info").hide();
            // The rest of the work is done via the unsubscribe event we will get
        },
        error: function (xhr) {
            ui_report.error(i18n.t("Error removing subscription"), xhr,
                            $(".stream_change_property_info"));
        },
    });
}

exports.do_open_create_stream = function () {
    // Only call this directly for hash changes.
    // Prefer open_create_stream().

    var stream = $.trim($("#search_stream_name").val());

    if (!should_list_all_streams()) {
        // Realms that don't allow listing streams should simply be subscribed to.
        stream_create.set_name(stream);
        ajaxSubscribe($("#search_stream_name").val());
        return;
    }

    stream_create.new_stream_clicked(stream);
};

exports.open_create_stream = function () {
    exports.do_open_create_stream();
    hashchange.update_browser_history('#streams/new');
};


exports.sub_or_unsub = function (sub) {
    if (sub.subscribed) {
        ajaxUnsubscribe(sub);
    } else {
        ajaxSubscribe(sub.name, sub.color);
    }
};


exports.initialize = function () {
    stream_list.create_initial_sidebar_rows();

    // We build the stream_list now.  It may get re-built again very shortly
    // when new messages come in, but it's fairly quick.
    stream_list.build_stream_list();

    add_email_hint_handler();

    $("#subscriptions_table").on("click", ".create_stream_button", function (e) {
        e.preventDefault();
        exports.open_create_stream();
    });

    $(".subscriptions").on("click", "[data-dismiss]", function (e) {
        e.preventDefault();
        // we want to make sure that the click is not just a simulated
        // click; this fixes an issue where hitting "enter" would
        // trigger this code path due to bootstrap magic.
        if (e.clientY !== 0) {
            exports.show_subs_pane.nothing_selected();
        }
    });

    $("body").on("mouseover", ".subscribed-button", function (e) {
        $(e.target).addClass("btn-danger").text(i18n.t("Unsubscribe"));
    }).on("mouseout", ".subscribed-button", function (e) {
        $(e.target).removeClass("btn-danger").text(i18n.t("Subscribed"));
    });

    $("#subscriptions_table").on("click", ".email-address", function () {
        selectText(this);
    });

    $('.empty_feed_sub_unsub').click(function (e) {
        e.preventDefault();

        $('#subscription-status').hide();
        var stream_name = narrow_state.stream();
        if (stream_name === undefined) {
            return;
        }
        var sub = stream_data.get_sub(stream_name);
        exports.sub_or_unsub(sub);

        $('.empty_feed_notice').hide();
        $('#empty_narrow_message').show();
    });

    $("#subscriptions_table").on("click", ".stream-row, .create_stream_button", function () {
        $(".right").addClass("show");
        $(".subscriptions-header").addClass("slide-left");
    });

    $("#subscriptions_table").on("click", ".fa-chevron-left", function () {
        $(".right").removeClass("show");
        $(".subscriptions-header").removeClass("slide-left");
    });

    $("#subscriptions_table").on("click", ".sub_setting_checkbox", function (e) {
        var control = $(e.target).closest('.sub_setting_checkbox').find('.sub_setting_control');
        // A hack.  Don't change the state of the checkbox if we
        // clicked on the checkbox itself.
        if (control[0] !== e.target) {
            control.prop("checked", !control.prop("checked"));
        }
    });

    (function defocus_sub_settings() {
        var sel = ".search-container, .streams-list, .subscriptions-header";

        $("#subscriptions_table").on("click", sel, function (e) {
            if ($(e.target).is(sel)) {
                stream_edit.open_edit_panel_empty();
            }
        });
    }());

};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = subs;
}
window.subs = subs;
