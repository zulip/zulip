import assert from "minimalistic-assert";
import * as z from "zod/mini";

export type PollDataConfig = {
    poll_owner_user_id: number;
    current_user_id: number;
    is_my_poll: boolean;
    question: string;
    options: string[];
    get_full_name_list: (user_ids: number[]) => string;
    report_error_function: (msg: string, more_info?: Record<string, unknown>) => void;
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

/*
    EVENT TYPES FOLLOW.

    The inbound types have exactly the same shape as the
    outbound types. It's a peer-to-peer protocol.

    Alice send the NewOption message (outbound).
    Bob receives the NewOption message (inbound).

    It's actually that simple.
*/

export const new_option_schema = z.object({
    type: z.literal("new_option"),
    idx: z.number(),
    option: z.string(),
});
type NewOption = {type: string; idx: number; option: string};

export const question_schema = z.object({
    type: z.literal("question"),
    question: z.string(),
});
type Question = {type: string; question: string};

export const vote_schema = z.object({
    type: z.literal("vote"),
    key: z.string(),
    vote: z.number(),
});
type Vote = {type: string; key: string; vote: number};

/* ---------------------- */

export const poll_widget_extra_data_schema = z.object({
    question: z.optional(z.string()),
    options: z.optional(z.array(z.string())),
});

export type PollWidgetExtraData = z.infer<typeof poll_widget_extra_data_schema>;

export type PollWidgetOutboundData = NewOption | Question | Vote;

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
    poll_owner_user_id: number;
    me: number;
    is_my_poll: boolean;
    poll_question: string;
    input_mode: boolean;
    get_full_name_list: (user_ids: number[]) => string;
    report_error_function: (error_message: string) => void;

    constructor({
        poll_owner_user_id,
        current_user_id,
        is_my_poll,
        question,
        options,
        get_full_name_list,
        report_error_function,
    }: PollDataConfig) {
        this.poll_owner_user_id = poll_owner_user_id;
        this.me = current_user_id;
        this.is_my_poll = is_my_poll;
        this.poll_question = question;
        this.input_mode = is_my_poll; // for now
        this.get_full_name_list = get_full_name_list;
        this.report_error_function = report_error_function;

        if (question) {
            this.set_question(question);
        }

        for (const [i, option] of options.entries()) {
            this.handle_new_option_event("canned", {
                idx: i,
                option,
                type: "new_option",
            });
        }
    }

    new_option_event(option: string): NewOption {
        const event = {
            type: "new_option",
            idx: this.my_idx,
            option,
        };

        this.my_idx += 1;

        return event;
    }

    handle_new_option_event(sender_id: string | number, data: NewOption): void {
        // All message readers may add a new option to the poll.
        const {idx, option} = data;
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
    }

    question_event(question: string): Question | undefined {
        const event = {
            type: "question",
            question,
        };
        if (this.is_my_poll) {
            return event;
        }
        return undefined;
    }

    handle_question_event(sender_id: number, data: Question): void {
        // Only the message author can edit questions.
        if (sender_id !== this.poll_owner_user_id) {
            this.report_error_function(`user ${sender_id} is not allowed to edit the question`);
            return;
        }

        this.set_question(data.question);
    }

    vote_event(key: string): Vote {
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
    }

    handle_vote_event(sender_id: number, data: Vote): void {
        const {key, vote} = data;

        // All message readers may vote on poll options.
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
                names: this.get_full_name_list(voters),
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

    // function to check whether option already exists
    is_option_present(data: PollOptionData[], latest_option: string): boolean {
        return data.some((el) => el.option === latest_option);
    }
}
