import $ from "jquery";

import render_stream_settings_archived_channel_popover from "../templates/popovers/stream_settings_archived_channel_popover.hbs";

import * as popover_menus from "./popover_menus.ts";
import * as settings_data from "./settings_data.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_settings_ui from "./stream_settings_ui.ts";
import {parse_html} from "./ui_util.ts";

export function initialize(): void {
    popover_menus.register_popover_menu("#more_options_stream", {
        theme: "popover-menu",
        onShow(instance) {
            const parsedContent = parse_html(
                render_stream_settings_archived_channel_popover({
                    archived_channels_visible: settings_data.is_archived_channels_visible(),
                }),
            );

            instance.setContent(parsedContent);

            popover_menus.on_show_prep(instance);
            return undefined;
        },
        onMount(instance) {
            const $popper = $(instance.popper);
            $popper.on("click", "#stream-settings-archived-channels-label-container", (e) => {
                e.preventDefault();
                settings_data.toggle_archived_channels();
                const archived_subs = stream_data.get_archived_subs();
                for (const sub of archived_subs) {
                    stream_settings_ui.add_sub_to_table(sub);
                }
                stream_settings_ui.redraw_left_panel();
                popover_menus.hide_current_popover_if_visible(instance);
            });
        },
        onHidden(instance) {
            instance.destroy();
        },
    });
}
