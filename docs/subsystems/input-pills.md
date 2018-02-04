# UI: Input Pills

This is a high level and API explanation of the input pill interface in the
frontend of the Zulip web application.

## Setup

A pill container should have the following markup:

```html
<div class="pill-container">
    <div class="input" contenteditable="true"></div>
</div>
```

The pills will automatically be inserted in before the ".input" in order.

## Basic Example

```js
var pc = input_pill($("#input_container"));
```

## Advanced Example

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

### `onPillCreate` method

The `onPillCreate` method can have a few different key actions. The function can
work as a validator, where if the `reject` function is called, it will disable
the pill from being added to the list. You can provide a validator function and
call `reject` if the pill isn't valid.

The return type for your callback function should be what you want the key to be
(this is not the displayed value, but rather than important ID of the pill). An
example of a key vs. a value would be in the case of users. The value
(human readable) would be the name of the user. We could show their name in the
pill, but the key would represent their user ID. One could run a function like:

```js
pc.onPillCreate(function (value, reject) {
    var id = users.getIDByFullName(value);

    // user does not exist.
    if (typeof id === "undefined") {
        reject();
    }

    // return the user ID to be the key for retrieval later.
    return id;
});
```

However sometimes, we want to modify the visible text on pill submission, which
requires changing the value and setting the key. We can use the "object" return
type in the `onPillCreate` method to return a new key and value.

This could be useful in the case where a user enters a valid user email to send
to, but we want the pill to display their full name, and the key to be the user ID.

```js
pc.onPillCreate(function (value, reject) {
    var user = users.getByEmail(value);

    // user does not exist.
    if (typeof id === "undefined") {
        reject();
    }

    return { key: user.id, value: user.full_name };
});
```
