# git fast-export merge

The `git_fast_export_merge.py` tool can read multiple archive files from 'git fast-export' 
and merge them into a single archive file for 'git fast-import' ordering the changes by date. 

Optionally, (with -m) when switching the input file some 'merge' command is generated into 
the output archive file which makes for a history as if coming from multiple branches. This
works fine if the different archives do not really represent parallel developments.

## background

The tool was written for helper code that was shared in multiple different repositories.
Each project had its own necessities to add some changes to the code which were then 
synchronized to the other projects.

Now it is possible to use `git fast-export HEAD -- libcode.py libhelper.py > libcode1.fi`.

Then merge them like `./git_Fast_export_merge.py libcode1.fi libcode2.fi -o libcode.fi`.

And the combined archive can be imported: `cd libbcode; cat ../libcode.fi | git fast-import`.

