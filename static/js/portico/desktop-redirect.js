"use strict";

const ClipboardJS = require("clipboard");

new ClipboardJS("#copy");
document.querySelector("#copy").focus();
