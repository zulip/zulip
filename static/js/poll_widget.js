"use strict";

const render_widgets_poll_widget = require("../templates/widgets/poll_widget.hbs");
const render_widgets_poll_widget_results = require("../templates/widgets/poll_widget_results.hbs");

const people = require("./people");

class PollData {
    // This object just holds data for a poll, although it
    // works closely with the widget's concept of how data
    // should be represented for rendering, plus how the
    // server sends us data.

    me = people.my_current_user_id();
    key_to_option = new Map();
    my_idx = 1;

    constructor(is_my_poll, question, options) {
        this.is_my_poll = is_my_poll;
        this.poll_question = question;
        this.input_mode = is_my_poll; // for now

        if (question) {
            this.set_question(question);
        }

        for (const [i, option] of options.entries()) {
            this.handle.new_option.inbound("canned", {
                idx: i,
                option,
            });
        }
    }

    set_question(new_question) {
        this.input_mode = false;
        this.poll_question = new_question;
    }

    get_question() {
        return this.poll_question;
    }

    set_input_mode() {
        this.input_mode = true;
    }

    clear_input_mode() {
        this.input_mode = false;
    }

    get_input_mode() {
        return this.input_mode;
    }

    get_widget_data() {
        const options = [];

        for (const [key, obj] of this.key_to_option) {
            const voters = Array.from(obj.votes.keys());
            const current_user_vote = voters.includes(this.me);

            options.push({
                option: obj.option,
                names: people.safe_full_names(voters),
                count: voters.length,
                key,
                current_user_vote,
            });
        }

        const widget_data = {
            options,
            question: this.poll_question,
        };

        return widget_data;
    }

    handle = {
        new_option: {
            outbound: (option) => {
                const event = {
                    type: "new_option",
                    idx: this.my_idx,
                    option,
                };

                this.my_idx += 1;

                return event;
            },

            inbound: (sender_id, data) => {
                const idx = data.idx;
                const key = sender_id + "," + idx;
                const option = data.option;
                const votes = new Map();

                this.key_to_option.set(key, {
                    option,
                    user_id: sender_id,
                    votes,
                });

                if (this.my_idx <= idx) {
                    this.my_idx = idx + 1;
                }
            },
        },

        question: {
            outbound: (question) => {
                const event = {
                    type: "question",
                    question,
                };
                if (this.is_my_poll) {
                    return event;
                }
                return;
            },

            inbound: (sender_id, data) => {
                this.set_question(data.question);
            },
        },

        vote: {
            outbound: (key) => {
                let vote = 1;

                // toggle
                if (this.key_to_option.get(key).votes.get(this.me)) {
                    vote = -1;
                }

                const event = {
                    type: "vote",
                    key,
                    vote,
                };

                return event;
            },

            inbound: (sender_id, data) => {
                const key = data.key;
                const vote = data.vote;
                const option = this.key_to_option.get(key);

                if (option === undefined) {
                    blueslip.warn("unknown key for poll: " + key);
                    return;
                }

                const votes = option.votes;

                if (vote === 1) {
                    votes.set(sender_id, 1);
                } else {
                    votes.delete(sender_id);
                }
            },
        },
    };

    handle_event(sender_id, data) {
        const type = data.type;
        if (this.handle[type]) {
            this.handle[type].inbound(sender_id, data);
        }
    }

    // function to check whether option already exists
    is_option_present(data, latest_option) {
        return data.some((el) => el.option === latest_option);
    }
}
exports.PollData = PollData;

exports.activate = function (opts) {
    const elem = opts.elem;
    const callback = opts.callback;

    let question = "";
    let options = [];
    if (opts.extra_data) {
        question = opts.extra_data.question || "";
        options = opts.extra_data.options || [];
    }

    const is_my_poll = people.is_my_user_id(opts.message.sender_id);
    const poll_data = new PollData(is_my_poll, question, options);

    function update_edit_controls() {
        const has_question = elem.find("input.poll-question").val().trim() !== "";
        elem.find("button.poll-question-check").toggle(has_question);
    }

    function render_question() {
        const question = poll_data.get_question();
        const input_mode = poll_data.get_input_mode();
        const can_edit = is_my_poll && !input_mode;
        const has_question = question.trim() !== "";
        const can_vote = has_question;
        const waiting = !is_my_poll && !has_question;
        const author_help = is_my_poll && !has_question;

        elem.find(".poll-question-header").toggle(!input_mode);
        elem.find(".poll-question-header").text(question);
        elem.find(".poll-edit-question").toggle(can_edit);
        update_edit_controls();

        elem.find(".poll-question-bar").toggle(input_mode);
        elem.find(".poll-option-bar").toggle(can_vote);

        elem.find(".poll-please-wait").toggle(waiting);

        elem.find(".poll-author-help").toggle(author_help);
    }

    function start_editing() {
        poll_data.set_input_mode();

        const question = poll_data.get_question();
        elem.find("input.poll-question").val(question);
        render_question();
        elem.find("input.poll-question").trigger("focus");
    }

    function abort_edit() {
        poll_data.clear_input_mode();
        render_question();
    }

    function submit_question() {
        const poll_question_input = elem.find("input.poll-question");
        let new_question = poll_question_input.val().trim();
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
        const data = poll_data.handle.question.outbound(new_question);
        callback(data);
    }

    function submit_option() {
        const poll_option_input = elem.find("input.poll-option");
        const option = poll_option_input.val().trim();
        const options = poll_data.get_widget_data().options;

        if (poll_data.is_option_present(options, option)) {
            return;
        }

        if (option === "") {
            return;
        }

        poll_option_input.val("").trigger("focus");

        const data = poll_data.handle.new_option.outbound(option);
        callback(data);
    }

    function submit_vote(key) {
        const data = poll_data.handle.vote.outbound(key);
        callback(data);
    }

    function build_widget() {
        const html = render_widgets_poll_widget();
        elem.html(html);

        elem.find("input.poll-question").on("keyup", (e) => {
            e.stopPropagation();
            update_edit_controls();
        });

        elem.find("input.poll-question").on("keydown", (e) => {
            e.stopPropagation();

            if (e.keyCode === 13) {
                submit_question();
                return;
            }

            if (e.keyCode === 27) {
                abort_edit();
                return;
            }
        });

        elem.find(".poll-edit-question").on("click", (e) => {
            e.stopPropagation();
            start_editing();
        });

        elem.find("button.poll-question-check").on("click", (e) => {
            e.stopPropagation();
            submit_question();
        });

        elem.find("button.poll-question-remove").on("click", (e) => {
            e.stopPropagation();
            abort_edit();
        });

        elem.find("button.poll-option").on("click", (e) => {
            e.stopPropagation();
            submit_option();
        });

        elem.find("input.poll-option").on("keydown", (e) => {
            e.stopPropagation();

            if (e.keyCode === 13) {
                submit_option();
                return;
            }

            if (e.keyCode === 27) {
                $("input.poll-option").val("");
                return;
            }
        });
    }

    function render_results() {
        const widget_data = poll_data.get_widget_data();

        const html = render_widgets_poll_widget_results(widget_data);
        elem.find("ul.poll-widget").html(html);

        elem.find("button.poll-vote")
            .off("click")
            .on("click", (e) => {
                e.stopPropagation();
                const key = $(e.target).attr("data-key");
                submit_vote(key);
            });
    }

    elem.handle_events = function (events) {
        for (const event of events) {
            poll_data.handle_event(event.sender_id, event.data);
        }

        render_question();
        render_results();
    };

    build_widget();
    render_question();
    render_results();
};

window.poll_widget = exports;
