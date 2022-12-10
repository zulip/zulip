import $ from "jquery";

import emoji_codes from "../generated/emoji/emoji_codes.json";
import * as typeahead from "../shared/js/typeahead";
import render_emoji_popover from "../templates/emoji_popover.hbs";
import render_emoji_popover_content from "../templates/emoji_popover_content.hbs";
import render_emoji_popover_search_results from "../templates/emoji_popover_search_results.hbs";
import render_emoji_showcase from "../templates/emoji_showcase.hbs";
import * as picker from "./emoji_picker"

import * as blueslip from "./blueslip";
import * as compose_ui from "./compose_ui";
import * as emoji from "./emoji";
import * as keydown_util from "./keydown_util";
import * as message_lists from "./message_lists";
import * as message_store from "./message_store";
import {page_params} from "./page_params";
import * as popovers from "./popovers";
import * as reactions from "./reactions";
import * as rows from "./rows";
import * as spectators from "./spectators";
import * as ui from "./ui";
import {user_settings} from "./user_settings";
import * as user_status_ui from "./user_status_ui";

// const codepoint = emoji.get_emoji_codepoint("plus");

var customizedemoji = [
  "1f44d", // +1
  "1f389", // tada
  "1f642", // smile
  "2764", // heart
  "1f6e0", // working_on_it
  "2795", // plus sign
]

export function customized_emoji() {
  return customizedemoji;
}

export function update_customized(emoji_id) {
  for(let i = 4; i > 0; i--) {
    customizedemoji[i] = customizedemoji[i-1];
  }
  customizedemoji[0] = emoji_id;
}
//some button in div class = emoji-popover
//that if clicked it shows another emoji-popover to select customized emoji
