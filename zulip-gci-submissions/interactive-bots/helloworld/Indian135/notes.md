While the set up of Zulip Bot Development 
Enviroment, on running the file 
'./tools/provision' (for installing zulip, 
zulip_bots, and zulip_botserver in 
developer mode),it gave me an output 
saying that it wasn't able to find 
'python'(I had installed python 3.6 just
before running the file) in a folder about
which I had no idea. I decided to correct 
the error on the next day. However, the 
next day, when I ran the file again, the 
error didn't show up and the file ran 
without an error. Then, I figured out that
after installing python, I had to restart 
my PC for proper functioning of python.

Another error was actually a silly 
mistake, but it is worth sharing. I tried
to run the helloworld bot without starting
my server development environment. In the 
output, I got many lines of logs and an error
at the end. The error said that it wasn't 
able to connect to the server 
'http://zulip.indian135.zulipdev.org:9991/api'.
When I saw this URL, I realised that I had not
started my development server.

I have provided you with a screenshot which 
shows the upper part of the logs which I found
when I did the silly mistake.
