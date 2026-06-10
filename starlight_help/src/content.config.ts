import {docsLoader} from "@astrojs/starlight/loaders";
import {docsSchema} from "@astrojs/starlight/schema";
import {z} from "astro/zod";
import {defineCollection} from "astro:content";

import EmojiCodes from "../../static/generated/emoji/emoji_codes.json";

const emoticonConversions: Record<string, string> = EmojiCodes.emoticon_conversions;
const nameToCodePoint: Record<string, string> = EmojiCodes.name_to_codepoint;

// Using image() in the schema means Astro bundles only the few emoji used for
// emoticons, rather than the thousands import.meta.glob would copy.
const emoticons = defineCollection({
    loader: () =>
        Object.entries(emoticonConversions).map(([emoticon, emoji], order) => ({
            id: emoticon,
            order,
            emoji,
            image: `../../static/generated/emoji/images-google-64/${nameToCodePoint[emoji.slice(1, -1)]}.png`,
        })),
    schema: ({image}) => z.object({order: z.int(), emoji: z.string(), image: image()}),
});

export const collections = {
    docs: defineCollection({loader: docsLoader(), schema: docsSchema()}),
    emoticons,
};
