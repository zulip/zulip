"use strict";

/* global chrome */

const recorderInjectedProp = "__$$PuppeteerScreenCapture_recorder_injected__";
if (!window[recorderInjectedProp]) {
    Object.defineProperty(window, recorderInjectedProp, {value: true, writable: false});

    const port = chrome.runtime.connect(chrome.runtime.id);
    port.onMessage.addListener((msg) => window.postMessage(msg, "*"));
    window.addEventListener("message", (event) => {
        // Relay client messages
        if (event.source === window && event.data.type) {
            port.postMessage(event.data);
        }

        if (event.data.type === "PLAYBACK_COMPLETE") {
            port.postMessage({type: "REC_STOP"}, "*");
        }

        if (event.data.downloadComplete) {
            const $html = document.querySelector("html");
            $html.classList.add("__PuppeteerScreenCapture_download_complete__");
            $html.dataset.puppeteerRecordingFilename = event.data.downloadFilename;
        }

        if (event.data.oldTitle) {
            document
                .querySelector("html")
                .classList.add("__PuppeteerScreenCapture_recorder_started__");
            if (document.title === "PuppeteerRecording") {
                document.title = event.data.oldTitle;
            }
        }
    });
}
