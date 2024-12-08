import type {Message} from "./message_store.ts";
import * as people from "./people.ts";

export class ConversationParticipants {
    humans: Set<number>;
    bots: Set<number>;

    constructor(messages: Message[]) {
        this.humans = new Set();
        this.bots = new Set();
        this.add_from_messages(messages);
    }

    add_from_messages(messages: Message[]): void {
        for (const msg of messages) {
            if (msg.sent_by_me) {
                this.humans.add(msg.sender_id);
                continue;
            }

            const sender = people.maybe_get_user_by_id(msg.sender_id);
            if (!sender) {
                continue;
            }

            if (sender.is_bot) {
                this.bots.add(msg.sender_id);
            } else {
                this.humans.add(msg.sender_id);
            }
        }
    }
}
