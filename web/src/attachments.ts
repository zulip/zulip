import * as z from "zod/mini";

export const attachment_schema = z.object({
    id: z.number(),
    name: z.string(),
    path_id: z.string(),
    size: z.number(),
    create_time: z.number(),
    messages: z.array(
        z.object({
            id: z.number(),
            date_sent: z.number(),
        }),
    ),
});

const attachments_schema = z.array(attachment_schema);

export const attachment_api_response_schema = z.object({
    attachments: attachments_schema,
    upload_space_used: z.number(),
});

export const detached_uploads_api_response_schema = z.object({
    detached_uploads: attachments_schema,
});
