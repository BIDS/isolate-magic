__all__ = []
from IPython.core.magic import (Magics, magics_class, line_magic,
                                        cell_magic, line_cell_magic)
import re

import networkx as nx
import nxsvg

class PreConditionError(NameError):
    pass
class PostConditionError(NameError):
    pass

class ProtectedNamespace(dict):
    def __init__(self, detainee):
        dict.__init__(self, detainee)
        self.log = []
        self.detainee = detainee

    def enter(self):
        """ enter a senstive region of code
            read / write operations to the
            namespace will be monitored
        """
        self.log = []

    def leave(self):
        """ leave a senstive region of code
            returns the pre and post conditions of
            the code segment between enter and leave
        """
        pre  = set([])
        post = set([])
        for symbol, mode in self.log:
            if mode == 'w':
                post.add(symbol)
            elif mode == 'r':
                # only if the symbol isn't
                # created in this run.
                if symbol not in post:
                    pre.add(symbol)
        return pre, post    

    def __getitem__(self, key):
        self.log.append((key, 'r'))
        return dict.__getitem__(self, key)

    def __setitem__(self, key, value):
        self.log.append((key, 'w'))
        self.detainee.__setitem__(key, value)
        return dict.__setitem__(self, key, value)

class Dag(object):
    @staticmethod
    def MultiDiGraph(history, augmentedhistory):
        """ 
            build the initial MultiDiGraph from a notebook history. 
            the graph can be further simplified.

            A node is a workunit in the notebook; it is an execution 
            of a notebook cell. we keep track of all workunits with the
            same name; those workunits form a history sequence.

            We only process
            attributes of a node:
               prompt_number : historical prompt number
               content   : the content of the work unit 
                           (whatever typed in the cell)
               name      : name of the cell, parsed from %%isolate
               pre       : pre condition, parsed from %%isolate
               post      : post condition, parsed from %%isolate
               history   : a sequence of node ids of the historical 
                           versions of the workunits
               version   : the index of the node in the history sequence

            attributes of an edge:
               symbols
        """
        mdg = nx.MultiDiGraph()
        mdg.add_node(-1, pre=[], post=[], content="",
                name="#BrokenPreConditions", history=[], version=-1)

        workunits = {} # the history versions of cells 

        nodes = []
        print augmentedhistory
        for id, cell in enumerate(history):
            if id not in augmentedhistory: 
                continue
            name, pre, post = parse_unit(cell)
            if name is None:
                name = str(id)
            if pre is None or post is None:
                pre, post = augmentedhistory[id]
            if name not in workunits:
                workunits[name] = [id]
            else:
                workunits[name].append(id)
            history = workunits[name]
            version = len(history) - 1
            mdg.add_node(id, prompt_number=id, pre=pre, post=post, content=cell,
                    name=name, version=version, history=history)
            nodes.append(id)

        # now build the edges
        d = {}
        for id in nodes:
            data = mdg.node[id]
            # all post conditions are updated by this unit
            for s in data['post']:
                d[s] = id
            for s in data['pre']:
                if s in d:
                    # the direction is flowing from producer to the consumer
                    mdg.add_edge(d[s], id, symbol=s)
                else:
                    mdg.add_edge(-1, id, symbol=s)
        return mdg

    @staticmethod
    def remove_solitary_nodes(dag):
        """ remove workunits that are unconnected; 
            probably shall remove only those without a %%isolate magic 
        """
        dag = dag.copy()
        solitary= [ n for n,d in dag.degree_iter() if d==0 ]
        dag.remove_nodes_from(solitary)
        return dag

    @staticmethod
    def select_latest(dag):
        """ select the latest versions of workunits in any history sequence;
            all other workunits are filtered out.
        """
        dag = dag.copy()
        removal = []
        for node, data in dag.nodes_iter(data=True):
            if data['version'] != len(data['history']) - 1:
                removal.append(node)
        dag.remove_nodes_from(removal)
        return dag

    @staticmethod
    def merge_edges(dag):
        """ merge symbols on parallel dependency edges
        """
        G = nx.DiGraph()
        for node, data in dag.nodes_iter(data=True):
            G.add_node(node, **data)
        for u, v, data in dag.edges_iter(data=True):
            d = {}
            for name in data:
                d[name] = set([data[name]])
            if G.has_edge(u,v):
                for name in data:
                    G[u][v][name].update(d[name])
            else:
                G.add_edge(u, v, **d)
        return G

    @staticmethod
    def visualize(dag):
        def NodeFormatter(node, data):
             return   '%s \n%d[%s]' %(
                    data['name'],
                    data['prompt_number'],
                    ', '.join([str(d) for d in data['history']])
                        ), {}
        def EdgeFormatter(u, v, data):
            x = data['symbol']
            return ', '.join(x) if isinstance(x, set) else x, {}

        pos = nx.spring_layout(dag)
        rend = nxsvg.SVGRenderer()
        return rend.draw(dag, pos, 
                nodeformatter=NodeFormatter, 
                edgeformatter=EdgeFormatter)

