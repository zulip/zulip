import * as z from "zod/mini";

export const submessage_schema = z.object({
    id: z.number(),
    sender_id: z.number(),
    message_id: z.number(),
    content: z.string(),
    msg_type: z.string(),
});

export type Submessage = z.infer<typeof submessage_schema>;
