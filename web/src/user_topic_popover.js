import $ from "jquery";

import render_change_visibility_policy_popover from "../templates/popovers/change_visibility_policy_popover.hbs";

import * as popover_menus from "./popover_menus";
import * as popover_menus_data from "./popover_menus_data";
import {parse_html} from "./ui_util";
import * as user_topics from "./user_topics";
import * as util from "./util";

export function initialize() {
    popover_menus.register_popover_menu(".change_visibility_policy", {
        theme: "popover-menu",
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

            instance.setContent(
                parse_html(
                    render_change_visibility_policy_popover(
                        popover_menus_data.get_change_visibility_policy_popover_content_context(
                            Number.parseInt(stream_id, 10),
                            topic_name,
                        ),
                    ),
                ),
            );
        },
        onMount(instance) {
            const $popper = $(instance.popper);
            const $elt = $(instance.reference).closest(".change_visibility_policy").expectOne();
            const stream_id = Number.parseInt($elt.attr("data-stream-id"), 10);
            const topic_name = $elt.attr("data-topic-name");

            if (!stream_id) {
                popover_menus.hide_current_popover_if_visible(instance);
                return;
            }

            $popper.on("change", "input[name='visibility-policy-select']", (e) => {
                const start_time = Date.now();

                const visibility_policy = Number.parseInt(
                    $(e.currentTarget).attr("data-visibility-policy"),
                    10,
                );

                const success_cb = () => {
                    setTimeout(
                        () => {
                            popover_menus.hide_current_popover_if_visible(instance);
                        },
                        util.get_remaining_time(start_time, 500),
                    );
                };

                const error_cb = () => {
                    const prev_visibility_policy = user_topics.get_topic_visibility_policy(
                        stream_id,
                        topic_name,
                    );
                    const $prev_visibility_policy_input = $(e.currentTarget)
                        .parent()
                        .find(`input[data-visibility-policy="${prev_visibility_policy}"]`);
                    setTimeout(
                        () => {
                            $prev_visibility_policy_input.prop("checked", true);
                        },
                        util.get_remaining_time(start_time, 500),
                    );
                };

                user_topics.set_user_topic_visibility_policy(
                    stream_id,
                    topic_name,
                    visibility_policy,
                    false,
                    false,
                    undefined,
                    success_cb,
                    error_cb,
                );
            });
        },
        onHidden(instance) {
            $(instance.reference)
                .closest(".change_visibility_policy")
                .expectOne()
                .removeClass("visibility-policy-popover-visible");
            instance.destroy();
            popover_menus.popover_instances.change_visibility_policy = undefined;

            // If the reference is in recent view / inbox, we would ideally restore focus
            // to the reference icon here but we don't do that because there are a lot of
            // reasons why the popover might be hidden (e.g. user clicking outside the popover).
        },
    });
}
