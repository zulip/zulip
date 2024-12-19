/* We track participants in a narrow here by updating
 * the data structure when a message is added / removed
 * from MessageListData.
 */

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
                // `sender` is always defined but this checks helps use
                // avoid patching all the tests.
                continue;
            }

            if (sender.is_bot) {
                this.bots.add(msg.sender_id);
            } else {
                this.humans.add(msg.sender_id);
            }
        }
    }
    // We don't support removal of a message due to deletion or message moves,
    // because we aren't tracking the set of message IDs for each participant,
    // so we currently just rebuild.

    visible(): Set<number> {
        return new Set(
            [...this.humans].filter((user_id) =>
                people.is_displayable_conversation_participant(user_id),
            ),
        );
    }
}
