import $ from "jquery";
import assert from "minimalistic-assert";

import {PollData} from "../shared/src/poll_data";
import type {InboundData, PollOptionData} from "../shared/src/poll_data";
import render_widgets_poll_widget from "../templates/widgets/poll_widget.hbs";
import render_widgets_poll_widget_results from "../templates/widgets/poll_widget_results.hbs";

import * as blueslip from "./blueslip";
import {$t} from "./i18n";
import * as keydown_util from "./keydown_util";
import * as people from "./people";
import type {Message} from "./types";

type PollOptions = {
    $elem: JQuery;
    callback: (data: unknown) => void;
    extra_data?: {
        question?: string;
        options?: string[];
    };
    message: Message;
};

// PollEventType for handling the Event type.
type PollEventType = {
    sender_id: number;
    data: InboundData;
};

type CustomPollJQuery = JQuery<HTMLElement> & {
    handle_events?: (events: PollEventType[]) => void;
};

export function activate({
    $elem,
    callback,
    extra_data: {question = "", options = []} = {},
    message,
}: PollOptions): void {
    const is_my_poll = people.is_my_user_id(message.sender_id);
    const poll_data = new PollData({
        message_sender_id: message.sender_id,
        current_user_id: people.my_current_user_id(),
        is_my_poll,
        question,
        options,
        comma_separated_names: people.get_full_names_for_poll_option,
        report_error_function: blueslip.warn,
    });

    function update_edit_controls(): void {
        const has_question: boolean =
            ($elem.find("input.poll-question").val() as string)?.trim() !== "";
        $elem.find("button.poll-question-check").toggle(has_question);
    }

    function render_question(): void {
        const question: string = poll_data.get_question();
        const input_mode: boolean = poll_data.get_input_mode();
        const can_edit: boolean = is_my_poll && !input_mode;
        const has_question: boolean = question.trim() !== "";
        const can_vote: boolean = has_question;
        const waiting: boolean = !is_my_poll && !has_question;
        const author_help: boolean = is_my_poll && !has_question;

        $elem.find(".poll-question-header").toggle(!input_mode);
        $elem.find(".poll-question-header").text(question);
        $elem.find(".poll-edit-question").toggle(can_edit);
        update_edit_controls();

        $elem.find(".poll-question-bar").toggle(input_mode);
        $elem.find(".poll-option-bar").toggle(can_vote);

        $elem.find(".poll-please-wait").toggle(waiting);

        $elem.find(".poll-author-help").toggle(author_help);
    }

    function start_editing(): void {
        poll_data.set_input_mode();

        const question: string = poll_data.get_question();
        $elem.find("input.poll-question").val(question);
        render_question();
        $elem.find("input.poll-question").trigger("focus");
    }

    function abort_edit(): void {
        poll_data.clear_input_mode();
        render_question();
    }

    function submit_question(): void {
        const $poll_question_input: JQuery = $elem.find("input.poll-question");
        let new_question: string = ($poll_question_input.val() as string)?.trim() || "";
        const old_question: string = poll_data.get_question();

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
        const data = poll_data.handle.question.outbound(new_question);
        callback(data);
    }

    function submit_option(): void {
        const $poll_option_input: JQuery = $elem.find("input.poll-option");
        const option: string = ($poll_option_input.val() as string)?.trim() || "";
        const options: PollOptionData[] = poll_data.get_widget_data().options;

        if (poll_data.is_option_present(options, option)) {
            return;
        }

        if (option === "") {
            return;
        }

        $poll_option_input.val("").trigger("focus");

        const data: unknown = poll_data.handle.new_option.outbound(option);
        callback(data);
    }

    function submit_vote(key: string): void {
        const data = poll_data.handle.vote.outbound(key);
        callback(data);
    }

    function build_widget(): void {
        const html: string = render_widgets_poll_widget();
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

        $elem.find("input.poll-option").on("keyup", (e: JQuery.Event) => {
            e.stopPropagation();
            check_option_button();

            if (keydown_util.is_enter_event(e as JQuery.KeyDownEvent)) {
                submit_option();
            }

            if (e.key === "Escape") {
                $("input.poll-option").val("");
                return;
            }
        });
    }

    function check_option_button(): void {
        const $poll_option_input: JQuery = $elem.find("input.poll-option");
        const option: string = ($poll_option_input.val() as string)?.trim() || "";
        const options: PollOptionData[] = poll_data.get_widget_data().options;

        if (poll_data.is_option_present(options, option)) {
            $elem.find("button.poll-option").attr("disabled", "disabled");
            $elem
                .find("button.poll-option")
                .attr("title", $t({defaultMessage: "Option already present."}));
        } else {
            $elem.find("button.poll-option").removeAttr("disabled");
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
                const key: string | undefined = $(e.target).attr("data-key");
                // submit_vote(key);
                assert(key !== undefined && key !== null, "Invalid or missing key attribute.");
                submit_vote(key);
            });
    }

    ($elem as CustomPollJQuery).handle_events = function (events: PollEventType[]): void {
        for (const event of events) {
            poll_data.handle_event(event.sender_id, event.data);
        }

        render_question();
        render_results();
    };

    build_widget();
    render_question();
    render_results();
}
