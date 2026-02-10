import ClipboardJS from "clipboard";

new ClipboardJS("#copy");
document.querySelector<HTMLElement>("#copy")!.focus();
