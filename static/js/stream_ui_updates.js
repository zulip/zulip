var render_subscription_count = require("../templates/subscription_count.hbs");
var render_subscription_setting_icon = require('../templates/subscription_setting_icon.hbs');
var render_subscription_type = require('../templates/subscription_type.hbs');

exports.update_check_button_for_sub = function (sub) {
    var button = subs.check_button_for_sub(sub);
    if (sub.subscribed) {
        button.addClass("checked");
    } else {
        button.removeClass("checked");
    }
    if (sub.should_display_subscription_button) {
        button.removeClass("disabled");
    } else {
        button.addClass("disabled");
    }
};

exports.initialize_disable_btn_hint_popover = function (btn_wrapper, popover_btn,
                                                        disabled_btn, hint_text) {
    // Disabled button blocks mouse events(hover) from reaching
    // to it's parent div element, so popover don't get triggered.
    // Add css to prevent this.
    disabled_btn.css("pointer-events", "none");
    popover_btn.popover({
        placement: "bottom",
        content: $("<div>", {class: "sub_disable_btn_hint"}).text(hint_text)
            .prop("outerHTML"),
        trigger: "manual",
        html: true,
        animation: false,
    });

    btn_wrapper.on('mouseover', function (e) {
        popover_btn.popover('show');
        e.stopPropagation();
    });

    btn_wrapper.on('mouseout', function (e) {
        popover_btn.popover('hide');
        e.stopPropagation();
    });
};

exports.initialize_cant_subscribe_popover = function (sub) {
    var button_wrapper = stream_edit.settings_for_sub(sub).find('.sub_unsub_button_wrapper');
    var settings_button = subs.settings_button_for_sub(sub);
    exports.initialize_disable_btn_hint_popover(button_wrapper, settings_button, settings_button,
                                                i18n.t("Only stream members can add users to a private stream"));
};

exports.update_settings_button_for_sub = function (sub) {
    var settings_button = subs.settings_button_for_sub(sub);
    if (sub.subscribed) {
        settings_button.text(i18n.t("Unsubscribe")).removeClass("unsubscribed");
    } else {
        settings_button.text(i18n.t("Subscribe")).addClass("unsubscribed");
    }
    if (sub.should_display_subscription_button) {
        settings_button.prop("disabled", false);
        settings_button.popover('destroy');
        settings_button.css("pointer-events", "");
    } else {
        settings_button.attr("title", "");
        exports.initialize_cant_subscribe_popover(sub);
        settings_button.attr("disabled", "disabled");
    }
};

exports.update_regular_sub_settings = function (sub) {
    if (!stream_edit.is_sub_settings_active(sub)) {
        return;
    }
    var $settings = $(".subscription_settings[data-stream-id='" + sub.stream_id + "']");
    if (sub.subscribed) {
        if ($settings.find(".email-address").val().length === 0) {
            // Rerender stream email address, if not.
            $settings.find(".email-address").text(sub.email_address);
            $settings.find(".stream-email-box").show();
        }
        $settings.find(".regular_subscription_settings").addClass('in');
    } else {
        $settings.find(".regular_subscription_settings").removeClass('in');
        // Clear email address widget
        $settings.find(".email-address").html("");
    }
};

exports.update_change_stream_privacy_settings = function (sub) {
    var stream_privacy_btn = $(".change-stream-privacy");

    if (sub.can_change_stream_permissions) {
        stream_privacy_btn.show();
    } else {
        stream_privacy_btn.hide();
    }
};

exports.update_stream_row_in_settings_tab = function (sub) {
    // This function display/hide stream row in stream settings tab,
    // used to display immediate effect of add/removal subscription event.
    // If user is subscribed to stream, it will show sub row under
    // "Subscribed" tab, otherwise if stream is not public hide
    // stream row under tab.
    if (subs.is_subscribed_stream_tab_active()) {
        var sub_row = subs.row_for_stream_id(sub.stream_id);
        if (sub.subscribed) {
            sub_row.removeClass("notdisplayed");
        } else if (sub.invite_only || page_params.is_guest) {
            sub_row.addClass("notdisplayed");
        }
    }
};

