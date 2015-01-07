isolate-magic
=============

An IPython magic to isolate namespaces

The docs for making IPython magics are
[here](http://ipython.org/ipython-doc/dev/config/custommagics.html#defining-magics)

For now, copy the file with the magic to the startup directory in
the desired ipython profile. If you don't have a preference, probably
`~/.ipython/profile_default/startup/` or the equivalent.

We also shall investigate the use of `pre-cell-run` and `post-cell-run` hooks.

Syntax (currently)
------------------
```
%%isolate  name(name of the cell) pre(pre-conditions of the cell) post(post-conditions of the cell)
```

The conditions can be a list of variable names, seperated by ','
  * pre-condition variables are pull from the notebook namespace before cell
    execution
  * post-conditoin variables are pushed to the notebook namespace after cell
    execution
  * if any of the conditions are omitted, isolate magic will identify them by tracking modifications to the global name space.

An active example is in:
  * http://nbviewer.ipython.org/github/BIDS/isolate-magic/blob/master/example.ipynb



How to build a Flow-Chart from 'isolate' magics
----------------------------------------
We also have experimental support for building a flow chart with the post/pre conditions decleared / infered from the notebook history. Currently, only the current session is supported.

This feature requires networkx and nxsvg (which requires svgwrite). 
```
g = %flowchart
```
If the dependency are installed properly, a svg element can be seen in the output of the cell.

The flow chart only contains those lead to the most recent versions of any named cells.
It is constructed by simplifying the original full diagram. The intermediate graphs can be inspected via `g.prev`.
