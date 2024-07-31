#! /usr/bin/python3
""":
use multiple archive files from 'git fast-export' and merge them into a single
archive file for 'git fast-import' ordering the changes by date. Optionally,
(with -m) when switching the input file some merge command is generated into 
the output archive file which makes for a history as coming from multiple branches.
- (but no actual parallel development please)."""

from typing import List, NamedTuple, Optional, Dict
from logging import getLogger, basicConfig, addLevelName, ERROR, WARNING, INFO, DEBUG
from datetime import datetime as Time
from datetime import timezone as TimeZone
from datetime import timedelta as Plus
from collections import OrderedDict
from fnmatch import fnmatchcase as fnmatch
import os.path as fs
import re
import sys

DONE = (WARNING+ERROR)//2
NOTE = (WARNING+INFO)//2
HINT = (DEBUG+INFO)//2
addLevelName(DONE, "DONE")
addLevelName(NOTE, "NOTE")
addLevelName(HINT, "HINT")
logg = getLogger("MERGE")

SUBDIR = ""
MERGES = False
COMMITTER = ""
SKIPAUTHORS = []
REPLACEAUTHORS = []

class Fromfile(NamedTuple):
    mark: str
    name: str


class Blob(NamedTuple):
    """ https://www.git-scm.com/docs/git-fast-import#_commands """
    fromfile: Fromfile
    command: str
    mark: str
    data: str

class Import(NamedTuple):
    blob: Blob
    command: str
    mark: str
    time: Time

class Commit(NamedTuple):
    blob: Blob
    merges: List[str]
    changes: List[str]
    author: str
    committer: str
    time: Time

class File(NamedTuple):
    filename: str
    fromfile: Fromfile
    filemark: str
    blob: Blob

class Update(NamedTuple):
    commit: Commit
    time: Time
    files: List[File]

class Loaded(NamedTuple):
    fromfile: Fromfile
    numblobs: int

class NewMark(NamedTuple):
    fromfile: Fromfile
    oldmark: str
    newmark: str

def time_from(author: str) -> Optional[Time]:
    m = re.match(".*@[^<>]*> *(\\d+) *([+-]\\d\\d)(\\d\\d)", author)
    if m:
        time = Time.fromtimestamp(int(m.group(1)))
        plus = Plus(hours = int(m.group(2)), minutes = int(m.group(3)))
        return time.astimezone(TimeZone(plus))
    else:
        logg.warning("unknown time desc: %s", line)
    return None

def filemarks_from(change: str) -> Dict[str, str]:
    marks = {}
    for line in change.splitlines():
        m = re.match("(\\w) (\\d+) (\\S+) (.*)", line)
        if m:
            mark = m.group(3)
            name = m.group(4)
            marks[mark] = name
        else:
            logg.warning("unknown change desc: %s", line)
    return marks

def commit_from(blob: Blob) -> Commit:
    author = ""
    committer = ""
    changes = []
    merges = []
    wait = "data"
    for line in blob.data.splitlines():
        if wait == "data":
            if line.startswith("author "):
                author = line
                continue
            if line.startswith("committer "):
                committer = line
                continue
            if line.startswith("data "):
                wait = "changes"
                continue
        if wait == "changes":
            if not line.strip():
                break
            if line.startswith("from "):
                merges += [ line ]
                continue
            if line.startswith("merge "):
                merges += [ line ]
                continue
            if line and line[1:].startswith(" 100"):
                changes += [ line ]
            elif not changes:
                logg.debug("?  %s", line)
            else:
                logg.warning("?? %s", line)
    return Commit(blob, merges, changes, author, committer, time_from(committer or author))

