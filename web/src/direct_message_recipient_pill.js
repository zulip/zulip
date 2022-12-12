import * as input_pill from "./input_pill";
import * as people from "./people";
import * as user_pill from "./user_pill";
import * as util from "./util";

export class DirectMessageRecipientPill {
    constructor($container) {
        const pill_config = {
            show_user_status_emoji: true,
        };
        this.widget = input_pill.create({
            $container,
            pill_config,
            create_item_from_text: user_pill.create_item_from_email,
            get_text_from_item: user_pill.get_email_from_item,
        });
    }

    clear() {
        this.widget.clear();
    }

    set_from_typeahead(person) {
        user_pill.append_person({
            pill_widget: this.widget,
            person,
        });
    }

    set_from_emails(value) {
        // value is something like "alice@example.com,bob@example.com"
        this.clear();
        this.widget.appendValue(value);
    }

    get_user_ids() {
        return user_pill.get_user_ids(this.widget);
    }

    has_unconverted_data() {
        return user_pill.has_unconverted_data(this.widget);
    }

    get_user_ids_string() {
        const user_ids = this.get_user_ids();
        const sorted_user_ids = util.sorted_ids(user_ids);
        const user_ids_string = sorted_user_ids.join(",");
        return user_ids_string;
    }

    get_emails() {
        // return something like "alice@example.com,bob@example.com"
        const user_ids = this.get_user_ids();
        const emails = user_ids.map((id) => people.get_by_user_id(id).email).join(",");
        return emails;
    }

    filter_taken_users(persons) {
        return user_pill.filter_taken_users(persons, this.widget);
    }
}
