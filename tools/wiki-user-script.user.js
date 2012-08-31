// ==UserScript==
// @match https://wiki.humbughq.com/*
// ==/UserScript==

// Sets a default commit message when editing the Humbug wiki.
//
// To install in Chromium 21:
//   - Close all Chromium windows
//   - Run chromium --enable-easy-off-store-extension-install
//   - Navigate to this directory and click the link to this file.
//
// May also work in Firefox with Greasemonkey.

(function () {
    var elem = document.getElementById("logMsg");
    if (elem != null) {
        elem.value = "(default commit message)";
    }
})();
