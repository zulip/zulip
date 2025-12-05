# Converter bot

This bot allows users to perform conversions for various measurement units.

## Usage

Run this bot as described in [here](https://zulipchat.com/api/running-bots#running-a-bot).

Use this bot with the following command

`@convert <number> <unit_from> <unit_to>`

This will convert `number`, given in the unit `unit_from`, to the unit `unit_to`
and print the result.

* `number` can be any floating-point number, e.g. 12, 13.05, 0.002.
* `unit_from` and `unit_to` are two units from [the following](#supported-units) table in the same category.
* `unit_from` and `unit_to` can be preceded by [these](#supported-prefixes) prefixes.

### Supported units

| Category | Units |
| ----------------- | ----- |
| Area | square-centimeter (cm^2, cm2), square-decimeter (dm^2, dm2), square-meter (m^2, m2), square-kilometer (km^2, km2), square-inch (in^2, in2), square-foot (ft^2, ft2), square-yard (y^2, y2), square-mile (mi^2, mi2), are (a), hectare (ha), acre (ac) |
| Information | bit, byte |
| Length | centimeter (cm), decimeter (dm), meter (m), kilometer (km), inch (in), foot (ft), yard (y), mile (mi), nautical-mile (nmi) |
| Temperature | Kelvin (K), Celsius (C), Fahrenheit (F) |
| Volume | cubic-centimeter (cm^3, cm3), cubic-decimeter (dm^3, dm3), liter (l), cubic-meter (m^3, m3), cubic-inch (in^3, in3), fluid-ounce (fl-oz), cubic-foot (ft^3, ft3), cubic-yard (y^3, y3) |
| Weight | gram (g), kilogram (kg), ton (t), ounce (oz), pound (lb) |
| Cooking (metric only, U.S. and imperial units differ slightly) | teaspoon (tsp), tablespoon (tbsp), cup |

### Supported prefixes

| Prefix | Power of 10 |
| ------ | ----------- |
| atto | 10<sup>-18</sup> |
| pico | 10<sup>-15</sup> |
| femto | 10<sup>-12</sup> |
| nano | 10<sup>-9</sup> |
| micro | 10<sup>-6</sup> |
| milli | 10<sup>-3</sup> |
| centi | 10<sup>-2</sup> |
| deci | 10<sup>-1</sup> |
| deca | 10<sup>1</sup> |
| hecto | 10<sup>2</sup> |
| kilo | 10<sup>3</sup> |
| mega | 10<sup>6</sup> |
| giga | 10<sup>9</sup> |
| tera | 10<sup>12</sup> |
| peta | 10<sup>15</sup> |
| exa | 10<sup>18</sup> |

### Usage examples

| Message | Response |
| ------- | ------ |
| `@convert 12 celsius fahrenheit` | 12.0 celsius = 53.600054 fahrenheit |
| `@convert 0.002 kilomile millimeter` | 0.002 kilomile = 3218688.0 millimeter |
| `@convert 31.5 square-mile ha  | 31.5 square-mile = 8158.4625 ha |
| `@convert 56 g lb` | 56.0 g = 0.12345887 lb |

## Notes

* You can use multiple `@convert` statements in a message, the response will look accordingly:
![multiple-converts](assets/multiple-converts.png)

* Enter `@convert help` to display a quick overview of the converter's functionality.

* For bits and bytes, the prefixes change the figure differently: 1 kilobyte is 1024 bytes,
1 megabyte is 1048576 bytes, etc.
