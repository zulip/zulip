import {html, to_html} from "../shared/src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_keyboard_shortcuts() {
    const out = html`<div
        class="overlay-modal"
        id="keyboard-shortcuts"
        tabindex="-1"
        role="dialog"
        aria-label="${$t({defaultMessage: "Keyboard shortcuts"})}"
    >
        <div
            class="overlay-scroll-container"
            data-simplebar
            data-simplebar-tab-index="-1"
            data-simplebar-auto-hide="false"
        >
            <div>
                <table class="hotkeys_table table table-striped table-bordered">
                    <thead>
                        <tr>
                            <th colspan="2">${$t({defaultMessage: "The basics"})}</th>
                        </tr>
                    </thead>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Reply to message"})}</td>
                        <td>
                            <span class="hotkey"><kbd>Enter</kbd> or <kbd>R</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "New channel message"})}</td>
                        <td>
                            <span class="hotkey"><kbd>C</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "New direct message"})}</td>
                        <td>
                            <span class="hotkey"><kbd>X</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Paste formatted text"})}</td>
                        <td>
                            <span class="hotkey"><kbd>Ctrl</kbd> + <kbd>V</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Paste as plain text"})}</td>
                        <td>
                            <span class="hotkey"
                                ><kbd data-mac-following-key="⌥">Ctrl</kbd> + <kbd>Shift</kbd> +
                                <kbd>V</kbd></span
                            >
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "Cancel compose and save draft"})}
                        </td>
                        <td>
                            <span class="hotkey"
                                ><kbd>Esc</kbd> or <kbd data-mac-key="Ctrl">Ctrl</kbd> +
                                <kbd>[</kbd></span
                            >
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "View drafts"})}</td>
                        <td>
                            <span class="hotkey"><kbd>D</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Next message"})}</td>
                        <td>
                            <span class="hotkey"
                                ><kbd class="arrow-key">↓</kbd> or <kbd>J</kbd></span
                            >
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Last message"})}</td>
                        <td>
                            <span class="hotkey"
                                ><kbd>End</kbd> or <kbd>Shift</kbd> + <kbd>G</kbd></span
                            >
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Next unread topic"})}</td>
                        <td>
                            <span class="hotkey"><kbd>N</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "Next unread followed topic"})}
                        </td>
                        <td>
                            <span class="hotkey"><kbd>Shift</kbd> + <kbd>N</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "Next unread direct message"})}
                        </td>
                        <td>
                            <span class="hotkey"><kbd>P</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Initiate a search"})}</td>
                        <td>
                            <span class="hotkey"
                                ><kbd>Ctrl</kbd> + <kbd>K</kbd> or <kbd>/</kbd></span
                            >
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "Show keyboard shortcuts"})}
                        </td>
                        <td>
                            <span class="hotkey"><kbd>?</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Go to your home view"})}</td>
                        <td>
                            <span class="hotkey"
                                ><kbd data-mac-key="Ctrl">Ctrl</kbd> + <kbd>[</kbd
                                ><span id="go-to-home-view-hotkey-help">
                                    or <kbd>Esc</kbd></span
                                ></span
                            >
                        </td>
                    </tr>
                </table>
            </div>
            <div>
                <table class="hotkeys_table table table-striped table-bordered">
                    <thead>
                        <tr>
                            <th colspan="2">${$t({defaultMessage: "Search"})}</th>
                        </tr>
                    </thead>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Initiate a search"})}</td>
                        <td>
                            <span class="hotkey"
                                ><kbd>Ctrl</kbd> + <kbd>K</kbd> or <kbd>/</kbd></span
                            >
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Filter channels"})}</td>
                        <td>
                            <span class="hotkey"><kbd>Q</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Filter users"})}</td>
                        <td>
                            <span class="hotkey"><kbd>W</kbd></span>
                        </td>
                    </tr>
                </table>
            </div>
            <div>
                <table class="hotkeys_table table table-striped table-bordered">
                    <thead>
                        <tr>
                            <th colspan="2">${$t({defaultMessage: "Scrolling"})}</th>
                        </tr>
                    </thead>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Previous message"})}</td>
                        <td>
                            <span class="hotkey"
                                ><kbd class="arrow-key">↑</kbd> or <kbd>K</kbd></span
                            >
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Next message"})}</td>
                        <td>
                            <span class="hotkey"
                                ><kbd class="arrow-key">↓</kbd> or <kbd>J</kbd></span
                            >
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Scroll up"})}</td>
                        <td>
                            <span class="hotkey"
                                ><kbd>PgUp</kbd> or <kbd>Fn</kbd> +
                                <kbd class="arrow-key">↑</kbd> or <kbd>Shift</kbd> +
                                <kbd>K</kbd></span
                            >
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Scroll down"})}</td>
                        <td>
                            <span class="hotkey"
                                ><kbd>PgDn</kbd> or <kbd>Fn</kbd> +
                                <kbd class="arrow-key">↓</kbd> or <kbd>Shift</kbd> + <kbd>J</kbd> or
                                <kbd>Space</kbd></span
                            >
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Last message"})}</td>
                        <td>
                            <span class="hotkey"
                                ><kbd>End</kbd> or <kbd>Fn</kbd> + <kbd class="arrow-key">→</kbd> or
                                <kbd>Shift</kbd> + <kbd>G</kbd></span
                            >
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "First message"})}</td>
                        <td>
                            <span class="hotkey"
                                ><kbd>Home</kbd>or <kbd>Fn</kbd> +
                                <kbd class="arrow-key">←</kbd></span
                            >
                        </td>
                    </tr>
                </table>
            </div>
            <div>
                <table class="hotkeys_table table table-striped table-bordered">
                    <thead>
                        <tr>
                            <th colspan="2">${$t({defaultMessage: "Navigation"})}</th>
                        </tr>
                    </thead>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "Go back through viewing history"})}
                        </td>
                        <td>
                            <span class="hotkey"
                                ><kbd data-mac-key="⌘">Alt</kbd> +
                                <kbd class="arrow-key">←</kbd></span
                            >
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "Go forward through viewing history"})}
                        </td>
                        <td>
                            <span class="hotkey"
                                ><kbd data-mac-key="⌘">Alt</kbd> +
                                <kbd class="arrow-key">→</kbd></span
                            >
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "Go to topic or DM conversation"})}
                        </td>
                        <td>
                            <span class="hotkey"><kbd>S</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "Go to channel feed from topic view"})}
                        </td>
                        <td>
                            <span class="hotkey"><kbd>S</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "Go to direct message feed"})}
                        </td>
                        <td>
                            <span class="hotkey"><kbd>Shift</kbd> + <kbd>P</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "Zoom to message in conversation context"})}
                        </td>
                        <td>
                            <span class="hotkey"><kbd>Z</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "Go to next unread topic"})}
                        </td>
                        <td>
                            <span class="hotkey"><kbd>N</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "Go to next unread followed topic"})}
                        </td>
                        <td>
                            <span class="hotkey"><kbd>Shift</kbd> + <kbd>N</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "Go to next unread direct message"})}
                        </td>
                        <td>
                            <span class="hotkey"><kbd>P</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "Cycle between channel views"})}
                        </td>
                        <td>
                            <span class="hotkey"
                                ><kbd>Shift</kbd> + <kbd>A</kbd> or <kbd>Shift</kbd> +
                                <kbd>D</kbd></span
                            >
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Go to inbox"})}</td>
                        <td>
                            <span class="hotkey"><kbd>Shift</kbd> + <kbd>I</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "Go to recent conversations"})}
                        </td>
                        <td>
                            <span class="hotkey"><kbd>T</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Go to combined feed"})}</td>
                        <td>
                            <span class="hotkey"><kbd>A</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "Go to starred messages"})}
                        </td>
                        <td>
                            <span class="hotkey"><kbd>*</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "Go to the conversation you are composing to"})}
                        </td>
                        <td>
                            <span class="hotkey"><kbd>Ctrl</kbd> + <kbd>.</kbd></span>
                        </td>
                    </tr>
                </table>
            </div>
            <div>
                <table class="hotkeys_table table table-striped table-bordered">
                    <thead>
                        <tr>
                            <th colspan="2">${$t({defaultMessage: "Composing messages"})}</th>
                        </tr>
                    </thead>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "New channel message"})}</td>
                        <td>
                            <span class="hotkey"><kbd>C</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "New direct message"})}</td>
                        <td>
                            <span class="hotkey"><kbd>X</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Reply to message"})}</td>
                        <td>
                            <span class="hotkey"><kbd>Enter</kbd> or <kbd>R</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "Quote and reply to message"})}
                        </td>
                        <td>
                            <span class="hotkey"><kbd>></kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "Reply directly to sender"})}
                        </td>
                        <td>
                            <span class="hotkey"><kbd>Shift</kbd> + <kbd>R</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "Reply @-mentioning sender"})}
                        </td>
                        <td>
                            <span class="hotkey"><kbd>@</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Send message"})}</td>
                        <td>
                            <span class="hotkey"
                                ><kbd>Tab</kbd> then <kbd>Enter</kbd> or <kbd>Ctrl</kbd> +
                                <kbd>Enter</kbd></span
                            >
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Insert new line"})}</td>
                        <td>
                            <span class="hotkey"><kbd>Shift</kbd> + <kbd>Enter</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Toggle preview mode"})}</td>
                        <td>
                            <span class="hotkey"><kbd>Alt</kbd> + <kbd>P</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "Cancel compose and save draft"})}
                        </td>
                        <td>
                            <span class="hotkey"
                                ><kbd>Esc</kbd> or <kbd data-mac-key="Ctrl">Ctrl</kbd> +
                                <kbd>[</kbd></span
                            >
                        </td>
                    </tr>
                </table>
            </div>
            <div>
                <table class="hotkeys_table table table-striped table-bordered">
                    <thead>
                        <tr>
                            <th colspan="2">${$t({defaultMessage: "Message actions"})}</th>
                        </tr>
                    </thead>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "Edit your last message"})}
                        </td>
                        <td>
                            <span class="hotkey"><kbd class="arrow-key">←</kbd></span>
                        </td>
                    </tr>
                    <tr id="edit-message-hotkey-help">
                        <td class="definition">
                            ${$t({defaultMessage: "Edit selected message or view source"})}
                        </td>
                        <td>
                            <span class="hotkey"><kbd>E</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "Show message sender's user card"})}
                        </td>
                        <td>
                            <span class="hotkey"><kbd>U</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "View read receipts"})}</td>
                        <td>
                            <span class="hotkey"><kbd>Shift</kbd> + <kbd>V</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Show images in thread"})}</td>
                        <td>
                            <span class="hotkey"><kbd>V</kbd></span>
                        </td>
                    </tr>
                    <tr id="move-message-hotkey-help">
                        <td class="definition">
                            ${$t({defaultMessage: "Move messages or topic"})}
                        </td>
                        <td>
                            <span class="hotkey"><kbd>M</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "View edit and move history"})}
                        </td>
                        <td>
                            <span class="hotkey"><kbd>Shift</kbd> + <kbd>H</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Star selected message"})}</td>
                        <td>
                            <span class="hotkey"><kbd>Ctrl</kbd> + <kbd>S</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "React to selected message with"})}
                            <img
                                alt=":thumbs_up:"
                                class="emoji"
                                src="../../static/generated/emoji/images/emoji/unicode/1f44d.png"
                                title=":thumbs_up:"
                            />
                        </td>
                        <td>
                            <span class="hotkey"><kbd>+</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">
                            ${$t({
                                defaultMessage: "Toggle first emoji reaction on selected message",
                            })}
                        </td>
                        <td>
                            <span class="hotkey"><kbd>=</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "Mark as unread from selected message"})}
                        </td>
                        <td>
                            <span class="hotkey"><kbd>Shift</kbd> + <kbd>U</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "Collapse/show selected message"})}
                        </td>
                        <td>
                            <span class="hotkey"><kbd>-</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Toggle topic mute"})}</td>
                        <td>
                            <span class="hotkey"><kbd>Shift</kbd> + <kbd>M</kbd></span>
                        </td>
                    </tr>
                </table>
            </div>
            <div>
                <table class="hotkeys_table table table-striped table-bordered">
                    <thead>
                        <tr>
                            <th colspan="2">${$t({defaultMessage: "Recent conversations"})}</th>
                        </tr>
                    </thead>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "View recent conversations"})}
                        </td>
                        <td>
                            <span class="hotkey"><kbd>T</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Filter topics"})}</td>
                        <td>
                            <span class="hotkey"><kbd>T</kbd></span>
                        </td>
                    </tr>
                </table>
            </div>
            <div>
                <table class="hotkeys_table table table-striped table-bordered">
                    <thead>
                        <tr>
                            <th colspan="2">${$t({defaultMessage: "Drafts"})}</th>
                        </tr>
                    </thead>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "View drafts"})}</td>
                        <td>
                            <span class="hotkey"><kbd>D</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Edit selected draft"})}</td>
                        <td>
                            <span class="hotkey"><kbd>Enter</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Delete selected draft"})}</td>
                        <td>
                            <span class="hotkey"><kbd>Backspace</kbd></span>
                        </td>
                    </tr>
                </table>
            </div>
            <div>
                <table class="hotkeys_table table table-striped table-bordered">
                    <thead>
                        <tr>
                            <th colspan="2">${$t({defaultMessage: "Menus"})}</th>
                        </tr>
                    </thead>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Toggle the gear menu"})}</td>
                        <td>
                            <span class="hotkey"><kbd>G</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Open personal menu"})}</td>
                        <td>
                            <span class="hotkey"><kbd>G</kbd><kbd class="arrow-key">→</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Open help menu"})}</td>
                        <td>
                            <span class="hotkey"><kbd>G</kbd><kbd class="arrow-key">←</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Open message menu"})}</td>
                        <td>
                            <span class="hotkey"><kbd>I</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Open reactions menu"})}</td>
                        <td>
                            <span class="hotkey"><kbd>:</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "Show keyboard shortcuts"})}
                        </td>
                        <td>
                            <span class="hotkey"><kbd>?</kbd></span>
                        </td>
                    </tr>
                </table>
            </div>
            <div>
                <table class="hotkeys_table table table-striped table-bordered">
                    <thead>
                        <tr>
                            <th colspan="2">${$t({defaultMessage: "Channel settings"})}</th>
                        </tr>
                    </thead>
                    <tr>
                        <td class="definition">
                            ${$t({defaultMessage: "Scroll through channels"})}
                        </td>
                        <td>
                            <span class="hotkey"
                                ><kbd class="arrow-key">↑</kbd> or
                                <kbd class="arrow-key">↓</kbd></span
                            >
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Switch between tabs"})}</td>
                        <td>
                            <span class="hotkey"
                                ><kbd class="arrow-key">←</kbd> or
                                <kbd class="arrow-key">→</kbd></span
                            >
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "View channel messages"})}</td>
                        <td>
                            <span class="hotkey"><kbd>Shift</kbd> + <kbd>V</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">
                            ${$t({
                                defaultMessage: "Subscribe to/unsubscribe from selected channel",
                            })}
                        </td>
                        <td>
                            <span class="hotkey"><kbd>Shift</kbd> + <kbd>S</kbd></span>
                        </td>
                    </tr>
                    <tr>
                        <td class="definition">${$t({defaultMessage: "Create new channel"})}</td>
                        <td>
                            <span class="hotkey"><kbd>N</kbd></span>
                        </td>
                    </tr>
                </table>
            </div>
            <hr />
            <a href="/help/keyboard-shortcuts" target="_blank" rel="noopener noreferrer"
                >${$t({defaultMessage: "Detailed keyboard shortcuts documentation"})}</a
            >
        </div>
    </div> `;
    return to_html(out);
}
