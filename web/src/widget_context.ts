import * as message_lists from "./message_lists.ts";
import type {Message} from "./message_store.ts";
import * as people from "./people.ts";

// The name ZulipWidgetContext (as opposed to WidgetContext)
// is intentional here, as we will eventually want to have
// widgets live in a non-Zulip context. That's the dream.
export class ZulipWidgetContext {
    message: Message;
    sender_id: number;

    constructor(message: Message) {
        this.message = message;
        this.sender_id = message.sender_id;
    }

    is_container_hidden(): boolean {
        const message_container = message_lists.current?.view.message_containers.get(
            this.message.id,
        );
        return message_container?.is_hidden ?? false;
    }

    is_my_poll(): boolean {
        return people.is_my_user_id(this.sender_id);
    }

    owner_user_id(): number {
        return this.sender_id;
    }

    current_user_id(): number {
        return people.my_current_user_id();
    }
}
