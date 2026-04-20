import { z } from "zod";

export const availability_schema = z.object({
    type: z.literal("availability_submitted"),
    user_id: z.number(),
});

export const propose_widget_extra_data_schema = z.object({
    meeting_id: z.number(),
    topic: z.string(),
    invitees: z.array(z.number()).optional(),
});

export type AvailabilityEvent = z.infer<typeof availability_schema>;

type ProposeDataParams = {
    meeting_id: number;
    topic: string;
    invitees: number[];
    current_user_id: number;
};

export class ProposeData {
    meeting_id: number;
    topic: string;
    invitees: number[];
    me: number;

    // set of user_ids who have submitted availability
    submitted: Set<number>;

    constructor({ meeting_id, topic, invitees, current_user_id }: ProposeDataParams) {
        this.meeting_id = meeting_id;
        this.topic = topic;
        this.invitees = invitees;
        this.me = current_user_id;
        this.submitted = new Set();
    }

    handle_availability_event(sender_id: number, _event: AvailabilityEvent): void {
        this.submitted.add(sender_id);
    }

    has_submitted(user_id: number): boolean {
        return this.submitted.has(user_id);
    }

    get_widget_data(): {
        meeting_id: number;
        topic: string;
        invitees: number[];
        submitted: Set<number>;
        i_have_submitted: boolean;
    } {
        return {
            meeting_id: this.meeting_id,
            topic: this.topic,
            invitees: this.invitees,
            submitted: this.submitted,
            i_have_submitted: this.submitted.has(this.me),
        };
    }

    availability_event(): AvailabilityEvent {
        return {
            type: "availability_submitted",
            user_id: this.me,
        };
    }
}