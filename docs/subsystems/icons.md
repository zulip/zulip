# Icons

## Adding a new icon

A new feature may require a new icon to represent it, for example to be used
next to a menu option. The issue you're working on may not have an icon
specified upfront. In this case, you should:

1. Prototype using a [Lucide icon](https://lucide.dev/icons/), which is the
   default source for icons in Zulip.

1. **When your feature is nearing completion**, post in the [appropriate
   channel](https://zulip.com/development-community/#where-do-i-send-my-message)
   in the Zulip development community to discuss what icon should be used (e.g.,
   #design for web app icons). You can use the discussion thread linked from the
   issue you're working on if there is one.

1. Once there is general consensus, @-mention Zulip's designer (Vlad Korobov) to
   ask him to prepare the icon to be used.

1. Follow the [attribution guidelines](../contributing/licensing.md)
   to document the icon source.

## Changing an icon

When changing an icon for an existing feature, be sure to [update the help
center](../documentation/helpcenter.md#icons) accordingly (`git grep` is your
friend).
