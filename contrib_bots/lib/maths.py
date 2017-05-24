# See readme.md for instructions on running this code.
from __future__ import absolute_import
from __future__ import print_function
import operator
from six.moves import map

class MathsHandler(object):
    '''
    This plugin allows you to complete maths equations
    quickly when in the middle of a chat. It looks for
    @maths and @math.

    This bot sends the maths solutions to the
    stream from which they are sent. More operations can
    easily be added by creating a function for each operation.
    An example use case of the bot is '@maths 4 * 12'
    This will return (To the current stream):
    '''
    def usage(self):
        return '''
            This plugin will allow users to complete maths
            calculations. Users should preface
            messages with "@maths or @math".

            Make sure to use this in the stream in which you want the answer.
            If you want to keep it private, send a private message to the
            bot.
            This bot currently contains only:
            Addition : +
            Multiplication : *
            Subtraction: -
            Division: /
            Brackets ()
            '''

    def triage_message(self, message):
        # return True iff we want to (possibly) response to this message

        original_content = message['content']

        is_maths_exp = (original_content.startswith('@maths') or
                        original_content.startswith('@math'))

        return is_maths_exp

    def handle_message(self, message, client, state_handler):
        original_content = message['content']
        original_sender = message['sender_email']
        original_subject = message['subject']
        sender_name = message['sender_full_name']
        maths_vals = MathsCalculator().parse_expression(original_content) # Gets the results of the parsing
        # including the numbers used, operations used, error status and original expression
        original_expression = maths_vals[3] # Used in bot response
        if maths_vals[2] == False: # Checks that there isn't an error
            answer = MathsCalculator().do_maths(maths_vals[0], maths_vals[1])
            new_content = ("@**" + sender_name + "** Mathsbot:" + original_expression +
                           " = "+str(answer)) # Answer message
        else:
            new_content = ("@**" + sender_name + "** Mathsbot: There is an error with" + original_expression +
                           ". You may have used an unknown/incorrect operator" +
                           " or left out a number/operator :slightly_frowning_face:") # Error Message
        if message['type'] == 'private': # Code for a Private Message to the bot

            client.send_message(dict(
                type='private',
                to=original_sender,
                content=new_content,
            ))
        else: # Code for a Stream Message to the bot
            client.send_message(dict(
                type='stream',
                subject=original_subject,
                to=message['display_recipient'],
                content=new_content,
            ))

class MathsCalculator(object):

    def is_number(self, x): # Checks whether a string is a number or not (used for confirming user input)
        try:
            float(x)
            return True
        except ValueError:
            return False

    def do_maths(self, maths_nums, maths_ops):

        operator_order = ('*', '/', '+', '-')  # order of operations goes from left to right.
    # If adding operators, remember to add them here ^^^^ as well
    # Assign operators to the operator functions
        op_dict = {'*': operator.mul, '/': operator.div, '+': operator.add, '-': operator.sub} # You can add your own operators here
        calc_len_lvl = len(maths_nums)-1
        while calc_len_lvl >= 0:
            print(calc_len_lvl)
            nums_current_lvl = maths_nums[calc_len_lvl]
            if calc_len_lvl in maths_ops:
                ops_current_lvl = maths_ops[calc_len_lvl]
            parts = []
            op_parts = []
            prev_pipe_char = -1
            for i in range(0, len(nums_current_lvl)):
                print(i)
                print(nums_current_lvl)
                if nums_current_lvl[i] == "|":
                    if i > 0:
                        parts.append(list(nums_current_lvl[prev_pipe_char+1:i]))
                        prev_pipe_char = i
                    else:
                        prev_pipe_char = i
                        print(parts)
            prev_pipe_char = -1
            for i in range(0, len(ops_current_lvl)):
                print(i)
                print(ops_current_lvl)
                if ops_current_lvl[i] == "|":
                    if i > 0:
                        op_parts.append(list(ops_current_lvl[prev_pipe_char+1:i]))
                        prev_pipe_char = i
                    else:
                        prev_pipe_char = i
                        print(op_parts)
            if len(parts) == 0:
                print("Hi")
                parts.append(nums_current_lvl)

            if len(op_parts) == 0:
                print("Hi")
                op_parts.append(ops_current_lvl)
            print(parts)
            for part in parts:
                nums_left = len(part)
                part_num = parts.index(part)
                op_part = op_parts[part_num]
                print(part)
                print(op_parts)
                print("Op Part" + str(op_part))
                while nums_left > 1:# Operator with this importance exists
                    for x in operator_order: # Loop over levels of 'importance'
                        print(x)
                        while any(o in op_part for o in x) and nums_left > 1:
                            print("Nums Left: " + str(nums_left) + "Part: " + str(part))
                            idx, oo = next((i, o) for i, o in enumerate(op_part) if o in x)# Next operator with this importance
                            print("IDX: " + str(idx))
                            op_part.pop(idx)# remove this operator from the operator list
                            values = list(map(float, part[idx:idx+2])) # here I just assume float for everything
                            print(values)
                            value = op_dict[oo](*values)
                            part[idx:idx+2] = [value] # Get rid of the integers
                            nums_left = len(part)
                            print(maths_ops)
                    print(maths_nums)
                    print(maths_ops)
                    print(part)
                if calc_len_lvl != 0:
                    marker = maths_nums[calc_len_lvl-1].index("#")
                    maths_nums[calc_len_lvl-1][marker] = str(part[0])
                    print(maths_nums[calc_len_lvl-1][marker])
            calc_len_lvl -= 1
            print("lol" + str(maths_nums) + str(maths_ops))
            print(maths_nums[0])
        return maths_nums[0][0]

    def parse_expression(self, message_content):
