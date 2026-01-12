import * as z from "zod/mini";

export const todo_setup_data_schema = z.object({
    task_list_title: z.optional(z.string()),
    tasks: z.optional(z.array(z.object({task: z.string(), desc: z.string()}))),
});

export type TodoSetupData = z.infer<typeof todo_setup_data_schema>;
