import $ from "jquery";
import assert from "minimalistic-assert";

import render_message_hidden_dialog from "../templates/message_hidden_dialog.hbs";
import render_widgets_poll_widget from "../templates/widgets/poll_widget.hbs";
import render_widgets_poll_widget_results from "../templates/widgets/poll_widget_results.hbs";

import * as blueslip from "./blueslip.ts";
import {$t} from "./i18n.ts";
import * as keydown_util from "./keydown_util.ts";
import type {Message} from "./message_store.ts";
import * as people from "./people.ts";
import type {PollWidgetOutboundData} from "./poll_data.ts";
import {PollData, new_option_schema, question_schema, vote_schema} from "./poll_data.ts";
import {ZulipWidgetContext} from "./widget_context.ts";
import type {Event} from "./widget_data.ts";
import type {AnyWidgetData} from "./widget_schema.ts";

export function activate({
    $elem,
    callback,
    any_data,
    message,
}: {
    $elem: JQuery;
    callback: (data: PollWidgetOutboundData) => void;
    any_data: AnyWidgetData;
    message: Message;
}): (events: Event[]) => void {
    assert(any_data.widget_type === "poll");
    const {extra_data} = any_data;
    const widget_context = new ZulipWidgetContext(message);
    const container_is_hidden = widget_context.is_container_hidden();
    const is_my_poll = widget_context.is_my_poll();
    const poll_owner_user_id = widget_context.owner_user_id();

    const poll_data = new PollData({
        message_sender_id: poll_owner_user_id,
        current_user_id: people.my_current_user_id(),
        is_my_poll,
        question: extra_data.question ?? "",
        options: extra_data.options ?? [],
        comma_separated_names: people.get_full_names_for_poll_option,
        report_error_function: blueslip.warn,
    });

    function update_edit_controls(): void {
        const has_question =
            $elem.find<HTMLInputElement>("input.poll-question").val()!.trim() !== "";
        $elem.find("button.poll-question-check").toggle(has_question);
    }

    function render_question(): void {
        const question = poll_data.get_question();
        const input_mode = poll_data.get_input_mode();
        const can_edit = is_my_poll && !input_mode;
        const has_question = question.trim() !== "";
        const waiting = !is_my_poll && !has_question;

        $elem.find(".poll-question-header").toggle(!input_mode);
        $elem.find(".poll-question-header").text(question);
        $elem.find(".poll-edit-question").toggle(can_edit);
        update_edit_controls();

        $elem.find(".poll-question-bar").toggle(input_mode);
        $elem.find(".poll-option-bar").show();

        $elem.find(".poll-please-wait").toggle(waiting);
    }

    function start_editing(): void {
        poll_data.set_input_mode();

        const question = poll_data.get_question();
        $elem.find("input.poll-question").val(question);
        render_question();
        $elem.find("input.poll-question").trigger("focus");
    }

    function abort_edit(): void {
        poll_data.clear_input_mode();
        render_question();
    }

    function submit_question(): void {
        const $poll_question_input = $elem.find<HTMLInputElement>("input.poll-question");
        let new_question = $poll_question_input.val()!.trim();
        const old_question = poll_data.get_question();

        // We should disable the button for blank questions,
        // so this is just defensive code.
        if (new_question.trim() === "") {
            new_question = old_question;
        }

        // Optimistically set the question locally.
        poll_data.set_question(new_question);
        render_question();

        // If there were no actual edits, we can exit now.
        if (new_question === old_question) {
            return;
        }

        // Broadcast the new question to our peers.
        const data = poll_data.question_event(new_question);
        if (data) {
            callback(data);
        }
    }

    function submit_option(): void {
        const $poll_option_input = $elem.find<HTMLInputElement>("input.poll-option");
        const option = $poll_option_input.val()!.trim();
        const options = poll_data.get_widget_data().options;

        if (poll_data.is_option_present(options, option)) {
            return;
        }

        if (option === "") {
            return;
        }

        $poll_option_input.val("").trigger("focus");

        const data = poll_data.new_option_event(option);
        callback(data);
    }

    function submit_vote(key: string): void {
        const data = poll_data.vote_event(key);
        callback(data);
    }

    function build_widget(): void {
        const html = render_widgets_poll_widget({});
        $elem.html(html);

        $elem.find("input.poll-question").on("keyup", (e) => {
            e.stopPropagation();
            update_edit_controls();
        });

        $elem.find("input.poll-question").on("keydown", (e) => {
            e.stopPropagation();

            if (keydown_util.is_enter_event(e)) {
                submit_question();
                return;
            }

            if (e.key === "Escape") {
                abort_edit();
                return;
            }
        });

        $elem.find(".poll-edit-question").on("click", (e) => {
            e.stopPropagation();
            start_editing();
        });

        $elem.find("button.poll-question-check").on("click", (e) => {
            e.stopPropagation();
            submit_question();
        });

        $elem.find("button.poll-question-remove").on("click", (e) => {
            e.stopPropagation();
            abort_edit();
        });

        $elem.find("button.poll-option").on("click", (e) => {
            e.stopPropagation();
            check_option_button();
            submit_option();
        });

        $elem.find("input.poll-option").on("keyup", (e) => {
            e.stopPropagation();
            check_option_button();

            if (keydown_util.is_enter_event(e)) {
                submit_option();
                return;
            }

            if (e.key === "Escape") {
                $("input.poll-option").val("");
                return;
            }
        });
    }

    function check_option_button(): void {
        const $poll_option_input = $elem.find<HTMLInputElement>("input.poll-option");
        const option = $poll_option_input.val()!.trim();
        const options = poll_data.get_widget_data().options;

        if (poll_data.is_option_present(options, option)) {
            $elem.find("button.poll-option").prop("disabled", true);
            $elem
                .find("button.poll-option")
                .attr("title", $t({defaultMessage: "Option already present."}));
        } else {
            $elem.find("button.poll-option").prop("disabled", false);
            $elem.find("button.poll-option").removeAttr("title");
        }
    }

    function render_results(): void {
        const widget_data = poll_data.get_widget_data();

        const html = render_widgets_poll_widget_results(widget_data);
        $elem.find("ul.poll-widget").html(html);

        $elem
            .find("button.poll-vote")
            .off("click")
            .on("click", (e) => {
                e.stopPropagation();
                const key = $(e.target).attr("data-key")!;
                submit_vote(key);
            });
    }

    function update_state_from_event(sender_id: number, data: unknown): void {
        assert(
            typeof data === "object" &&
                data !== null &&
                "type" in data &&
                typeof data.type === "string",
        );
        const type = data.type;
        switch (type) {
            case "new_option": {
                poll_data.handle_new_option_event(sender_id, new_option_schema.parse(data));
                break;
            }
            case "question": {
                poll_data.handle_question_event(sender_id, question_schema.parse(data));
                break;
            }
            case "vote": {
                poll_data.handle_vote_event(sender_id, vote_schema.parse(data));
                break;
            }
            default: {
                blueslip.warn(`poll widget: unknown inbound type: ${type}`);
            }
        }
    }

    function handle_events(events: Event[]): void {
        // We don't have to handle events now since we go through
        // handle_event loop again when we unmute the message.
        if (container_is_hidden) {
            return;
        }

        for (const event of events) {
            update_state_from_event(event.sender_id, event.data);
        }

        render_question();
        render_results();
    }

    if (container_is_hidden) {
        const html = render_message_hidden_dialog();
        $elem.html(html);
    } else {
        build_widget();
        render_question();
        render_results();
    }

    return handle_events;
}
