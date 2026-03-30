import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_left_sidebar_stream_setting_popover from "../templates/popovers/left_sidebar/left_sidebar_stream_setting_popover.hbs";

import * as channel from "./channel.ts";
import * as popover_menus from "./popover_menus.ts";
import * as settings_config from "./settings_config.ts";
import * as settings_data from "./settings_data.ts";
import {parse_html} from "./ui_util.ts";
import {user_settings} from "./user_settings.ts";

export function initialize(): void {
    popover_menus.register_popover_menu("#streams_inline_icon", {
        theme: "popover-menu",
        onShow(instance) {
            const can_create_streams =
                settings_data.user_can_create_private_streams() ||
                settings_data.user_can_create_public_streams() ||
                settings_data.user_can_create_web_public_streams();

            if (!can_create_streams) {
                // If the user can't create streams, we directly
                // navigate them to the Stream settings subscribe UI.
                window.location.assign("#channels/all");
                // Returning false from an onShow handler cancels the show.
                return false;
            }

            // Assuming that the instance can be shown, track and
            // prep the instance for showing
            popover_menus.popover_instances.stream_settings = instance;
            instance.setContent(
                parse_html(
                    render_left_sidebar_stream_setting_popover({
                        web_stream_unreads_count_display_policy_values:
                            settings_config.web_stream_unreads_count_display_policy_values,
                        web_channel_default_view_values:
                            settings_config.web_channel_default_view_values,
                    }),
                ),
            );
            popover_menus.on_show_prep(instance);

            const current_web_stream_unreads_count_display_policy =
                user_settings.web_stream_unreads_count_display_policy;
            const current_web_channel_default_view = user_settings.web_channel_default_view;

            const $popover_content = $(instance.popper);
            $popover_content
                .find(
                    `.web_stream_unreads_count_display_policy_choice[value=${current_web_stream_unreads_count_display_policy}]`,
                )
                .prop("checked", true);
            $popover_content
                .find(`.web_channel_default_view_choice[value=${current_web_channel_default_view}]`)
                .prop("checked", true);

            //  When showing the popover menu, we want the
            // "Add channels" and the "Filter channels" tooltip
            //  to appear below the "Add channels" icon.
            const add_streams_tooltip: tippy.ReferenceElement | undefined =
                $("#add_streams_tooltip").get(0);
            assert(add_streams_tooltip !== undefined);
            add_streams_tooltip._tippy?.setProps({
                placement: "bottom",
            });

            return undefined;
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.stream_settings = null;

            //  After the popover menu is closed, we want the
            //  "Add channels" and the "Filter channels" tooltip
            //  to appear at it's original position that is
            //  above the "Add channels" icon.
            const add_streams_tooltip: tippy.ReferenceElement | undefined =
                $("#add_streams_tooltip").get(0);
            assert(add_streams_tooltip !== undefined);
            add_streams_tooltip._tippy?.setProps({
                placement: "top",
            });
        },
    });

    $("body").on(
        "click",
        "#add-stream-menu-popover .web-stream-unreads-count-display-policy-option",
        function (this: HTMLElement) {
            const data = {web_stream_unreads_count_display_policy: $(this).val()};
            const current_value = user_settings.web_stream_unreads_count_display_policy;

            if (current_value === data.web_stream_unreads_count_display_policy) {
                popover_menus.popover_instances.stream_settings?.hide();
                return;
            }

            void channel.patch({
                url: "/json/settings",
                data,
                success() {
                    popover_menus.popover_instances.stream_settings?.hide();
                },
            });
        },
    );

    $("body").on(
        "click",
        "#add-stream-menu-popover .web-channel-default-view-option",
        function (this: HTMLElement) {
            const data = {web_channel_default_view: $(this).val()};
            const current_value = user_settings.web_channel_default_view;

            if (current_value === data.web_channel_default_view) {
                popover_menus.popover_instances.stream_settings?.hide();
                return;
            }

            void channel.patch({
                url: "/json/settings",
                data,
                success() {
                    popover_menus.popover_instances.stream_settings?.hide();
                },
            });
        },
    );
}
