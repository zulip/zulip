import * as z from "zod/mini";

/*
    The zform widget is essentially support for creating
    a "choices" form that presents the user (in a message
    in the messages view) with a list of choices and
    buttons to push.

    The prime example of this is our trivia bot.

    See docs/subsystems/widgets.md and go to the
    zform-trivia-quiz-bot section for more details.
*/

export const zform_widget_extra_data_schema = z.object({
    choices: z.array(
        z.object({
            type: z.string(),
            long_name: z.string(),
            reply: z.string(),
            short_name: z.string(),
        }),
    ),
    heading: z.string(),
    type: z.literal("choices"),
});

export type ZFormExtraData = z.infer<typeof zform_widget_extra_data_schema>;
