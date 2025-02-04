import $ from "jquery";
import assert from "minimalistic-assert";

import render_stream_card_popover from "../templates/popovers/stream_card_popover.hbs";

import * as browser_history from "./browser_history.ts";
import * as hash_util from "./hash_util.ts";
import * as modals from "./modals.ts";
import * as peer_data from "./peer_data.ts";
import * as popover_menus from "./popover_menus.ts";
import * as stream_data from "./stream_data.ts";
import * as sub_store from "./sub_store.ts";
import * as ui_util from "./ui_util.ts";

let stream_id: number | undefined;

export function initialize(): void {
    popover_menus.register_popover_menu(".pill[data-stream-id]", {
        theme: "popover-menu",
        placement: "right",
        onShow(instance) {
            popover_menus.popover_instances.stream_card_popover = instance;
            popover_menus.on_show_prep(instance);

            const $elt = $(instance.reference);
            const stream_id_str = $elt.attr("data-stream-id");
            assert(stream_id_str !== undefined);
            stream_id = Number.parseInt(stream_id_str, 10);
            const subscribers_count = peer_data.get_subscriber_count(stream_id);

            instance.setContent(
                ui_util.parse_html(
                    render_stream_card_popover({
                        stream: {
                            ...sub_store.get(stream_id),
                        },
                        subscribers_count,
                    }),
                ),
            );
        },
        onMount(instance) {
            const $popper = $(instance.popper);

            // Stream settings
            $popper.on("click", ".open_stream_settings", () => {
                assert(stream_id !== undefined);
                const sub = sub_store.get(stream_id);
                assert(sub !== undefined);
                popover_menus.hide_current_popover_if_visible(instance);
                // modals.close_active_if_any() is mainly used to handle navigation to channel settings
                // using the popover that is opened when clicking on channel pills in the invite user modal.
                modals.close_active_if_any();
                const can_change_stream_permissions =
                    stream_data.can_change_permissions_requiring_metadata_access(sub);
                let stream_edit_hash = hash_util.channels_settings_edit_url(sub, "general");
                if (!can_change_stream_permissions) {
                    stream_edit_hash = hash_util.channels_settings_edit_url(sub, "personal");
                }
                browser_history.go_to_location(stream_edit_hash);
            });
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.stream_card_popover = null;
        },
    });
}
