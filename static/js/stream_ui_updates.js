import render_subscription_type from "../templates/subscription_type.hbs";

import * as peer_data from "./peer_data";
import * as stream_data from "./stream_data";

export function initialize_disable_btn_hint_popover(
    btn_wrapper,
    popover_btn,
    disabled_btn,
    hint_text,
) {
    // Disabled button blocks mouse events(hover) from reaching
    // to it's parent div element, so popover don't get triggered.
    // Add css to prevent this.
    disabled_btn.css("pointer-events", "none");
    popover_btn.popover({
        placement: "bottom",
        content: $("<div>", {class: "sub_disable_btn_hint"}).text(hint_text).prop("outerHTML"),
        trigger: "manual",
        html: true,
        animation: false,
    });

    btn_wrapper.on("mouseover", (e) => {
        popover_btn.popover("show");
        e.stopPropagation();
    });

    btn_wrapper.on("mouseout", (e) => {
        popover_btn.popover("hide");
        e.stopPropagation();
    });
}

export function initialize_cant_subscribe_popover(sub) {
    const button_wrapper = stream_edit.settings_for_sub(sub).find(".sub_unsub_button_wrapper");
    const settings_button = subs.settings_button_for_sub(sub);
    initialize_disable_btn_hint_popover(
        button_wrapper,
        settings_button,
        settings_button,
        i18n.t("Only stream members can add users to a private stream"),
    );
}

export function update_settings_button_for_sub(sub) {
    // This is for the Subscribe/Unsubscribe button in the right panel.
    const settings_button = subs.settings_button_for_sub(sub);
    if (sub.subscribed) {
        settings_button.text(i18n.t("Unsubscribe")).removeClass("unsubscribed");
    } else {
        settings_button.text(i18n.t("Subscribe")).addClass("unsubscribed");
    }
    if (sub.should_display_subscription_button) {
        settings_button.prop("disabled", false);
        settings_button.popover("destroy");
        settings_button.css("pointer-events", "");
    } else {
        settings_button.attr("title", "");
        initialize_cant_subscribe_popover(sub);
        settings_button.prop("disabled", true);
    }
}

export function update_regular_sub_settings(sub) {
    // These are in the right panel.
    if (!stream_edit.is_sub_settings_active(sub)) {
        return;
    }
    const $settings = $(`.subscription_settings[data-stream-id='${CSS.escape(sub.stream_id)}']`);
    if (sub.subscribed) {
        if ($settings.find(".email-address").val().length === 0) {
            // Rerender stream email address, if not.
            $settings.find(".email-address").text(sub.email_address);
            $settings.find(".stream-email-box").show();
        }
        $settings.find(".regular_subscription_settings").addClass("in");
    } else {
        $settings.find(".regular_subscription_settings").removeClass("in");
        // Clear email address widget
        $settings.find(".email-address").html("");
    }
}

export function update_change_stream_privacy_settings(sub) {
    // This is in the right panel.
    const stream_privacy_btn = $(".change-stream-privacy");

    if (sub.can_change_stream_permissions) {
        stream_privacy_btn.show();
    } else {
        stream_privacy_btn.hide();
    }
}

export function update_notification_setting_checkbox(notification_name) {
    // This is in the right panel (Personal settings).
    const stream_row = $("#subscriptions_table .stream-row.active");
    if (!stream_row.length) {
        return;
    }
    const stream_id = stream_row.data("stream-id");
    $(`#${CSS.escape(notification_name)}_${CSS.escape(stream_id)}`).prop(
        "checked",
        stream_data.receives_notifications(stream_id, notification_name),
    );
}

export function update_stream_row_in_settings_tab(sub) {
    // This is in the left panel.
    // This function display/hide stream row in stream settings tab,
    // used to display immediate effect of add/removal subscription event.
    // If user is subscribed to stream, it will show sub row under
    // "Subscribed" tab, otherwise if stream is not public hide
    // stream row under tab.
    if (subs.is_subscribed_stream_tab_active()) {
        const sub_row = subs.row_for_stream_id(sub.stream_id);
        if (sub.subscribed) {
            sub_row.removeClass("notdisplayed");
        } else if (sub.invite_only || page_params.is_guest) {
            sub_row.addClass("notdisplayed");
        }
    }
}

export function update_stream_subscription_type_text(sub) {
    // This is in the right panel.
    const stream_settings = stream_edit.settings_for_sub(sub);
    const template_data = {
        ...sub,
        stream_post_policy_values: stream_data.stream_post_policy_values,
        message_retention_text: stream_edit.get_retention_policy_text_for_subscription_type(sub),
    };
    const html = render_subscription_type(template_data);
    if (stream_edit.is_sub_settings_active(sub)) {
        stream_settings.find(".subscription-type-text").expectOne().html(html);
    }
}

export function update_subscribers_list(sub) {
    // This is for the "Stream membership" section of the right panel.
    // Render subscriptions only if stream settings is open
    if (!stream_edit.is_sub_settings_active(sub)) {
        return;
    }

    if (!sub.can_access_subscribers) {
        $(".subscriber_list_settings_container").hide();
    } else {
        const subscribers = peer_data.get_subscribers(sub.stream_id);
        const users = stream_edit.get_users_from_subscribers(subscribers);

        /*
            We try to find a subscribers list that is already in the
            cache that list_widget.js maintains.  The list we are
            looking for would have been created in the function
            stream_edit.show_subscription_settings, using the same
            naming scheme as below for the `name` parameter.
        */
        const subscribers_list = ListWidget.get("stream_subscribers/" + sub.stream_id);

        // Changing the data clears the rendered list and the list needs to be re-rendered.
        // Perform re-rendering only when the stream settings form of the corresponding
        // stream is open.
        if (subscribers_list) {
            stream_edit.sort_but_pin_current_user_on_top(users);
            subscribers_list.replace_list_data(users);
        }
        $(".subscriber_list_settings_container").show();
    }
}

export function update_add_subscriptions_elements(sub) {
    if (!stream_edit.is_sub_settings_active(sub)) {
        return;
    }

    if (page_params.is_guest) {
        // For guest users, we just hide the add_subscribers feature.
        $(".add_subscribers_container").hide();
        return;
    }

    // Otherwise, we adjust whether the widgets are disabled based on
    // whether this user is authorized to add subscribers.
    const input_element = $(".add_subscribers_container").find(".input").expectOne();
    const button_element = $(".add_subscribers_container")
        .find('button[name="add_subscriber"]')
        .expectOne();
    const allow_user_to_add_subs = sub.can_add_subscribers;

    if (allow_user_to_add_subs) {
        input_element.prop("disabled", false);
        button_element.prop("disabled", false);
        button_element.css("pointer-events", "");
        $(".add_subscribers_container input").popover("destroy");
    } else {
        input_element.prop("disabled", true);
        button_element.prop("disabled", true);

        initialize_disable_btn_hint_popover(
            $(".add_subscribers_container"),
            input_element,
            button_element,
            i18n.t("Only stream members can add users to a private stream"),
        );
    }
}