exports.update_stream_privacy_type_icon = function (sub) {
    var stream_settings = stream_edit.settings_for_sub(sub);
    var sub_row = subs.row_for_stream_id(sub.stream_id);
    var html = render_subscription_setting_icon(sub);

    if (overlays.streams_open()) {
        sub_row.find('.icon').expectOne().replaceWith($(html));
    }
    if (stream_edit.is_sub_settings_active(sub)) {
        var large_icon = stream_settings.find('.large-icon').expectOne();
        if (sub.invite_only) {
            large_icon.removeClass("hash").addClass("lock")
                .html("<i class='fa fa-lock' aria-hidden='true'></i>");
        } else {
            large_icon.addClass("hash").removeClass("lock").html("");
        }
    }
};

exports.update_stream_privacy_type_text = function (sub) {
    var stream_settings = stream_edit.settings_for_sub(sub);
    var html = render_subscription_type(sub);
    if (stream_edit.is_sub_settings_active(sub)) {
        stream_settings.find('.subscription-type-text').expectOne().html(html);
    }
};

exports.update_subscribers_count = function (sub, just_subscribed) {
    if (!overlays.streams_open()) {
        // If the streams overlay isn't open, we don't need to rerender anything.
        return;
    }
    var stream_row = subs.row_for_stream_id(sub.stream_id);
    if (!sub.can_access_subscribers || just_subscribed && sub.invite_only || page_params.is_guest) {
        var rendered_sub_count = render_subscription_count(sub);
        stream_row.find('.subscriber-count').expectOne().html(rendered_sub_count);
    } else {
        stream_row.find(".subscriber-count-text").expectOne().text(sub.subscriber_count);
    }
};

exports.update_subscribers_list = function (sub) {
    // Render subscriptions only if stream settings is open
    if (!stream_edit.is_sub_settings_active(sub)) {
        return;
    }

    if (!sub.can_access_subscribers) {
        $(".subscriber_list_settings_container").hide();
    } else {
        var emails = stream_edit.get_email_of_subscribers(sub.subscribers);
        var subscribers_list = list_render.get("stream_subscribers/" + sub.stream_id);

        // Changing the data clears the rendered list and the list needs to be re-rendered.
        // Perform re-rendering only when the stream settings form of the corresponding
        // stream is open.
        if (subscribers_list) {
            stream_edit.sort_but_pin_current_user_on_top(emails);
            subscribers_list.data(emails);
            subscribers_list.render();
        }
        $(".subscriber_list_settings_container").show();
    }
};

exports.update_add_subscriptions_elements = function (sub) {
    if (!stream_edit.is_sub_settings_active(sub)) {
        return;
    }

    if (page_params.is_guest) {
        // For guest users, we just hide the add_subscribers feature.
        $('.add_subscribers_container').hide();
        return;
    }

    // Otherwise, we adjust whether the widgets are disabled based on
    // whether this user is authorized to add subscribers.
    var input_element = $('.add_subscribers_container').find('input[name="principal"]').expectOne();
    var button_element = $('.add_subscribers_container').find('button[name="add_subscriber"]').expectOne();
    var allow_user_to_add_subs = sub.can_add_subscribers;

    if (allow_user_to_add_subs) {
        input_element.removeAttr("disabled");
        button_element.removeAttr("disabled");
        button_element.css('pointer-events', "");
        $('.add_subscribers_container input').popover('destroy');
    } else {
        input_element.attr("disabled", "disabled");
        button_element.attr("disabled", "disabled");

        exports.initialize_disable_btn_hint_popover($('.add_subscribers_container'), input_element, button_element,
                                                    i18n.t("Only stream members can add users to a private stream"));
    }
};

window.stream_ui_updates = exports;
