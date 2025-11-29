import $ from "jquery";
import * as z from "zod/mini";

import render_message_hidden_dialog from "../templates/message_hidden_dialog.hbs";
import render_widgets_poll_widget from "../templates/widgets/poll_widget.hbs";
import render_widgets_poll_widget_results from "../templates/widgets/poll_widget_results.hbs";

import * as blueslip from "./blueslip.ts";
import {$t} from "./i18n.ts";
import * as keydown_util from "./keydown_util.ts";
import * as message_lists from "./message_lists.ts";
import type {Message} from "./message_store.ts";
import * as people from "./people.ts";
import type {
    InboundData,
    NewOptionOutboundData,
    QuestionOutboundData,
    VoteOutboundData,
} from "./poll_data.ts";
import {PollData} from "./poll_data.ts";
import type {WidgetExtraData} from "./widgetize.ts";

export type Event = {sender_id: number; data: InboundData};

export const poll_widget_extra_data_schema = z.object({
    question: z.optional(z.string()),
    options: z.optional(z.array(z.string())),
});

export type PollWidgetExtraData = z.infer<typeof poll_widget_extra_data_schema>;

export type PollWidgetOutboundData =
    | NewOptionOutboundData
    | QuestionOutboundData
    | VoteOutboundData;

export function activate({
    $elem,
    callback,
    extra_data,
    message,
}: {
    $elem: JQuery;
    callback: (data: PollWidgetOutboundData) => void;
    extra_data: WidgetExtraData;
    message: Message;
}): (events: Event[]) => void {
    const is_my_poll = people.is_my_user_id(message.sender_id);
    
    const parse_result = poll_widget_extra_data_schema.safeParse(extra_data);
    if (!parse_result.success) {
        blueslip.error("invalid poll widget extra data", {issues: parse_result.error.issues});
        return (_events: Event[]): void => {
            /* noop */
        };
    }
    const parsed_extra_data = parse_result.data;

    const poll_data = new PollData({
        message_sender_id: message.sender_id,
        current_user_id: people.my_current_user_id(),
        is_my_poll,
        question: parsed_extra_data.question ?? "",
        options: parsed_extra_data.options ?? [],
        comma_separated_names: people.get_full_names_for_poll_option,
        report_error_function: blueslip.warn,
    });
    const message_container = message_lists.current?.view.message_containers.get(message.id);

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
        
        // Show/hide edited marker
        const was_edited = message.last_edit_timestamp !== undefined;
        if (was_edited && message.last_edit_timestamp) {
            const edit_timestamp = message.last_edit_timestamp * 1000;
            const edit_date = new Date(edit_timestamp);
            const now = new Date();
            
            let time_str;
            const is_today = edit_date.toDateString() === now.toDateString();
            const time_format = edit_date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
            
            if (is_today) {
                time_str = `Last edited today at ${time_format}`;
            } else {
                const date_format = edit_date.toLocaleDateString();
                time_str = `Last edited on ${date_format} at ${time_format}`;
            }
            
            $elem.find(".poll-edited-marker").show();
            $elem.find(".poll-edited-marker").attr("title", time_str);
        } else {
            $elem.find(".poll-edited-marker").hide();
        }
        
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

        if (new_question.trim() === "") {
            new_question = old_question;
        }

        poll_data.set_question(new_question);
        render_question();

        if (new_question === old_question) {
            return;
        }

        // Update timestamp when question changes
        message.last_edit_timestamp = Date.now() / 1000;
        render_question();

        const data = poll_data.handle.question.outbound(new_question);
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

        const data = poll_data.handle.new_option.outbound(option);
        callback(data);
    }

    function submit_vote(key: string): void {
        const data = poll_data.handle.vote.outbound(key);
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

    const handle_events = function (events: Event[]): void {
        if (message_container?.is_hidden) {
            return;
        }

        for (const event of events) {
            poll_data.handle_event(event.sender_id, event.data);
        }

        render_question();
        render_results();
    };

    if (message_container?.is_hidden) {
        const html = render_message_hidden_dialog();
        $elem.html(html);
    } else {
        build_widget();
        render_question();
        render_results();
    }

    return handle_events;
}