@magics_class
class IsolateMagics(Magics):
    STRICT = 9     # the input is p
    LOOSE = 0

    def __init__(self, shell):
        super(IsolateMagics, self).__init__(shell)
        self.level = self.LOOSE
        self.AugmentedHistory = {}

    @line_magic('dag')
    def dag(self, line):
        """ make a dag !"""
        dag = Dag.MultiDiGraph(self.shell.history_manager.input_hist_raw, self.AugmentedHistory)
        dag = Dag.remove_solitary_nodes(dag)
        dag = Dag.merge_edges(dag)
        dag = Dag.select_latest(dag)
        def getsvg(dag):
            return Dag.visualize(dag)
        dag._repr_svg_ = getsvg.__get__(dag)
        return dag

    def setup(self):
        if not isinstance(self.shell.user_ns, ProtectedNamespace):
            self.shell.user_ns = ProtectedNamespace(self.shell.user_ns)
            print "setting up user_ns to", type(self.shell.user_ns)

    @line_magic('isolatemode')
    def isolatemode(self, line):
        """%%isolatemode [ loose | strict ]
           Two modes are supported:

           loose: the output is pruned. Any symbols undeclared with post clause
              is purged from the notebook namespace after the cell is done.
           strict: in addition to `loose';
              the input is pruned. Only symbols declared with pre are kept when
              the cell is ran.
        """
        self.setup()
        line = line.lower().split()
        if 'strict' in line:
            self.level = self.STRICT
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
        self.setup()

        name, pre, post = parse(line)

        # the juice is here
        # ipython processes other magics
        self.shell.user_ns.enter()
        self.shell.run_cell(cell)

        # not the best way to do this; ask ! 
        histid = len(self.shell.history_manager.input_hist_raw) - 1

        realpre, realpost = self.shell.user_ns.leave()
        
        if pre is not None:
            extra_pre_real = realpre.difference(pre)
            extra_pre_assumption = pre.difference(realpre)
            print extra_pre_real
            print extra_pre_assumption
            if self.level >= self.STRICT:
                if len(extra_pre_real):
                    raise PreConditionError(str(extra_pre_real))

        if post is not None:
            extra_post_real = realpost.difference(post)
            extra_post_assumption = post.difference(realpost)
            print extra_post_real
            print extra_post_assumption

            if self.level >= self.STRICT:
                if len(extra_post_real):
                    raise PreConditionError(str(extra_post_real))

        self.AugmentedHistory[histid] = (realpre, realpost)

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
    pre = None
    post = None
    name = None
    for c in clauses:
        if c[1].lower() == 'pre':
            if pre is None:
                pre = set()
            pre.update(set([a.strip() for a in c[2].split(', ')]))
        elif c[1].lower() == 'post':
            if post is None:
                post = set()
            post.update(([a.strip() for a in c[2].split(', ')]))
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
