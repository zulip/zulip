import $ from "jquery";
import {z} from "zod";

import render_unsubscribe_private_stream_modal from "../templates/confirm_dialog/confirm_unsubscribe_private_stream.hbs";
import render_inline_decorated_stream_name from "../templates/inline_decorated_stream_name.hbs";
import render_selected_stream_title from "../templates/stream_settings/selected_stream_title.hbs";

import * as channel from "./channel.ts";
import * as confirm_dialog from "./confirm_dialog.ts";
import * as hash_util from "./hash_util.ts";
import {$t, $t_html} from "./i18n.ts";
import * as loading from "./loading.ts";
import * as overlays from "./overlays.ts";
import * as peer_data from "./peer_data.ts";
import * as settings_config from "./settings_config.ts";
import * as settings_data from "./settings_data.ts";
import {current_user} from "./state_data.ts";
import * as stream_ui_updates from "./stream_ui_updates.ts";
import type {StreamSubscription} from "./sub_store.ts";
import * as ui_report from "./ui_report.ts";

export function set_right_panel_title(sub: StreamSubscription): void {
    let title_icon_color = "#333333";
    if (settings_data.using_dark_theme()) {
        title_icon_color = "#dddeee";
    }

    const preview_url = hash_util.by_stream_url(sub.stream_id);
    $("#subscription_overlay .stream-info-title").html(
        render_selected_stream_title({sub, title_icon_color, preview_url}),
    );
}

export const show_subs_pane = {
    nothing_selected(): void {
        $(".settings, #stream-creation").hide();
        $(".nothing-selected").show();
        $("#subscription_overlay .stream-info-title").text(
            $t({defaultMessage: "Channel settings"}),
        );
    },
    settings(sub: StreamSubscription): void {
        $(".settings, #stream-creation").hide();
        $(".settings").show();
        set_right_panel_title(sub);
    },
    create_stream(
        container_name = "configure_channel_settings",
        sub?: {
            name: string;
            invite_only: boolean;
            is_web_public: boolean;
        },
    ): void {
        $(".stream_creation_container").hide();
        if (container_name === "configure_channel_settings") {
            $("#subscription_overlay .stream-info-title").text(
                $t({defaultMessage: "Configure new channel settings"}),
            );
        } else {
            $("#subscription_overlay .stream-info-title").html(
                render_selected_stream_title({
                    sub: sub ?? {
                        name: "",
                        invite_only: false,
                        is_web_public: false,
                    },
                }),
            );
        }
        update_footer_buttons(container_name);
        $(`.${CSS.escape(container_name)}`).show();
        $(".nothing-selected, .settings, #stream-creation").hide();
        $("#stream-creation").show();
    },
};

export function update_footer_buttons(container_name: string): void {
    if (container_name === "subscribers_container") {
        // Hide stream creation containers and show add subscriber container
        $(".finalize_create_stream").show();
        $("#stream_creation_go_to_subscribers").hide();
        $("#stream_creation_go_to_configure_channel_settings").show();
    } else {
        // Hide add subscriber container and show stream creation containers
        $(".finalize_create_stream").hide();
        $("#stream_creation_go_to_subscribers").show();
        $("#stream_creation_go_to_configure_channel_settings").hide();
    }
}

export function get_active_data(): {
    $row: JQuery;
    id: number;
    $tabs: JQuery;
} {
    const $active_row = $("div.stream-row.active");
    const valid_active_id = Number.parseInt($active_row.attr("data-stream-id")!, 10);
    const $active_tabs = $(".subscriptions-container").find("div.ind-tab.selected");
    return {
        $row: $active_row,
        id: valid_active_id,
        $tabs: $active_tabs,
    };
}

/* For the given stream_row, remove the tick and replace by a spinner. */
function display_subscribe_toggle_spinner($stream_row: JQuery): void {
    /* Prevent sending multiple requests by removing the button class. */
    $stream_row.find(".check").removeClass("sub_unsub_button");

    /* Hide the tick. */
    const $tick = $stream_row.find("svg");
    $tick.addClass("hide");

    /* Add a spinner to show the request is in process. */
    const $spinner = $stream_row.find(".sub_unsub_status").expectOne();
    $spinner.show();
    loading.make_indicator($spinner);
}

/* For the given stream_row, add the tick and delete the spinner. */
function hide_subscribe_toggle_spinner($stream_row: JQuery): void {
    /* Re-enable the button to handle requests. */
    $stream_row.find(".check").addClass("sub_unsub_button");

    /* Show the tick. */
    const $tick = $stream_row.find("svg");
    $tick.removeClass("hide");

    /* Destroy the spinner. */
    const $spinner = $stream_row.find(".sub_unsub_status").expectOne();
    loading.destroy_indicator($spinner);
}

