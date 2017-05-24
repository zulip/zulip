This bot calculates and responds with the answers to mathematical expressions.
It is responsive to @math and @maths.
At the moment it uses the 'operations' module. However, new mathematical operations can
be added by creating a function for the operation and inserting the operator and function into
the 3 commented locations
This means that the bot is fully customisable and new maths operations can be added when needed.

The bot currently supports:
+ : Addition
- : Subtraction
* : Multiplication
/ : Division


The bot will respond in the stream in which you message it. For example, if you send a
Private Message to it, it will respond with a Private Message and if you message it in the
'devel' stream, it will reply in the 'devel' stream.

An Example use case looks like this:

JefftheBest1: @maths 3 * 48
MathsBot: @JefftheBest1 MathsBot: 3 * 48 = 144

An Example error case looks like this:

JefftheBest1: @maths 3+12+
MathsBot: @JefftheBest1 Mathsbot: There is an error with 3+12+ You may have used an unknown/incorrect operator
                                  or left out a number/operator :slightly_frowning_face:


