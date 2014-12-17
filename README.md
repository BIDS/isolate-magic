isolate-magic
=============

An IPython magic to isolate namespaces

The skeleton for making IPython magics is [here](http://ipython.org/ipython-doc/dev/config/custommagics.html#defining-magics)

Syntax (currently)
----------
```
%%isolate  pre(pre-conditions of the cell) post(post-conditions of the cell)
```

The conditions can be variable names or special names starting with @.
  * pre-condition variables are pull from the notebook namespace before cell execution
  * post-conditoin variables are pushed to the notebook namespace after cell execution
  * special names prepresent resources that are not in the notebook namespace, for example, files on the disk
  
An active example is in:
  * http://nbviewer.ipython.org/github/BIDS/isolate-magic/blob/master/example.ipynb

For example, we can have cells like these:

```
%%isolate post(@IMPORTANT_TEXT)
!wget http://github.com/BIDS/isolate-magic/tree/README.md
```

```
%%isolate pre(@IMPORTANT_TEXT) post(os)
# notice that we do not support attribute look up in post
# hence our post-condition is only 'os'
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
   2. if cell has pre-condition, look up the post dict, and make a 'proper' link
      if not, issue a warning, push the cell to a list of defered cells
 5. Loop over the defered cells
   1. if cell has pre-condition, look up the post dict, and make a 'improper' link
      if not, issue a warning in some way (marking the cell as dead/incomplete)

 * 'proper': the tail cell's last execution is up-to-date
 * 'improper': the tail cell's last execution is older than its input; it at least needs updated.