def run(files: List[str]) -> None:
    loaded = []
    blobs = []
    for filenum, filename in enumerate(files):
        filemark = chr(ord('A') + filenum)
        fromfile = Fromfile(filemark, filename)
        numblobs = 0
        command = ""
        text = ""
        mark = ""
        for line in open(filename):
            if line.strip().startswith("commit "):
               if text:
                   numblobs += 1
                   blobs += [ Blob(fromfile, command, mark, text) ]
               text = line
               mark = ""
               command = "commit"
            elif line.strip() == "blob":
               if text:
                   numblobs += 1
                   blobs += [ Blob(fromfile, command, mark, text) ]
               text = line
               mark = ""
               command = "blob"
            else:
               text += line
            if line.startswith("mark :"):
               mark = line[5:].strip()
        if text:
            numblobs += 1
            blobs += [ Blob(fromfile, command, mark, text) ]
        loaded += [ Loaded(fromfile, numblobs) ]
    logg.log(NOTE, "loaded %s blobs from %s files", len(blobs), len(loaded))
    for blob in blobs:
        if not blob.mark:
            logg.log(NOTE, "%s %s (%s) %s=%s", blob.command, "??", len(blob.data), 
                blob.fromfile.mark, blob.fromfile.name)
        else:
            logg.info("%s %s (%s) %s=%s", blob.command, blob.mark, len(blob.data), 
                blob.fromfile.mark, blob.fromfile.name)
        if blob.command in ["commit"]:
            commit = commit_from(blob)
            logg.info("| author %s", commit.author)
            logg.info("| committer %s", commit.committer)
            logg.info("| merges %s", commit.merges)
            logg.info("| time %s", commit.time)
            for change in commit.changes:
                logg.info("  %s", change)
    blobmap = {}
    for blob in blobs:
        frommark = blob.fromfile.mark
        blobmark = blob.mark
        blobmap[frommark+blobmark] = blob
    logg.log(NOTE, "loaded %s blobs, blobmap %s blobs", len(blobs), len(blobmap.keys()))
    numcommits = 0
    numchanges = 0
    updates = {}
    for blobref, blob in blobmap.items():
        if blob.command == "commit":
            numcommits += 1
            fileinfos = []
            commit = commit_from(blob)
            ignore = False
            for skip in SKIPAUTHORS:
                skips = skip if "*" in skip else F"*{skip}*"
                if fnmatch(commit.author, skips):
                    ignore = True
                    break
            if ignore:
               continue
            frommark = blob.fromfile.mark
            filemarks = {}
            for change in commit.changes:
                filemarks.update(filemarks_from(change))
                numchanges += 1
            for filemark in filemarks:
                filename = filemarks[filemark]
                lookup = frommark + filemark
                if lookup in blobmap:
                    blob = blobmap[lookup]
                    fileinfo = File(filename, blob.fromfile, filemark, blob)
                    fileinfos += [ fileinfo ]
                else:
                    logg.warning("could not find %s:", lookup)
            updates[blobref] = Update(commit, commit.time, fileinfos)
    logg.log(NOTE, "loaded %s blobs, %s commits + %s changes = %s", len(blobs), numcommits, numchanges, numcommits+numchanges)
    base = 1000
    if len(blobs) >= 1000:
       base = 10000
    if len(blobs) >= 10000:
       base = 100000
    imports = []
    newmarks = OrderedDict()
    for ref in sorted(updates, key=lambda x: updates[x].time):
        update = updates[ref]
        logg.info("commit %s @ %s", ref, update.time)
        for fileinfo in update.files:
            blob = fileinfo.blob
            frok = blob.fromfile.mark
            mark = blob.mark
            filename = fileinfo.filename
            num = base + len(newmarks)
            newnum = ":%i" % num
            newmarks[frok+mark] = NewMark(blob.fromfile, blob.mark, newnum)
            logg.info("  file %s%s %s %s", frok, mark, newnum, filename)
            imp = Import(blob, blob.command, newnum, update.time)
            imports += [ imp ]
        num = base + len(newmarks)
        newnum = ":%i" % num
        blob = update.commit.blob
        mark = blob.mark
        frok = blob.fromfile.mark
        newmarks[frok+mark] = NewMark(blob.fromfile, blob.mark, newnum)
        logg.info("    up %s %s <- %s", ref, newnum, blob.mark)
        imp = Import(blob, blob.command, newnum, update.time)
        imports += [ imp ]
    logg.log(NOTE, "loaded %s blobs, generated %s blobs", len(blobs), len(imports))
    for ref, newnum in newmarks.items():
        logg.log(HINT, "     %s -> %s", ref, newnum)
    if OUTPUT:
        out = open(OUTPUT, "w")
    else:
        out = sys.stdout
    oldmark = ""
    for imp in imports:
        blob = imp.blob
        frok = blob.fromfile.mark
        if blob.command == "commit":
            newdata = update_commit(blob.data, frok, newmarks, oldmark)
            oldmark = imp.mark
        elif blob.command == "blob":
            newdata = update_blob(blob.data, frok, newmarks)
        else:
            newdata = ""
            logg.error("unknown command %s", blob.command)
        print(newdata, file=out)


