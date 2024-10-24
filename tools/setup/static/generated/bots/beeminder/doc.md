# Beeminder bot

The Beeminder bot can help you adding datapoints towards
your Beeminder goal from Zulip.

To use the Beeminder bot, you can simply call it with `@beeminder`
followed by a daystamp, value and an optional comment.

Syntax is like:
```
@beeminder daystamp, value, comment  
```

**NOTE** : **Commas** between inputs are a must, otherwise,
you'll get an error.

## Setup and Configuration

Before running Beeminder bot you will need three things as follows :

1.  **auth_token**
  - Go to your [Beeminder](https://www.beeminder.com/) **account settings**.
Under **APPS & API** section you will find your **auth token**.

2. **username**
  - Your Beeminder username.

3. **Goalname**
  - The name of your Beeminder goal for which you want to
add datapoints from [Zulip](https://zulipchat.com/)

Once you have above information, you should supply
them in `beeminder.conf` file.

Run this bot as described in
[here](https://zulipchat.com/api/running-bots#running-a-bot).

## Usage

You can give command to add datapoint in 4 ways:

1. `@beeminder daystamp, value, comment`
  - Example usage: `@beeminder 20180125, 15, Adding datapoint`.
  - This will add a datapoint to your Beeminder goal having
**daystamp**: `20180125`, **value**: `15` with
**comment**: `Adding datapoint`.

2. `@beeminder daystamp, value`
  - Example usage: `@beeminder 20180125, 15`.
  - This will add a datapoint in your Beeminder goal having
**daystamp**: `20180125`, **value**: `15` and **comment**: `None`.

3. `@beeminder value, comment`
  - Example usage: `@beeminder 15, Adding datapoint`.
  - This will add a datapoint in your Beeminder goal having
**daystamp**: `current daystamp`, **value**: `15` and **comment**: `Adding datapoint`.

4. `@beeminder value`
  - Example usage: `@beeminder 15`.
  - This will add a datapoint in your Beeminder goal having
**daystamp**: `current daystamp`, **value**: `15` and **comment**: `None`.

5. `@beeminder ` or `@beeminder help` will fetch you the `help message`.
