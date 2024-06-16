import assert from "minimalistic-assert";
import {z} from "zod";

export type PollDataConfig = {
    message_sender_id: number;
    current_user_id: number;
    is_my_poll: boolean;
    question: string;
    options: string[];
    comma_separated_names: (user_ids: number[]) => string;
    report_error_function: (msg: string, more_info?: unknown) => void;
};

export type PollOptionData = {
    option: string;
    names: string;
    count: number;
    key: string;
    current_user_vote: boolean;
};

type PollOption = {
    option: string;
    user_id: number | string;
    votes: Map<number, number>;
};

export type WidgetData = {
    options: PollOptionData[];
    question: string;
};

export type InboundData = unknown;
export type NewOptionOutboundData = {type: string; idx: number; option: string};
export type QuestionOutboundData = {type: string; question: string};
export type VoteOutboundData = {type: string; key: string; vote: number};
export type PollHandle = {
    new_option: {
        outbound: (option: string) => NewOptionOutboundData;
        inbound: (sender_id: number | string, data: InboundData) => void;
    };
    question: {
        outbound: (question: string) => QuestionOutboundData | undefined;
        inbound: (sender_id: number, data: InboundData) => void;
    };
    vote: {
        outbound: (key: string) => VoteOutboundData;
        inbound: (sender_id: number, data: InboundData) => void;
    };
};

const inbound_option_schema = z.object({
    idx: z.number(),
    option: z.string(),
    type: z.literal("new_option"),
});

const inbound_question_schema = z.object({
    question: z.string(),
    type: z.literal("question"),
});

const inbound_vote_schema = z.object({
    key: z.string(),
    type: z.literal("vote"),
    vote: z.number(),
});

// Any single user should send add a finite number of options
// to a poll. We arbitrarily pick this value.
const MAX_IDX = 1000;

export class PollData {
    // This object just holds data for a poll, although it
    // works closely with the widget's concept of how data
    // should be represented for rendering, plus how the
    // server sends us data.

    key_to_option = new Map<string, PollOption>();
    my_idx = 1;
    message_sender_id: number;
    me: number;
    is_my_poll: boolean;
    poll_question: string;
    input_mode: boolean;
    comma_separated_names: (user_ids: number[]) => string;
    report_error_function: (error_message: string) => void;
    handle: PollHandle;

    constructor({
        message_sender_id,
        current_user_id,
        is_my_poll,
        question,
        options,
        comma_separated_names,
        report_error_function,
    }: PollDataConfig) {
        this.message_sender_id = message_sender_id;
        this.me = current_user_id;
        this.is_my_poll = is_my_poll;
        this.poll_question = question;
        this.input_mode = is_my_poll; // for now
        this.comma_separated_names = comma_separated_names;
        this.report_error_function = report_error_function;

        if (question) {
            this.set_question(question);
        }

        this.handle = {
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
                    const safe_data = inbound_option_schema.parse(data);

                    // All message readers may add a new option to the poll.
                    const idx = safe_data.idx;
                    const option = safe_data.option;
                    const options = this.get_widget_data().options;

                    // While the UI doesn't allow adding duplicate options
                    // to an existing poll, the /poll command syntax to create
                    // them does not prevent duplicates, so we suppress them here.
                    if (this.is_option_present(options, option)) {
                        return;
                    }

                    if (idx < 0 || idx > MAX_IDX) {
                        this.report_error_function("poll widget: idx out of bound");
                        return;
                    }

                    const key = `${sender_id},${idx}`;
                    const votes = new Map<number, number>();

                    this.key_to_option.set(key, {
                        option,
                        user_id: sender_id,
                        votes,
                    });

                    // I may have added a poll option from another device.
                    if (sender_id === this.me && this.my_idx <= idx) {
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
                    const safe_data = inbound_question_schema.parse(data);

                    // Only the message author can edit questions.
                    if (sender_id !== this.message_sender_id) {
                        this.report_error_function(
                            `user ${sender_id} is not allowed to edit the question`,
                        );
                        return;
                    }

                    this.set_question(safe_data.question);
                },
            },

            vote: {
                outbound: (key) => {
                    let vote = 1;

                    // toggle
                    assert(this.key_to_option.has(key), `option key not found: ${key}`);
                    if (this.key_to_option.get(key)!.votes.get(this.me)) {
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
                    const safe_data = inbound_vote_schema.parse(data);

                    // All message readers may vote on poll options.
                    const key = safe_data.key;
                    const vote = safe_data.vote;

                    if (!(vote === 1 || vote === -1)) {
                        this.report_error_function("poll widget: bad value for inbound vote count");
                        return;
                    }

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

        for (const [i, option] of options.entries()) {
            this.handle.new_option.inbound("canned", {
                idx: i,
                option,
                type: "new_option",
            });
        }
    }

    set_question(new_question: string): void {
        this.input_mode = false;
        this.poll_question = new_question;
    }

    get_question(): string {
        return this.poll_question;
    }

    set_input_mode(): void {
        this.input_mode = true;
    }

    clear_input_mode(): void {
        this.input_mode = false;
    }

    get_input_mode(): boolean {
        return this.input_mode;
    }

    get_widget_data(): WidgetData {
        const options: PollOptionData[] = [];

        for (const [key, obj] of this.key_to_option) {
            const voters = [...obj.votes.keys()];
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

    handle_event(sender_id: number, data: InboundData): void {
        assert(
            typeof data === "object" &&
                data !== null &&
                "type" in data &&
                typeof data.type === "string",
        );
        const type = data.type;
        if (type === "new_option" || type === "question" || type === "vote") {
            this.handle[type].inbound(sender_id, data);
        } else {
            this.report_error_function(`poll widget: unknown inbound type: ${type}`);
        }
    }

    // function to check whether option already exists
    is_option_present(data: PollOptionData[], latest_option: string): boolean {
        return data.some((el) => el.option === latest_option);
    }
}
