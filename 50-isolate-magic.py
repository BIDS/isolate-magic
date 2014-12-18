__all__ = []
from IPython.core.magic import (Magics, magics_class, line_magic,
                                        cell_magic, line_cell_magic)
import re

class PreConditionError(NameError):
    pass
class PostConditionError(NameError):
    pass

class Cell(object):
    def __init__(self, id, input, pre, post):
        self.id = id
        self.input = input
        self.pre = pre
        self.post = post
        self.fanout = {}
        self.fanin = {}

    def _fanstr(self, fan, symbols, flag):
        l = []
        for s in symbols:
            if s in fan:
                idstr = ', '.join( [ str(c.id) for c in fan[s] ])
            else:
                idstr = ''

            if flag == 'in':
                l.append('{%s => %s}' %(idstr, s))
            else:
                l.append('{%s => %s}' %(s, idstr))
        return ', '.join(l)

    def __repr__(self):
        fanin = self._fanstr(self.fanin, self.pre, 'in')
        fanout = self._fanstr(self.fanout, self.post, 'out')
        repr = "<cell %d: pre(%s) post(%s)>: %s %s" % \
                (self.id,
                        ', '.join(self.pre),
                        ', '.join(self.post),
                fanin,
                fanout,
                )
        return repr
    def link(self, next, symbol):
        if symbol not in self.fanout:
            self.fanout[symbol] = []
        self.fanout[symbol].append(next)

        if symbol not in next.fanin:
            next.fanin[symbol] = []
        next.fanin[symbol].append(self)
class Dag(object):
    def __init__(self, cells):
        self.cells = [
            parse_cell(i, cell)
            for i, cell in enumerate(cells)
            ]
        d = {}
        for cell in self.cells:
            # all post conditions are updated by this cell
            for s in cell.post:
                d[s] = cell
            for s in cell.pre:
                if s in d:
                    d[s].link(cell, s)
                else:
                    pass
                    #raise Exception("can't build DAG, insufficient input")

    def __repr__(self):
        return '\n'.join([repr(c) for c in self.cells])

    def __del__(self):
        # break the cycles
        for cell in self.cells:
            cell.fanin.clear()
            cell.fanout.clear()

@magics_class
class IsolateMagics(Magics):
    STRICT = 9     # the input is p
    UNPROTECTED = -1
    LOOSE = 0
    def __init__(self, shell):
        super(IsolateMagics, self).__init__(shell)
        self.level = self.LOOSE

    @line_magic('dag')
    def dag(self, line):
        """ make a dag !"""
        dag = Dag(self.shell.history_manager.input_hist_raw)
        print dag
    @line_magic('isolatemode')
    def isolatemode(self, line):
        """%%isolatemode [ unprotected | loose | strict ]
           Three modes are supported:

           unprotected: the pre and post clauses are descriptive only

           loose: the output is pruned. Any symbols undeclared with post clause
              is purged from the notebook namespace after the cell is done.
           strict: in addition to `loose';
              the input is pruned. Only symbols declared with pre are kept when
              the cell is ran.
        """
        line = line.lower().split()
        if 'strict' in line:
            self.level = self.STRICT
        elif 'unprotected' in line:
            self.level = self.UNPROTECTED
        elif 'loose' in line:
            self.level = self.LOOSE
        else:
            raise ValueError("Unsupported isolatemode")

    @cell_magic('isolate')
    def isolate(self, line, cell):
        """ declare symbols pre and post the cell execution

            use %%isolatemode to set the global isolation mode

            %%isolate pre(a, b, c) post(d, e, f)
            %%isolate pre(a, b, c) post(d, e, f)  pre(g, h, i)
        """
        pre, post = parse(line)

        old_ns = self.shell.user_ns.copy()

        if self.level > self.UNPROTECTED:
            badnames = [
                symbol
                for symbol in pre if not (
                    symbol.startswith('@')
                    or
                    symbol in old_ns)
            ]

            if len(badnames) > 0:
                raise PreConditionError(
                    "The following variables are undefined: {}".format(
                        ', '.join(badnames) ) )

        if self.level >= self.STRICT:
            self.shell.user_ns.clear()
            for symbol in pre:
                if symbol.startswith('@'):
                    continue
                self.shell.user_ns[symbol] = old_ns[symbol]

        # the juice is here
        # ipython processes other magics
        self.shell.run_cell(cell)

        after_ns = self.shell.user_ns.copy()

        if self.level > self.UNPROTECTED:
            badnames = [
                symbol
                for symbol in post if not (
                    symbol.startswith('@')
                    or
                    symbol in after_ns)
            ]
            # alright, due to #7256 we can't tell if run_cell failed or not
            # so on failures we get a second error due to post-conditions.
            if len(badnames) > 0:
                raise PostConditionError("The following variables are undefined: %s",
                        str(badnames))


        if self.level >= self.LOOSE:
            self.shell.user_ns.clear()
            self.shell.user_ns.update(old_ns)
            for symbol in post:
                if symbol.startswith('@'):
                    continue
                self.shell.user_ns[symbol] = after_ns[symbol]



def parse_cell(i, cell):
    for line in cell.split('\n'):
        if not line.startswith('%%isolate'):
            pass
        return Cell(i, cell, *parse(line))
    return None

def parse(line):
    clauses = re.findall('(\s*(pre|post)\(([^)]*)\))', line)
    pre = []
    post = []
    for c in clauses:
        if c[1].lower() == 'pre':
            pre.extend([a.strip() for a in c[2].split(', ')])
        elif c[1].lower() == 'post':
            post.extend([a.strip() for a in c[2].split(', ')])
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