class Comment(NamedTuple):
    author: str
    timespec: str
    comment: str

HISTORY = []

def update_commit(data: str, frok: str, marks: Dict[str, NewMark], newfrom: str = ""):
    global HISTORY
    lines = []
    wait = "data"
    donemark = False
    oldfrom = ""
    wastimespec = ""
    wasauthor = ""
    wascomment = ""
    skipover = 0
    for line in data.splitlines():
        if wait == "data":
            if line.startswith("commit refs/heads/"):
                lines += [F"commit refs/heads/{BRANCH}"]
                continue
            if line.startswith("data "):
                skipover = int(line[len("data "):])
                wait = "end"
                lines += [ line ]
                continue
            if line.startswith("from :"):
                oldfrom = line[len("from "):].strip()
                if newfrom:
                   lines += ["from "+newfrom]
                   donemark = True
                   oldref = frok+oldfrom
                   if oldref in marks:
                       newmark = marks[oldref].newmark
                       if newmark != newfrom and MERGES:
                           lines += ["merge "+newmark]
                continue
            if line.startswith("merge :"):
                continue
            if line.startswith("committer "):
                if COMMITTER and ">" in line:
                    timespec = line.split(">",1)[1]
                    newline = "committer "+COMMITTER+timespec
                    wastimespec = timespec
                else:
                    newline = line
                lines += [newline]
                continue
            if line.startswith("author "):
                if ">" in line:
                    newline = line
                    author0, timespec = line[len("author "):].split(">",1)
                    author = (author0 + ">").strip()
                    wasauthor = author
                    for replace in REPLACEAUTHORS:
                        if "=" in replace:
                           old, new = replace.split("=", 1)
                           if fnmatch(author, old):
                               newline = "author "+new+timespec
                else:
                    newline = line
                lines += [newline]
                continue
            if line.startswith("mark :"):
                oldmark = line[5:].strip()
                oldref = frok+oldmark
                if oldref in marks:
                   newmark = marks[oldref].newmark
                else:
                    logg.error("did not find oldmark %s", oldref)
                    newmark = oldmark
                lines += ["mark "+newmark]
            else:
                lines += [ line ]
        elif wait == "end":
            if skipover:
               wascomment = line
               skipover = 0
            if line.startswith("from :"):
                oldfrom = line[len("from "):].strip()
                if newfrom:
                   lines += ["from "+newfrom]
                   donemark = True
                   oldref = frok+oldfrom
                   if oldref in marks:
                       newmark = marks[oldref].newmark
                       if newmark != newfrom and MERGES:
                           lines += ["merge "+newmark]
                continue
            if line.startswith("merge :"):
                continue
            if line and line[1:].startswith(" 100"):
                if newfrom and not donemark:
                   lines += ["from "+newfrom]
                   donemark = True
                m = re.match("(\\S) (\\d+) (\\S+) (.*)", line)
                if m:
                    oldmark = m.group(3)
                    oldref = frok+oldmark
                    if oldref in marks:
                        newmark = marks[oldref].newmark
                    else:
                        logg.error("did not find oldmark %s", oldref)
                        newmark = oldmark
                    filename = m.group(4)
                    if SUBDIR:
                        filename = SUBDIR + "/" + filename
                    newline = "%s %s %s %s" % (m.group(1), m.group(2), newmark, filename)
                else:
                    logg.error("unknown change: %s", line)
                    newline = line
                lines += [newline]
            else:
                lines += [line]
        else:
            lines += [line]
    HISTORY += [Comment(wasauthor, wastimespec, wascomment)]
    return "\n".join(lines)

