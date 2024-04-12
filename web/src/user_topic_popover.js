import $ from "jquery";

import render_change_visibility_policy_popover from "../templates/popovers/change_visibility_policy_popover.hbs";

import * as popover_menus from "./popover_menus";
import * as popover_menus_data from "./popover_menus_data";
import {parse_html} from "./ui_util";
import * as user_topics from "./user_topics";

export function initialize() {
    popover_menus.register_popover_menu(".change_visibility_policy", {
        placement: "bottom",
        popperOptions: {
            modifiers: [
                {
                    // The placement is set to bottom, but if that placement does not fit,
                    // the opposite top placement will be used.
                    name: "flip",
                    options: {
                        fallbackPlacements: ["top", "left"],
                    },
                },
            ],
        },
        onShow(instance) {
            popover_menus.popover_instances.change_visibility_policy = instance;
            popover_menus.on_show_prep(instance);
            const $elt = $(instance.reference).closest(".change_visibility_policy").expectOne();
            const stream_id = $elt.attr("data-stream-id");
            const topic_name = $elt.attr("data-topic-name");
            $elt.addClass("visibility-policy-popover-visible");

            instance.context =
                popover_menus_data.get_change_visibility_policy_popover_content_context(
                    Number.parseInt(stream_id, 10),
                    topic_name,
                );
            instance.setContent(
                parse_html(render_change_visibility_policy_popover(instance.context)),
            );
        },
        onMount(instance) {
            const $popper = $(instance.popper);
            const {stream_id, topic_name} = instance.context;

            if (!stream_id) {
                popover_menus.hide_current_popover_if_visible(instance);
                return;
            }

            // TODO: Figure out a good way to offer feedback if this request fails.
            $popper.on("click", ".visibility_policy_option", (e) => {
                $(".visibility_policy_option").removeClass("selected_visibility_policy");
                $(e.currentTarget).addClass("selected_visibility_policy");

                const visibility_policy = $(e.currentTarget).attr("data-visibility-policy");
                user_topics.set_user_topic_visibility_policy(
                    stream_id,
                    topic_name,
                    visibility_policy,
                );
                popover_menus.hide_current_popover_if_visible(instance);
            });
        },
        onHidden(instance) {
            $(instance.reference)
                .closest(".change_visibility_policy")
                .expectOne()
                .removeClass("visibility-policy-popover-visible");
            instance.destroy();
            popover_menus.popover_instances.change_visibility_policy = undefined;
        },
    });
}
