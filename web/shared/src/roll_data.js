const MAX_IDX = 1000;

export class RollData {

    key_to_option = new Map();
    my_idx = 1;

    constructor({
        message_sender_id,
        current_user_id,
        is_my_roll,
        range,
        count,
        report_error_function,
    }) {
        this.message_sender_id = message_sender_id;
        this.me = current_user_id;
        this.is_my_roll = is_my_roll;
        this.range = range;
        this.count = count;
        this.report_error_function = report_error_function;

    }

    set_roll(new_question) {
        this.input_mode = false;
        this.roll_statement = new_roll;
    }

    get_roll() {
        return this.roll_statement;
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

        const widget_data = {
            range: this.range,
            count: this.count,
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
                const count = data.count;

                if (!Number.isInteger(idx) || idx < 0 || idx > MAX_IDX) {
                    this.report_error_function("roll widget: bad type for range idx");
                    return;
                }

                if (typeof count !== "string") {
                    this.report_error_function("roll widget: bad type for count");
                    return;
                }

                const key = sender_id + "," + idx;

                if (sender_id === this.me && this.my_idx <= idx) {
                    this.my_idx = idx + 1;
                }
            },
        },

        roll: {
            outbound: (roll) => {
                const event = {
                    type: "roll",
                    roll,
                };
                if (this.is_my_roll) {
                    return event;
                }
                return undefined;
            },

            inbound: (sender_id, data) => {

                if (typeof data.roll !== "string") {
                    this.report_error_function("roll widget: invalid inputs");
                    return;
                }

                this.set_roll(data.count, data.range);
            },
        },

    };

    handle_event(sender_id, data) {
        const type = data.type;
        if (this.handle[type] && this.handle[type].inbound) {
            this.handle[type].inbound(sender_id, data);
        } else {
            this.report_error_function(`roll widget: unknown inbound type: ${type}`);
        }
    }

    // function to check whether option already exists
    is_option_present(data, latest_option) {
        return data.some((el) => el.option === latest_option);
    }
}
