# Hotspots

Hotspots introduce users to important UI elements. They are an effective
means of guiding users towards new features and providing context where
Zulip's UI may not be self-evident.

## Adding a new hotspot

... is easy! If you are working on a new feature or think highlighting a
certain UI element would improve Zulip's user experience, we welcome you to
[open an issue](https://github.com/zulip/zulip/issues/new?title=hotspot%20request:)
for discussion.

### Step 1: Create hotspot content

In `zerver/lib/hotspots.py`, add your content to the `ALL_HOTSPOTS` dictionary.
Each key-value pair in `ALL_HOTSPOTS` associates the name of the hotspot with the
content displayed to the user.

```
ALL_HOTSPOTS = {
    ...
    'new_hotspot_name': {
        'title': 'Provide a concise title',
        'description': 'A helpful explanation goes here.',
    },
}
```

### Step 2: Configure hotspot placement

The target element and visual orientation of each hotspot is specified in
`HOTSPOT_LOCATIONS` of `static/js/hotspots.js`.

The `icon_offset` property specifies where the pulsing icon is placed *relative to
the width and height of the target element*.

By default, `popovers.compute_placement` is used to responsively
determine whether a popover is best displayed above (TOP), below (BOTTOM),
on the left (LEFT), on the right (RIGHT), or if none of those options fit,
directly in the center of the message viewport (VIEWPORT_CENTER).

However, if you would like to fix the orientation of a hotspot popover, a
`popover` property can be additionally specified.

### Step 3: Test manually

To test your hotspot in the development environment, set `SEND_ALL = True` in
`zerver/lib/hotspots.py`, and invoke `hotspots.initialize()` in your browser
console. Every hotspot should be displayed.

Here are some visual characteristics to confirm:
- popover content is readable
- icons reposition themselves on resize
- icons are hidden and shown along with their associated elements
- popovers reposition and reorient themselves on resize

### Step 4 (if necessary): Tweak hotspot icon z-index

Hotspot icons are assigned a [z-index](https://developer.mozilla.org/en-US/docs/Web/CSS/z-index)
of 100 by default, which positions them in front of all message viewport
content and behind sidebars and overlays. If a hotspot is associated with
a target element on a sidebar or overlay, the icon's z-index may need to
be increased to 101, 102, or 103.

This adjustment can be made at the bottom of `static/styles/hotspots.css`:
```
\#hotspot_new_hotspot_name_icon {
    z-index: 103;
}
```

Hotspot popover overlays are assigned the highest z-index within the web app
of 104, so icon z-indexing should not be greater than 103.
