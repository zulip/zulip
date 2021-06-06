export class PollData {
    // This object just holds data for a poll, although it
    // works closely with the widget's concept of how data
    // should be represented for rendering, plus how the
    // server sends us data.

    key_to_option = new Map();
    my_idx = 1;

    constructor({
        current_user_id,
        is_my_poll,
        question,
        options,
        comma_separated_names,
        report_error_function,
    }) {
        this.me = current_user_id;
        this.is_my_poll = is_my_poll;
        this.poll_question = question;
        this.input_mode = is_my_poll; // for now
        this.comma_separated_names = comma_separated_names;
        this.report_error_function = report_error_function;

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
                names: this.comma_separated_names(voters),
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
                return undefined;
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
                    this.report_error_function("unknown key for poll: " + key);
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
