__all__ = []
from IPython.core.magic import (Magics, magics_class, line_magic,
                                        cell_magic, line_cell_magic)
import re

class PreConditionError(NameError):
    pass
class PostConditionError(NameError):
    pass

@magics_class
class IsolateMagics(Magics):
    @cell_magic('isolate')
    def isolate(self, line, cell, protected=True):
        pre, post = self.parser(line)

        oldnames = set(self.shell.user_ns.keys())
        badnames = []

        for symbol in pre:
            if symbol.startswith('@'):
                continue
            if not symbol in oldnames:
                badnames.append(symbol)
        if len(badnames) > 0:
            raise PreConditionError("The following variables are undefined: %s",
                    str(badnames))

        # the juice is here
        # ipython processes other magics
        self.shell.run_cell(cell)

        badnames = []

        for symbol in post:
            if symbol.startswith('@'):
                continue
            if not symbol in self.shell.user_ns:
                badnames.append(symbol)

        # alright, due to #7256 we can't tell if run_cell failed or not
        # so on failures we get a second error due to post-conditions.
        if len(badnames) > 0:
            raise PostConditionError("The following variables are undefined: %s",
                    str(badnames))

        if protected:
            # now remove extra symbols in the user ns:
            for symbol in self.shell.user_ns.keys():
                if symbol not in post and symbol not in oldnames:
                    self.shell.user_ns.pop(symbol)


    def parser(self, line):
        clauses = re.findall('(\s*(pre|post)\(([^)]*)\))', line)
        pre = []
        post = []
        for c in clauses:
            if c[1].lower() == 'pre':
                pre = [a.strip() for a in c[2].split(', ')]
            elif c[1].lower() == 'post':
                post = [a.strip() for a in c[2].split(', ')]
        return pre, post


# In order to actually use these magics, you must register them with a
# running IPython.  This code must be placed in a file that is loaded
# once
# IPython is up and running:
ip = get_ipython()
# You can register the class itself without instantiating it.  IPython
# will
# call the default constructor on it.
ip.register_magics(IsolateMagics)