export function ajaxSubscribe(
    stream: string,
    color: string | undefined = undefined,
    $stream_row: JQuery | undefined = undefined,
): void {
    // Subscribe yourself to a single stream.
    let true_stream_name;

    if ($stream_row !== undefined) {
        display_subscribe_toggle_spinner($stream_row);
    }
    void channel.post({
        url: "/json/users/me/subscriptions",
        data: {subscriptions: JSON.stringify([{name: stream, color}])},
        success(_resp, _statusText, xhr) {
            if (overlays.streams_open()) {
                $("#create_stream_name").val("");
            }

            const res = z
                .object({
                    already_subscribed: z.record(z.string(), z.array(z.string())),
                })
                .parse(xhr.responseJSON);
            if (Object.keys(res.already_subscribed).length > 0) {
                // Display the canonical stream capitalization.
                true_stream_name = res.already_subscribed[current_user.user_id]![0];
                ui_report.success(
                    $t_html(
                        {defaultMessage: "Already subscribed to {channel}"},
                        {channel: true_stream_name},
                    ),
                    $(".stream_change_property_info"),
                );
            }
            // The rest of the work is done via the subscribe event we will get

            if ($stream_row !== undefined) {
                hide_subscribe_toggle_spinner($stream_row);
            }
        },
        error(xhr) {
            if ($stream_row !== undefined) {
                hide_subscribe_toggle_spinner($stream_row);
            }
            ui_report.error(
                $t_html({defaultMessage: "Error adding subscription"}),
                xhr,
                $(".stream_change_property_info"),
            );
        },
    });
}

function ajaxUnsubscribe(sub: StreamSubscription, $stream_row: JQuery | undefined): void {
    // TODO: use stream_id when backend supports it
    if ($stream_row !== undefined) {
        display_subscribe_toggle_spinner($stream_row);
    }
    void channel.del({
        url: "/json/users/me/subscriptions",
        data: {subscriptions: JSON.stringify([sub.name])},
        success() {
            $(".stream_change_property_info").hide();
            // The rest of the work is done via the unsubscribe event we will get

            if ($stream_row !== undefined) {
                hide_subscribe_toggle_spinner($stream_row);
            }
        },
        error(xhr) {
            if ($stream_row !== undefined) {
                hide_subscribe_toggle_spinner($stream_row);
            }
            ui_report.error(
                $t_html({defaultMessage: "Error removing subscription"}),
                xhr,
                $(".stream_change_property_info"),
            );
        },
    });
}

export function unsubscribe_from_private_stream(sub: StreamSubscription): void {
    const invite_only = sub.invite_only;
    const sub_count = peer_data.get_subscriber_count(sub.stream_id);
    const stream_name_with_privacy_symbol_html = render_inline_decorated_stream_name({stream: sub});

    const html_body = render_unsubscribe_private_stream_modal({
        unsubscribing_other_user: false,
        display_stream_archive_warning: sub_count === 1 && invite_only,
    });

    function unsubscribe_from_stream(): void {
        let $stream_row;
        if (overlays.streams_open()) {
            $stream_row = $(
                "#channels_overlay_container div.stream-row[data-stream-id='" +
                    sub.stream_id +
                    "']",
            );
        }

        ajaxUnsubscribe(sub, $stream_row);
    }

    confirm_dialog.launch({
        html_heading: $t_html(
            {defaultMessage: "Unsubscribe from <z-link></z-link>?"},
            {"z-link": () => stream_name_with_privacy_symbol_html},
        ),
        html_body,
        on_click: unsubscribe_from_stream,
    });
}

export function sub_or_unsub(
    sub: StreamSubscription,
    $stream_row: JQuery | undefined = undefined,
): void {
    if (sub.subscribed) {
        // TODO: This next line should allow guests to access web-public streams.
        if (sub.invite_only || current_user.is_guest) {
            unsubscribe_from_private_stream(sub);
            return;
        }
        ajaxUnsubscribe(sub, $stream_row);
    } else {
        ajaxSubscribe(sub.name, sub.color, $stream_row);
    }
}

export function update_public_stream_privacy_option_state($container: JQuery): void {
    const $public_stream_elem = $container.find(
        `input[value='${CSS.escape(settings_config.stream_privacy_policy_values.public.code)}']`,
    );
    $public_stream_elem.prop("disabled", !settings_data.user_can_create_public_streams());
}

export function hide_or_disable_stream_privacy_options_if_required($container: JQuery): void {
    stream_ui_updates.update_web_public_stream_privacy_option_state($container);

    update_public_stream_privacy_option_state($container);

    stream_ui_updates.update_private_stream_privacy_option_state($container);
}
