import * as z from "zod/mini";

// Schema for the propose meeting widget data your modal will receive
export const availability_widget_extra_data_schema = z.object({
  topic: z.string(),
  dates: z.array(z.string()), // ["2026-04-07", "2026-04-08", ...]
  start_time: z.string(), // "09:00"
  end_time: z.string(), // "17:00"
  slot_duration_mins: z.number(), // 30
  invitees: z.array(z.number()), // user_ids
});

export type AvailabilityWidgetExtraData = z.infer<
  typeof availability_widget_extra_data_schema
>;

export const availability_event_schema = z.object({
  type: z.literal("availability"),
  available_slots: z.array(z.string()), // ["2026-04-07T09:00", "2026-04-07T09:30", ...]
});

export type AvailabilityEvent = z.infer<typeof availability_event_schema>;

export type AvailabilityDataConfig = {
  topic: string;
  dates: string[];
  start_time: string;
  end_time: string;
  slot_duration_mins: number;
  invitees: number[];
  current_user_id: number;
};

export function generate_slots(
  dates: string[],
  start_time: string,
  end_time: string,
  slot_duration_mins: number,
): string[] {
  const slots: string[] = [];
  const [start_h, start_m] = start_time.split(":").map(Number);
  const [end_h, end_m] = end_time.split(":").map(Number);
  const start_mins = start_h! * 60 + start_m!;
  const end_mins = end_h! * 60 + end_m!;

  for (const date of dates) {
    for (let m = start_mins; m < end_mins; m += slot_duration_mins) {
      const hh = String(Math.floor(m / 60)).padStart(2, "0");
      const mm = String(m % 60).padStart(2, "0");
      slots.push(`${date}T${hh}:${mm}`);
    }
  }
  return slots;
}

export class MeetingAvailabilityData {
  topic: string;
  dates: string[];
  start_time: string;
  end_time: string;
  slot_duration_mins: number;
  invitees: number[];
  me: number;
  // Maps user_id -> set of slot keys they marked available
  responses = new Map<number, Set<string>>();

  constructor({
    topic,
    dates,
    start_time,
    end_time,
    slot_duration_mins,
    invitees,
    current_user_id,
  }: AvailabilityDataConfig) {
    this.topic = topic;
    this.dates = dates;
    this.start_time = start_time;
    this.end_time = end_time;
    this.slot_duration_mins = slot_duration_mins;
    this.invitees = invitees;
    this.me = current_user_id;
  }

  handle_availability_event(sender_id: number, event: AvailabilityEvent): void {
    this.responses.set(sender_id, new Set(event.available_slots));
  }

  availability_event(selected_slots: string[]): AvailabilityEvent {
    return {type: "availability", available_slots: selected_slots};
  }

  get_slot_count(slot_key: string): number {
    let count = 0;
    for (const slots of this.responses.values()) {
      if (slots.has(slot_key)) {
        count++;
      }
    }
    return count;
  }

  get_my_selected_slots(): Set<string> {
    return this.responses.get(this.me) ?? new Set();
  }

  get_total_respondents(): number {
    return this.responses.size;
  }

  get_all_slots(): string[] {
    return generate_slots(
      this.dates,
      this.start_time,
      this.end_time,
      this.slot_duration_mins,
    );
  }

  get_widget_data() {
    const all_slots = this.get_all_slots();
    const slot_counts: Record<string, number> = {};
    for (const slot of all_slots) {
      slot_counts[slot] = this.get_slot_count(slot);
    }
    return {
      topic: this.topic,
      dates: this.dates,
      start_time: this.start_time,
      end_time: this.end_time,
      slot_duration_mins: this.slot_duration_mins,
      invitees: this.invitees,
      all_slots,
      slot_counts,
      my_selected_slots: this.get_my_selected_slots(),
      total_respondents: this.get_total_respondents(),
    };
  }
}