# Determines the operation which is being used and parses the expression
        maths_exp = message_content.replace('@maths', '').replace('@math', '') # Used for Bot response later
        calc = ''.join(maths_exp.split())
        operators = set('+-*/') # If adding operators, remember to add them here as well
        ops = {}# Operators in string
        nums = {}   # Non-operators
        buffer = [] # Buffer
        error = False # Math Error Boolean
        prevval = None # Var containing the previous value (Operator or Number)
        negnum = False # Var for creating negative numbers
        brac_lvl = 0
        charnum = 0 # Number of char in calculation
        for i in calc:  # Look at each character
            charnum += 1
            if negnum:
                i = "-"+i
                negnum = False
            if i in operators and prevval is not None and prevval != "op" and charnum != len(calc):  # Check for valid operators
                if buffer:
                    nums.setdefault(brac_lvl, list()).append(''.join(buffer))
                    buffer = []
                ops.setdefault(brac_lvl, list()).append(i)
                prevval = "op"
            elif i == "-" and charnum != len(calc):
                negnum = True
                prevval = "op"
            elif i == "(" and charnum != len(calc):
                if buffer:
                    nums.setdefault(brac_lvl, list()).append(''.join(buffer))
                    ops.setdefault(brac_lvl, list()).append("*")
                buffer = ['#'] # Bracket location indicator
                nums.setdefault(brac_lvl, list()).append(''.join(buffer))
                buffer = []
                brac_lvl += 1
            elif i == "-(" and charnum != len(calc):
                nums.setdefault(brac_lvl, list()).append("-1")
                ops.setdefault(brac_lvl, list()).append("*")
                buffer = ['#']
                nums.setdefault(brac_lvl, list()).append(''.join(buffer))
                buffer = []
                brac_lvl += 1
            elif i == ")":
                if buffer:
                    nums.setdefault(brac_lvl, list()).append(''.join(buffer))
                buffer = ['|'] # Bracket splitting indicator]
                nums.setdefault(brac_lvl, list()).append(''.join(buffer))
                ops.setdefault(brac_lvl, list()).append("|")
                buffer = []
                brac_lvl -= 1
            elif self.is_number(i):
            # Stuff that isn't operators.These characters go to the buffer.
                buffer.append(i)
                prevval = "num"
            else:
                print("There is an Error")
                error = True
            print(buffer)

        if buffer:
            nums.setdefault(brac_lvl, list()).append(''.join(buffer))
        print(nums)
        print(ops)
        print(error)
        print(maths_exp)
        return nums, ops, error, maths_exp


def test():
    assert str(MathsCalculator().parse_expression("@math 3+3-3*3/3")) == ("({0: ['3', '3', '3', '3', '3']}, {0: ['+', '-', '*', '/']}, False, ' 3+3-3*3/3')")
    assert str(MathsCalculator().parse_expression("@math ????")) == "({}, {}, True, '????')"
    assert str(MathsCalculator().parse_expression("@math 12+(3(2+4(9+2)))")) == ("({0: ['12', '#'], 1: ['3', '#', '|'], 2: ['2', '4', '#', '|'], 3: ['9', '2', '|']}, {0: ['+'], 1: ['*', '|'], 2: ['+', '*', '|'], 3: ['+', '|']}, False, '12+(3(2+4(9+2)))')")
    assert str(MathsCalculator().do_maths({0: ['6', '12']}, {0: ['*']})) == "72.0"
    assert str(MathsCalculator().do_maths({0: ['#', '6', '#'], 1: ['3', '12', '|', '3', '5', '|']}, {0: ['+', '*'], 1: ['*', '|', '+', '|']})) == "84.0"
    


handler_class = MathsHandler

if __name__ == '__main__': # Temporary testing framework
    test()
