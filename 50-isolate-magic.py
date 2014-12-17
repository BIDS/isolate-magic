# put this file in .ipython/profile_[xxxxxx]/startup

__all__ = []
from IPython.core.magic import (Magics, magics_class, line_magic,
                                        cell_magic, line_cell_magic)
import re
@magics_class
class IsolateMagics(Magics):
    @cell_magic('isolate')
    def isolate(self, line, cell):
        pre, post = self.parser(line)
        print 'pre', pre
        print 'post', post
        ns = self.shell.user_ns.copy()
        for symbol in pre:
            assert symbol in ns
        exec (cell, ns)
        for symbol in post:
            self.shell.user_ns[symbol] = ns[symbol]

    def parser(self, line):
        clauses = re.findall('(\s*(pre|post)\(([^)]*)\))', line)
        pre = []
        post = []
        for c in clauses:
            if c[1].lower() == 'pre':
                pre = c[2].split(',')
            elif c[1].lower() == 'post':
                post = c[2].split(',')
        return pre, post

        eval(cell, locals)

# In order to actually use these magics, you must register them with a
# running IPython.  This code must be placed in a file that is loaded
# once
# IPython is up and running:
ip = get_ipython()
# You can register the class itself without instantiating it.  IPython
# will
# call the default constructor on it.
ip.register_magics(IsolateMagics)
