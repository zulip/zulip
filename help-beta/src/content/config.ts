import {docsSchema} from "@astrojs/starlight/schema";
import {defineCollection} from "astro:content";

export const collections = {
    docs: defineCollection({schema: docsSchema()}),
};
