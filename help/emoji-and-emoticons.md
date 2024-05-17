# Emoji and emoticons

{!emoji-and-emoticons-intro.md!}

!!! tip ""

    You can also quickly respond to a message by using [emoji reactions](/help/emoji-reactions).

## Use an emoji in your message

{start_tabs}

{tab|via-compose-box-buttons}

{!start-composing.md!}

1. Click the **smiley face** (<i class="zulip-icon zulip-icon-smile-bigger"></i>)
   icon at the bottom of the compose box.

1. Select an emoji. You can type to search, use the arrow keys, or click on
   an emoji with your mouse.

{tab|via-markdown}

{!start-composing.md!}

1. Type `:`, followed by a few letters from the emoji name, to see autocomplete
   suggestions. The letters don't have to be at the beginning of the emoji name.
   For example, `:app` will match both `:apple:` and `:pineapple:`.

1. Type the full emoji name followed by `:`, or select an emoji from the list of
   suggestions.

{tab|via-paste}

{!start-composing.md!}

1. Paste an emoji copied from outside of Zulip directly into the compose box.

{end_tabs}

!!! tip ""

    You can hover over an emoji in the emoji picker, a message, or an [emoji
    reaction](/help/emoji-reactions) to learn its name.

### Use an emoticon

You can configure Zulip to convert emoticons into emoji, so that, e.g., `:)`
will be displayed as
<img
    src="/static/generated/emoji/images-google-64/1f642.png"
    alt="smile"
    class="emoji-small"
/>
.

{start_tabs}

{settings_tab|preferences}

1. Under **Emoji settings**, select **Convert emoticons before sending**.

{end_tabs}

The list of supported emoticons is available
[here](/help/configure-emoticon-translations).

## Examples

{!emoji-and-emoticons-examples.md!}

## Use an emoji in a topic name

You can use unicode characters in topic names, including unicode
emoji. Each platform has a different way to enter unicode
emoji. [Custom emoji](/help/custom-emoji) cannot be used in topic
names.

{start_tabs}

{tab|mac}

1. [Start a new topic](/help/introduction-to-topics#how-to-start-a-new-topic).

1. Press <kbd>Command ⌘</kbd> + <kbd>Control</kbd> + <kbd>Space</kbd>
   to open the **Character Viewer**. See the
   [macOS documentation](https://support.apple.com/guide/mac-help/use-emoji-and-symbols-on-mac-mchlp1560/mac)
   to learn more.

1. Select an emoji. You can type to search, use the arrow keys, or click on
   an emoji with your mouse.

{tab|windows}

1. [Start a new topic](/help/introduction-to-topics#how-to-start-a-new-topic).

1. Press <kbd>Windows</kbd> + <kbd>.</kbd>
   to open the **emoji keyboard**. See the
   [Windows documentation](https://support.microsoft.com/en-us/windows/windows-keyboard-tips-and-tricks-588e0b72-0fff-6d3f-aeee-6e5116097942)
   to learn more.

1. Select an emoji. You can type to search, use the arrow keys, or click on
   an emoji with your mouse.

{tab|linux}

1. [Start a new topic](/help/introduction-to-topics#how-to-start-a-new-topic).

1. Open the [Characters app for GNOME](https://apps.gnome.org/en/Characters/).

1. Select an emoji. You can type to search, use the arrow keys, or click on
   an emoji with your mouse.

{tab|chrome}

1. [Start a new topic](/help/introduction-to-topics#how-to-start-a-new-topic).

1. Right-click on the text input box.

1. Select **Emoji** or **Emoji & Symbols**. You will only see this option if
   supported by your operating system.

1. Select an emoji. You can type to search, use the arrow keys, or click on
   an emoji with your mouse.

{tab|via-paste}

1. [Start a new topic](/help/introduction-to-topics#how-to-start-a-new-topic).

1. Paste an emoji copied from outside of Zulip directly into the text input box.

!!! tip ""

    <https://emojipedia.org/> may be a helpful resource.

{end_tabs}

## Change your emoji set

Your emoji set determines how you see emoji. It has no effect on the emoji
you send. Zulip emoji are compatible with screen readers and other accessibility tools.

{start_tabs}

{settings_tab|preferences}

1. Under **Emoji**, select **Google**,
   **Twitter**, **Plain text**, or **Google blobs** for the emoji theme.

{end_tabs}

!!! warn ""

    **Google blobs** is an old style of Google emoji that has not been maintained
    by Google since 2017, when they switched to a more modern style. Zulip allows
    you to still use blob emoji, but any new emoji that have been released since
    2017 will be displayed in the modern **Google** style.

## Related articles

* [Add custom emoji](/help/custom-emoji)
* [Emoji reactions](/help/emoji-reactions)
* [Configure emoticon translations](/help/configure-emoticon-translations)
