isolate-magic
=============

An IPython magic to isolate namespaces

The skeleton for making IPython magics is [here](http://ipython.org/ipython-doc/dev/config/custommagics.html#defining-magics)

Syntax (proposed)
----------

%%isolate-pre:  pre-conditions of the cell
%%isolate-post: post-conditions of the cell

The conditions can be variable names or special names starting with @.
  * pre-condition variables are pull from the notebook namespace before cell execution
  * post-conditoin variables are pushed to the notebook namespace after cell execution
  * special names prepresent resources that are not in the notebook namespace, for example, files on the disk
  
For example, we can have cells like these:

```
%%isolate-post @IMPORTANT_TEXT
!wget http://github.com/BIDS/isolate-magic/tree/README.md
```

```
%%isolate-pre @IMPORTANT_TEXT
import os.path
assert os.path.exists('README.md')
```


How to build a DAG from 'isolate' magics:
--------------------
 1. read in the ipynb file
 2. sort by `prompt number`
 3. post = {}
 4. transverse the cell list
   1. if cell has post-condition, add the cell to post dict
   2. if cell has pre-condition, look up the post dict, and make a directional link
      if not, give a warning or make a special mark on the cell
