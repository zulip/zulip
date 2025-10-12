declare module "*/static/generated/emoji/emoji_codes.json" {
    export type EmojiCodes = {
        // Allow other top-level fields
        [key: string]: unknown;
        // Map of category name -> list of emoji codepoints (strings)
        emoji_catalog: Record<string, string[]>;
        // All emoji names
        names: string[];
    };

    const emoji_codes: EmojiCodes;
    export default emoji_codes;
}
