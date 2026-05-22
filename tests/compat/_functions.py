import re

try:
    from _const import ALPHABET
except ImportError:
    from tests.compat._const import ALPHABET


def is_whole(s):
    try:
        es = int(s)
        es2 = float(s)
        if es2 - es == 0:
            return True
        else:
            return False
    except:
        return False


def is_float(s):
    try:
        es = int(s)
        es2 = float(s)
        if es2 - es != 0:
            return True
        else:
            return False
    except:
        try:
            es2 = float(s)
            return True
        except:
            return False


def is_number(s):
    try:
        float(s)
    except:
        return False
    return True


def strip_alpha(string, spaces=False):
    if spaces:
        return ''.join([x for x in list(string) if x.upper() in ALPHABET[:26] or x == " "])
    return ''.join([x for x in list(string) if x.upper() in ALPHABET[:26]])


def match_count(pattern, search_string):
    total = 0
    start = 0
    there = re.compile(pattern)
    while True:
        mo = there.search(search_string, start)
        if mo is None:
            return total
        total += 1
        start = 1 + mo.start()
