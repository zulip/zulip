"use strict";

/* global chrome, navigator, Blob, MediaRecorder, FileReader */

let recorder = null;
let filename = null;

function startRecording(port, oldTitle) {
    chrome.desktopCapture.chooseDesktopMedia(["tab", "audio"], async (streamId) => {
        const options = {
            audio: {
                mandatory: {
                    chromeMediaSource: "system",
                },
            },
            video: {
                mandatory: {
                    chromeMediaSource: "desktop",
                    chromeMediaSourceId: streamId,
                    minWidth: 1280,
                    maxWidth: 1280,
                    minHeight: 720,
                    maxHeight: 720,
                    minFrameRate: 60,
                },
            },
        };

        const stream = await navigator.mediaDevices.getUserMedia(options);
        port.postMessage({oldTitle});
        recorder = new MediaRecorder(stream, {
            videoBitsPerSecond: 2500000,
            ignoreMutedMedia: true,
            mimeType: "video/webm",
        });

        const videoChunks = [];
        recorder.ondataavailable = function (event) {
            if (event.data.size > 0) {
                videoChunks.push(event.data);
            }
        };

        recorder.onstop = function () {
            if (filename === null || filename === undefined) {
                return;
            }

            const buffer = new Blob(videoChunks, {
                type: "video/webm",
            });

            const url = URL.createObjectURL(buffer);
            chrome.downloads.download({
                url,
                filename,
            });
        };

        recorder.start();
    });
}

chrome.runtime.onConnect.addListener((port) => {
    port.onMessage.addListener(async (msg) => {
        console.log(msg);
        switch (msg.type) {
            case "SET_EXPORT_PATH":
                filename = msg.filename;
                break;

            case "REC_STOP":
                recorder.stop();
                break;

            case "REC_CLIENT_PLAY":
                if (recorder) {
                    return;
                }

                startRecording(port, msg.data.oldTitle);
                break;
        }
    });

    // Wait until download completes...
    let downloadFilename = null;
    chrome.downloads.onChanged.addListener((delta) => {
        if (delta.filename !== undefined) {
            downloadFilename = delta.filename.current;
        }

        if (!delta.state || delta.state.current !== "complete") {
            return;
        }

        try {
            port.postMessage({downloadComplete: true, downloadFilename});
        } catch (e) {
            console.error(e);
        }
    });
});
