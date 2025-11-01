import "./common.ts";
import "../portico/header.ts";
import "../portico/google-analytics.ts";
import "../portico/portico_modals.ts";
import "../portico/tippyjs.ts";
import "../../third/bootstrap/css/bootstrap.portico.css";
import "../../styles/portico/portico_styles.css";
import "tippy.js/dist/tippy.css";

// Initialize emoji rendering for portico pages
import * as emojisets from "../emojisets.ts";

// Use Google as default emojiset for unauthenticated pages
// since user_settings is not available
void emojisets.select("google");
