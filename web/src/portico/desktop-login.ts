import {electron_bridge} from "../electron_bridge.ts";

document.querySelector<HTMLFormElement>("form#form")!.addEventListener("submit", () => {
    document.querySelector<HTMLParagraphElement>("p#bad-token")!.hidden = false;
});
document.querySelector<HTMLInputElement>("input#token")!.focus();

async function decrypt_manual(): Promise<{key: Uint8Array; pasted: Promise<string>}> {
    const key = await crypto.subtle.generateKey({name: "AES-GCM", length: 256}, true, ["decrypt"]);
    return {
        key: new Uint8Array(await crypto.subtle.exportKey("raw", key)),
        pasted: new Promise((resolve) => {
            const tokenElement = document.querySelector<HTMLInputElement>("input#token")!;
            tokenElement.addEventListener("input", () => {
                void (async () => {
                    document.querySelector<HTMLParagraphElement>("p#bad-token")!.hidden = true;
                    document.querySelector<HTMLButtonElement>("button#submit")!.disabled =
                        tokenElement.value === "";
                    try {
                        const data = new Uint8Array(
                            tokenElement.value.match(/../g)?.map((b) => Number.parseInt(b, 16)) ??
                                [],
                        );
                        const iv = data.slice(0, 12);
                        const ciphertext = data.slice(12);
                        const plaintext = await crypto.subtle.decrypt(
                            {name: "AES-GCM", iv},
                            key,
                            ciphertext,
                        );
                        resolve(new TextDecoder().decode(plaintext));
                    } catch {
                        // Ignore all parsing and decryption failures.
                    }
                })();
            });
        }),
    };
}

void (async () => {
    // Sufficiently new versions of the desktop app provide the
    // electron_bridge.decrypt_clipboard API, which returns AES-GCM encryption
    // key and a promise; as soon as something encrypted to that key is copied
    // to the clipboard, the app decrypts it and resolves the promise to the
    // plaintext.  This lets us skip the manual paste step.
    const {key, pasted} = electron_bridge?.decrypt_clipboard
        ? electron_bridge.decrypt_clipboard(1)
        : await decrypt_manual();

    const keyHex = [...key].map((b) => b.toString(16).padStart(2, "0")).join("");
    window.open(
        (window.location.search ? window.location.search + "&" : "?") +
            "desktop_flow_otp=" +
            encodeURIComponent(keyHex),
        "_blank",
    );

    const token = await pasted;
    document.querySelector<HTMLFormElement>("form#form")!.hidden = true;
    document.querySelector<HTMLParagraphElement>("p#done")!.hidden = false;
    window.location.href = "/accounts/login/subdomain/" + encodeURIComponent(token);
})();
