import * as v from "valibot";

export const attachment_schema = v.object({
    id: v.number(),
    name: v.string(),
    path_id: v.string(),
    size: v.number(),
    create_time: v.number(),
    messages: v.array(
        v.object({
            id: v.number(),
            date_sent: v.number(),
        }),
    ),
});

const attachments_schema = v.array(attachment_schema);

export const attachment_api_response_schema = v.object({
    attachments: attachments_schema,
    upload_space_used: v.number(),
});

export const detached_uploads_api_response_schema = v.object({
    detached_uploads: attachments_schema,
});
