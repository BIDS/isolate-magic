def ext_main():
    from IPython.core.magic import (Magics, magics_class, line_magic,
                                            cell_magic, line_cell_magic)
    import re

    import networkx as nx

    class ProtectedNamespace(dict):
        def __init__(self, detainee, hidden):
            dict.__init__(self, detainee)
            self.log = []
            self.detainee = detainee
            self.hidden = hidden

        def enter(self, pre=None):
            """ enter a senstive region of code
                read / write operations to the
                namespace will be monitored

                if pre is True, then 
                only those in pre are preserved.
            """
            self.backup = self.copy()
            if pre is not None:
                self.clear()
                self.detainee.clear()
                for symbol in pre:
                    if symbol in self.backup:
                        self[symbol] = self.backup[symbol]
                #print 'after enter', self.keys()
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
            # pull in the old symbols
            for symbol in self.backup:
                if symbol not in self:
                    self[symbol] = self.backup[symbol]
            return self.backup, pre, post    

        def __getitem__(self, key):
            #print 'get', key, self.keys()
            val = dict.__getitem__(self, key)
            if key not in self.hidden:
                self.log.append((key, 'r'))
            return val

        def __setitem__(self, key, value):
            self.detainee.__setitem__(key, value)
            dict.__setitem__(self, key, value)
            if key not in self.hidden:
                self.log.append((key, 'w'))

    class Dag(object):
        @staticmethod
        def MultiDiGraph(history, augmentedhistory):
            """ 
                build the initial MultiDiGraph from a notebook history. 
                the graph can be further simplified.

                A node is a workunit in the notebook; it is an execution 
                of a notebook cell. we keep track of all workunits with the
                same nodename; those workunits form a history sequence.

                We only process
                attributes of a node:
                   prompt_number : historical prompt number
                   content   : the content of the work unit 
                               (whatever typed in the cell)
                   nodename      : nodename of the cell, parsed from %%isolate
                   pre       : pre condition, parsed from %%isolate
                   post      : post condition, parsed from %%isolate
                   history   : a sequence of node ids of the historical 
                               versions of the workunits
                   version   : the index of the node in the history sequence

                attributes of an edge:
                   symbols
            """
            mdg = nx.MultiDiGraph()
            mdg.add_node("BAD", pre=[], post=[], content="NULL",
                    nodename="BrokenPreConditions", history=[], prompt_number=-1, version=-1)

            workunits = {} # the history versions of cells 

            nodes = []
            for id, cell in enumerate(history):
                if id not in augmentedhistory: 
                    continue
                nodename, pre, post = parse_unit(cell)
                if nodename is None:
                    nodename = str(id)
                if pre is None or post is None:
                    name1, pre, post = augmentedhistory[id]
                
                if nodename not in workunits:
                    workunits[nodename] = [id]
                else:
                    workunits[nodename].append(id)
                history = workunits[nodename]
                version = len(history) - 1
                mdg.add_node(id, prompt_number=id, pre=pre, post=post, content=cell,
                        nodename=nodename, version=version, history=history)
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
                        mdg.add_edge("BAD", id, symbol=s)
            return mdg

        @staticmethod
        def remove_solitary_nodes(dag):
            """ remove workunits that are unconnected; 
                probably shall remove only those without a %%isolate magic 
            """
            old = dag
            dag = dag.copy()
            solitary= [ n for n,d in dag.degree_iter() if d==0 ]
            dag.remove_nodes_from(solitary)
            dag.prev = old
            return dag

        @staticmethod
        def select_latest(dag):
            """ select the latest versions of workunits in any history sequence;
                all other workunits are filtered out.
            """
            old = dag
            dag = dag.copy()
            removal = []
            for node, data in dag.nodes_iter(data=True):
                if data['version'] != len(data['history']) - 1:
                    removal.append(node)
            dag.remove_nodes_from(removal)
            dag.prev = old
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
                for nodename in data:
                    d[nodename] = set([data[nodename]])
                #d['weight'] = (len(d['symbol']) + 1)
                if G.has_edge(u,v):
                    for nodename in data:
                        G[u][v][nodename].update(d[nodename])
                else:
                    G.add_edge(u, v, **d)
            G.prev = dag
            return G

        @staticmethod
        def visualize(dag):
            import nxsvg
            def NodeFormatter(node, data):
                prop = {}
                if node != "BAD":
                    r = data['history'].index(data['prompt_number'])
                    prop['stroke'] = 'rgb(%d,0,0)' % (255 * (r + 1) // len(data['history']))
                return   '\a%s\n%d[%s]' %(
                        data['nodename'],
                        data['prompt_number'],
                        ', '.join([str(d) for d in data['history']])
                            ), prop
            def EdgeFormatter(u, v, data):
                x = data['symbol']
                prop = {}
                prop['marker_mid'] = 't'
                prop['marker_size'] = 10.0
                return ', '.join(x) if isinstance(x, set) else x, prop

            try:
                pos = nx.graphviz_layout(dag)
                raise Exception()
            except Exception as e:
                pos = nxsvg.hierarchy_layout(dag)
            rend = nxsvg.SVGRenderer(GlobalScale=len(dag) ** 0.6 * 300.)
            return rend.draw(dag, pos, 
                    size=('600px', '600px'),
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
            self.echo = False

        @staticmethod
        def getsvg(dag):
            return Dag.visualize(dag)

        @line_magic('dag')
        def dag(self, line):
            """ make a dag !"""
            dag = Dag.MultiDiGraph(self.shell.history_manager.input_hist_raw, self.AugmentedHistory)
            try:
                import nxsvg
                dag._repr_svg_ = IsolateMagics.getsvg.__get__(dag)
                dag = Dag.remove_solitary_nodes(dag)
                dag._repr_svg_ = IsolateMagics.getsvg.__get__(dag)
                dag = Dag.merge_edges(dag)
                dag._repr_svg_ = IsolateMagics.getsvg.__get__(dag)
                dag = Dag.select_latest(dag)
                dag._repr_svg_ = IsolateMagics.getsvg.__get__(dag)
            except ImportError:
                self.shell.write_err("nxsvg not found please install nxsvg for visualization")

            return dag

        def update_inputs(self, line_num):
            hm = self.shell.history_manager
            if line_num in self.AugmentedHistory:
                source_raw = hm.input_hist_raw[-1]
                newlines = []
                for line in source_raw.split('\n'):
                    if not line.startswith('%%isolate'):
                        newlines.append(line)
                    else:
                        echo = self.getecho(line_num)
                        newlines.append(echo)
                source_raw = '\n'.join(newlines)
                hm.input_hist_raw[-1] = source_raw
                source = hm.input_hist_parsed[-1]
                with hm.db_input_cache_lock:
                    for i, (ln, parsed, raw) in enumerate(hm.db_input_cache):
                        if ln == line_num:
                            hm.db_input_cache[i] = (ln, parsed, source_raw)
                            break
                    else:
                        with hm.db:
                            hm.db.execute("UPDATE history SET source=?, source_raw=? where session==? and line==?",
                                (source, source_raw, hm.session_number, line_num))

        def setup(self):
            if not isinstance(self.shell.user_ns, ProtectedNamespace):
                self.shell.user_ns = ProtectedNamespace(self.shell.user_ns, self.shell.user_ns_hidden)

                self.shell.write("setting up user_ns to %s" % str(type(self.shell.user_ns)))

        @line_magic('isolatemode')
        def isolatemode(self, line):
            """%%isolatemode [ loose | strict ] [ echo | noecho]
               Two modes are supported:

               loose: the output is pruned. Any symbols undeclared with post clause
                  is purged from the notebook namespace after the cell is done.
               strict: in addition to `loose';
                  the input is pruned. Only symbols declared with pre are kept when
                  the cell is ran.

               echo: print the desired %%isolate line of the cell is ran
            """
            self.setup()
            line = line.lower().split()
            if 'strict' in line:
                self.level = self.STRICT
            elif 'loose' in line:
                self.level = self.LOOSE
            else:
                raise ValueError("Unsupported isolatemode")
            if 'echo' in line:
                self.echo = True
            if 'noecho' in line:
                self.echo = False

        @cell_magic('isolate')
        def isolate(self, line, cell):
            """ declare symbols pre and post the cell execution

                use %%isolatemode to set the global isolation mode

                %%isolate pre(a, b, c) post(d, e, f)
                %%isolate pre(a, b, c) post(d, e, f)  pre(g, h, i)
            """
            self.setup()

            nodename, pre, post = parse(line)
            # the juice is here
            # ipython processes other magics
            if pre is not None and self.level >= self.STRICT:
                self.shell.user_ns.enter(pre)
            else:
                self.shell.user_ns.enter()

            self.shell.run_cell(cell)

            # not the best way to do this; ask ! 
            histid = len(self.shell.history_manager.input_hist_raw) - 1
            if nodename is None:
                nodename = '%d' % histid

            oldns, realpre, realpost = self.shell.user_ns.leave()
            
            if pre is not None:
                extra_pre_real = realpre.difference(pre)
                extra_pre_assumption = pre.difference(realpre)
                if self.level >= self.STRICT:
                    if len(extra_pre_real):
                        self.shell.write_err(
                                'Pre execution variables not defined in clause: %s\n' %
                                ','.join(extra_pre_real)
                                )
                    if len(extra_pre_assumption):
                        # this shall be seen after a NameError exception
                        self.shell.write_err(
                                'Pre execution variables not used in cell: %s\n' %
                                ','.join(extra_pre_assumption)
                                )

            if post is not None:
                extra_post_real = realpost.difference(post)
                extra_post_assumption = post.difference(realpost)

                if self.level >= self.LOOSE:
                    if len(extra_post_real):
                        self.shell.write_err(
                                'Post execution variables not defined in clause: %s\n' %
                                ','.join(extra_post_real)
                                )
                    if len(extra_post_assumption):
                        self.shell.write_err(
                                'Post execution variables not defined in cell: %s\n' %
                                ','.join(extra_post_assumption)
                                )
                if self.level >= self.STRICT:
                    # now lets prune the namespace and remove those extra variables
                    for symbol in extra_post_real:
                        if symbol in oldns:
                            # recover the value before the transaction
                            self.shell.user_ns[symbol] = oldns[symbol]
                        else:
                            # or remove it if it were not there
                            self.shell.user_ns.pop(symbol)
                    realpre = realpre.difference(extra_post_real)
            self.AugmentedHistory[histid] = (nodename, realpre, realpost)
            self.update_inputs(histid)
            if self.echo:
                self.shell.write(self.getecho(histid) + '\n')

        def getecho(self, histid):
            nodename, pre, post = self.AugmentedHistory[histid]
            echo = ' '.join([
                "%%isolate",
                "nodename(" + nodename + ")",
                ("pre(" + ','.join(pre) + ")") if len(pre) else '',
                ("post(" + ','.join(post) + ")") if len(post) else ''])
            return echo
        @line_magic('iso_debug')
        def debug(self, _line):
            return self

    def parse_unit(cell):
        for line in cell.split('\n'):
            if not line.startswith('%%isolate'):
                pass
            nodename, pre, post = parse(line)
            return nodename, pre, post
        return None

    def parse(line):
        clauses = re.findall('(\s*(pre|post|name)\(([^)]*)\))', line)
        pre = None
        post = None
        nodename = None
        for c in clauses:
            if c[1].lower() == 'pre':
                if pre is None:
                    pre = set()
                pre.update(set([a.strip() for a in c[2].split(',') if len(a.strip())]))
            elif c[1].lower() == 'post':
                if post is None:
                    post = set()
                post.update(set([a.strip() for a in c[2].split(',') if len(a.strip())]))
            elif c[1].lower() == 'name':
                nodename = c[2].strip()
        return nodename, pre, post

    # In order to actually use these magics, you must register them with a
    # running IPython.  This code must be placed in a file that is loaded
    # once
    # IPython is up and running:
    ip = get_ipython()
    # You can register the class itself without instantiating it.  IPython
    # will
    # call the default constructor on it.
    ip.register_magics(IsolateMagics)

ext_main()
del ext_main
