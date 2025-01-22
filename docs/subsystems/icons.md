# Icons

Zulip makes extensive use of icons to decorate elements in the UI as
well as for compact buttons.

## Using icons

- Modern Zulip icons are implemented using `<i class="zulip-icon
zulip-icon-smile"></i>`, which is rendered using generated CSS that
  maps that class name combination to displaying the SVG file located
  at `web/shared/icons/smile.svg`.

- Older icons use [Font Awesome 4.7](https://fontawesome.com/),
  declared in our HTML via `<i class="fa fa-paperclip"></i>`. We are
  migrating away from Font Awesome both for design and licensing
  reasons (Font Awesome 5.0+ is no longer fully open source).

Always consider [accessibility](../subsystems/accessibility.md) when
using icons. Typically, this means:

- Icons that are used **purely as a decoration** to a textual label (for
  example, in our popover menus) should use `aria-hidden`, so that
  screenreaders ignore them in favor of reading the label.

- Buttons whose **entire label** is an icon should have a
  [tooltip](../subsystems/html-css.md#tooltips) as well as an
  `aria-label` declaration, so that screenreaders will explain the
  button. Generally, the tooltip text should be identical to the
  `aria-label` text.

## Adding a new icon

A new feature may require a new icon to represent it, for example to be used
next to a menu option. The issue you're working on may not have an icon
specified upfront. In this case, you should:

1. Prototype using a [Lucide icon](https://lucide.dev/icons/), which is the
   default source for icons in Zulip. SVG files must be added under
   `web/shared/icons/` (don't forget to `git add`) to be used.

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
