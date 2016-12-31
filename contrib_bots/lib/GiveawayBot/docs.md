#Zulip Giveaway Bot - Created By Daniel O'Brien


##Overview:

This bot facilitates the creation of 'Giveaways' within Zuilip. Once a giveaway has been initialized, it will automatically count down for a set period of time and once that time has passed it will randomly choose a winner out of the people whom entered the giveaway in that time period.


##Syntax:

@giveaway init|enter|exit|cancel [giveaway_name] [giveaway_time]


##Commands:

init: Initialize a giveaway, [giveaway_name] and [giveaway_time] must also be supplied.

enter: Enter a giveaway, requires for there to already be an active giveaway to work.

exit: Exit a giveaway, requires for there to be an active giveaway in which the user is already partaking.

cancel: Cancel a giveaway, requires for there already to be an active giveaway. Can only be executed by the creator of the giveaway.


giveaway_name: The name of the giveaway the user wishes to create.
Must be 1 word/several words separated with dashes or underscores.


giveaway_time: The time, in minutes, the user wishes the giveaway to
go on for. Maximum of 100 mins to prevent a stack overflow.


##Example Usage:

@giveaway init Foobar 10 -

This command will create a giveaway called "Foobar" which will last for 10 minutes.


@giveaway enter -

This command will enter the user whom executed this command in whatever giveaway is currently running.


@giveaway exit -

Opposite of @giveaway enter (see above).


@giveaway cancel -

This command will cancel any giveaway that is currently running. Can  only be executed by the person whom created the giveaway in the first place.
