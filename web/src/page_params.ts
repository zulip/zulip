import assert from "minimalistic-assert";

import {page_params as base_page_params} from "./base_page_params.ts";

assert(base_page_params.page_type === "home");

// We use this comment so it can ignore the ignore the export  style
// so that we don't break the Types for the rest of the app.
// eslint-disable-next-line unicorn/prefer-export-from
export const page_params = base_page_params;