def update_blob(data: str, frok: str, marks: Dict[str, NewMark]):
    lines = []
    wait = "data"
    for line in data.splitlines():
        if wait == "data":
            if line.startswith("data "):
                wait = "end"
                lines += [line]
                continue
            if line.startswith("mark :"):
                oldmark = line[5:].strip()
                oldref = frok+oldmark
                if oldref in marks:
                    newmark = marks[oldref].newmark
                else:
                    logg.error("did not find oldmark %s", oldref)
                    newmark = oldmark
                lines += ["mark "+newmark]
            else:
                lines += [line]
        else:
            lines += [line]
    return "\n".join(lines)

def gitconfig_user() -> str:
    config = ConfigParser()
    config.read(fs.expanduser("~/.gitconfig"))
    uname = config.get("user", "name", fallback="")
    email = config.get("user", "email", fallback="")
    if uname and email:
        return "%s <%s>" % (uname, email)
    return ""

if __name__ == "__main__":
    from configparser import ConfigParser
    from optparse import OptionParser
    cmdline = OptionParser("%prog [files.fi ..]", description=__doc__)
    cmdline.formatter.max_help_position = 33
    cmdline.add_option("-v", "--verbose", action="count", default=0,
                       help="increase logging level")
    cmdline.add_option("-H", "--history", action="store_true", default=False,
                       help="log the generated history (for checking)")
    cmdline.add_option("-F", "--historyfile", metavar="F", default="",
                       help="put the generated history into a file")
    cmdline.add_option("-S", "--subdir", metavar="N", default="",
                       help="rename files to be in subdir")
    cmdline.add_option("-c", "--committer", metavar="mail", default="",
                       help="defaults to author from ~/.gitconfig")
    cmdline.add_option("-s", "--skip", metavar="author*", action="append", default=[],
                       help="skip commits matching some author")
    cmdline.add_option("-r", "--replace", metavar="old=new", action="append", default=[],
                       help="replace author matched by left part")
    cmdline.add_option("-m", "--merges", action = "store_true", default=False,
                       help="generate merges for different inputs")
    cmdline.add_option("-b", "--branch", metavar="file", default="main",
                       help="generate import to this branch (main)")
    cmdline.add_option("-o", "--output", metavar="file", default="",
                       help="generate into file instead of stdout")
    opt, args = cmdline.parse_args()
    basicConfig(level = ERROR - 5 * opt.verbose)
    SUBDIR = opt.subdir
    MERGES = opt.merges
    BRANCH = opt.branch
    OUTPUT = opt.output
    REPLACEAUTHORS = opt.replace
    SKIPAUTHORS = opt.skip
    COMMITTER = opt.committer
    if not COMMITTER:
       COMMITTER = gitconfig_user()
    run(args)
    if opt.history:
        if opt.historyfile:
            with open(opt.historyfile, "w") as hfile:
                for hist in reversed(HISTORY):
                    print(hist.author, hist.timespec, ":", hist.comment, file=hfile)
        else:
            for hist in reversed(HISTORY):
                logg.log(DONE, " %s %s: %s", hist.author, hist.timespec, hist.comment)
        