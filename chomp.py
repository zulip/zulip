import glob
import os
import re

FNS = 'static/js/*.js'

def fix_file(fn):
    with open(fn) as f:
        lines = f.readlines()

    with open(fn, 'r') as f:
        string = ""
        stack_ops = False
        stack_count = 0
        for line in lines:
            if not stack_ops:
                c = re.findall('\.on\(\'click\'.*({)', line, re.DOTALL)
                if c:
                    # start stack ops,
                    stack_ops = True
                    stack_count = 1
                    string = line
            else:
                open_brace = re.findall('.*({)', line, re.DOTALL)
                close_brace = re.findall('.*(})', line, re.DOTALL)
                string += line

                # xor
                if bool(open_brace) != bool(close_brace):
                    if open_brace:
                        stack_count += 1
                    else:
                        stack_count -= 1
                if (stack_count == 0):
                    if not re.findall('e\.stopPropagation\(\)', string):
                        print(f.name)
                        print(string)
                        stack_ops = False
                


def run():
    os.system('git checkout ' + FNS)

    for fn in glob.glob(FNS):
        fix_file(fn)

    os.system('git diff')

run()