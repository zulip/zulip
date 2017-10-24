# UI: Input Pills

This is a high level and API explanation of the input pill interface in the
frontend of the Zulip web application.

# Setup

A pill container should have the following markup:

```html
<div class="pill-container">
    <div class="input" contenteditable="true"></div>
</div>
```

The pills will automatically be inserted in before the ".input" in order.

# Basic Example

```js
var pc = input_pill($("#input_container"));
```

# Advanced Example

```html
<div class="pill-container" id="input_container">
    <div class="input" contenteditable="true"></div>
</div>
<button>Submit</button>
```

```js
var pc = input_pill($("#input_container").eq(0));

// this is a map of user emails to their IDs.
var map = {
    "user@gmail.com": 112,
    "example@zulip.com": 18,
    "test@example.com": 46,
    "oh@oh.io": 2,
};

// when a user tries to create a pill (by clicking enter), check if the map
// contains an entry for the user email entered, and if not, reject the entry.
// otherwise, return the ID of the user as a key.
pc.onPillCreate(function (value, reject) {
    var key = map[value];

    if (typeof key === "undefined") reject();

    return key;
});

// this is a submit button
$("#input_container + button").click(function () {
    // log both the keys and values.
    // the keys would be the human-readable values, and the IDs the optional
    // values that are returned in the `onPillCreate` method.
    console.log(pc.keys(), pc.values());
});
```
