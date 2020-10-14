import google_blob_sheet from "emoji-datasource-google-blob/img/google/sheets-256/64.png";
import google_sheet from "emoji-datasource-google/img/google/sheets-256/64.png";
import twitter_sheet from "emoji-datasource-twitter/img/twitter/sheets-256/64.png";

import octopus_url from "../generated/emoji/images-google-64/1f419.png";

import google_blob_css from "!style-loader?injectType=lazyStyleTag!css-loader!../generated/emoji-styles/google-blob-sprite.css";
import google_css from "!style-loader?injectType=lazyStyleTag!css-loader!../generated/emoji-styles/google-sprite.css";
import twitter_css from "!style-loader?injectType=lazyStyleTag!css-loader!../generated/emoji-styles/twitter-sprite.css";

const emojisets = new Map([
    ["google", {css: google_css, sheet: google_sheet}],
    ["google-blob", {css: google_blob_css, sheet: google_blob_sheet}],
    ["twitter", {css: twitter_css, sheet: twitter_sheet}],
]);

// For `text` emojiset we fallback to `google-blob` emojiset
// for displaying emojis in emoji picker and typeahead.
emojisets.set("text", emojisets.get("google-blob"));

let current_emojiset;

export async function select(name) {
    const new_emojiset = emojisets.get(name);
    if (new_emojiset === current_emojiset) {
        return;
    }
    await new Promise((resolve, reject) => {
        const sheet = new Image();
        sheet.addEventListener("load", resolve);
        sheet.addEventListener("error", reject);
        sheet.src = new_emojiset.sheet;
    });
    if (current_emojiset) {
        current_emojiset.css.unuse();
    }
    new_emojiset.css.use();
    current_emojiset = new_emojiset;
}

export function initialize() {
    select(page_params.emojiset);

    // Load the octopus image in the background, so that the browser
    // will cache it for later use.  Note that we hardcode the octopus
    // emoji to the old Google one because it's better.
    //
    // TODO: We should probably just make this work just like the Zulip emoji.
    const octopus_image = new Image();
    octopus_image.src = octopus_url;
}
