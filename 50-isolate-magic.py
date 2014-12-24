__all__ = []
from IPython.core.magic import (Magics, magics_class, line_magic,
                                        cell_magic, line_cell_magic)
import re

import networkx as nx

class PreConditionError(NameError):
    pass
class PostConditionError(NameError):
    pass

class Dag(object):
    @staticmethod
    def MultiDiGraph(history):
        mdg = nx.MultiDiGraph()
        # This is probably not the best way to handle this once we figure out
        # what we want to do
        mdg.add_node(-1, pre=[], post=[], content="",
                name="#BrokenPreConditions")

        for id, cell in enumerate(history):
            name, pre, post = parse_unit(cell)
            if name is None:
                name = str(id)
            mdg.add_node(id, pre=pre, post=post, content=cell, name=name)

        # now build the edges
        d = {}
        for node, data in mdg.nodes(data=True):
            # all post conditions are updated by this unit
            for s in data['post']:
                d[s] = node
            for s in data['pre']:
                if s in d:
                    # the direction is flowing from producer to the consumer
                    mdg.add_edge(d[s], node, symbol=s)
                else:
                    mdg.add_edge(-1, node, symbol=s)
        return mdg

    @staticmethod
    def remove_solitary_nodes(dag):
        dag = dag.copy()
        solitary= [ n for n,d in dag.degree_iter() if d==0 ]
        dag.remove_nodes_from(solitary)
        return dag

    @staticmethod
    def merge_edges(dag):
        G = nx.DiGraph()
        for node, data in dag.nodes_iter(data=True):
            G.add_node(node, **data)
        for u, v, data in dag.edges_iter(data=True):
            d = {}
            for name in data:
                d[name] = [data[name]]
            if G.has_edge(u,v):
                for name in data:
                    G[u][v][name].extend(data[name])
            else:
                G.add_edge(u, v, **d)
        return G
    @staticmethod
    def labels(dag):
        behavededgelabel = lambda x : ', '.join(x) if isinstance(x, list) else x
        edgelabels = dict(
                [((node, neighbour), behavededgelabel(data['symbol']))
                    for node, neighbour, data in dag.edges(data=True)])
        nodelabels = dict(
                [(node, '%d:%s' %(node, data['name']))
                    for node, data in dag.nodes(data=True)])
        return edgelabels, nodelabels

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
        dag = Dag.MultiDiGraph(self.shell.history_manager.input_hist_raw)
        dag = Dag.merge_edges(dag)
        dag = Dag.remove_solitary_nodes(dag)
        # This logic should probably go in the Dag class
        pos = nx.spring_layout(dag)

        edgelabels, nodelabels = Dag.labels(dag)
        return (
            nx.draw_networkx_nodes(dag, pos, nodesize=900),
            nx.draw_networkx_edges(dag, pos),
            nx.draw_networkx_labels(dag, pos, nodelabels),
            nx.draw_networkx_edge_labels(dag, pos, edgelabels),
            )
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
        name, pre, post = parse(line)

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

    @line_magic('iso_debug')
    def debug(self, _line):
        return self


def parse_unit(cell):
    for line in cell.split('\n'):
        if not line.startswith('%%isolate'):
            pass
        name, pre, post = parse(line)
        return name, pre, post
    return None

def parse(line):
    clauses = re.findall('(\s*(pre|post|name)\(([^)]*)\))', line)
    pre = []
    post = []
    name = None
    for c in clauses:
        if c[1].lower() == 'pre':
            pre.extend([a.strip() for a in c[2].split(', ')])
        elif c[1].lower() == 'post':
            post.extend([a.strip() for a in c[2].split(', ')])
        elif c[1].lower() == 'name':
            name = c[2].strip()
    return name, pre, post
# In order to actually use these magics, you must register them with a
# running IPython.  This code must be placed in a file that is loaded
# once
# IPython is up and running:
ip = get_ipython()
# You can register the class itself without instantiating it.  IPython
# will
# call the default constructor on it.
ip.register_magics(IsolateMagics)
