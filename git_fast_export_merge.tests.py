#! /usr/bin/env python3

__copyright__ = "(C) 2017-2024 Guido Draheim, licensed under the Apache License 2.0"""
__version__ = "1.6.3321"

from typing import Optional, Any, List, Union, Iterator, NamedTuple

from subprocess import check_output, Popen, PIPE, CalledProcessError
from unittest import TestCase, TestSuite, TextTestRunner
import os.path as fs
import shutil
import os, sys, re
import inspect
from time import sleep
from fnmatch import fnmatchcase as fnmatch
from logging import getLogger, basicConfig, WARNING, INFO, addLevelName

NOTE = (WARNING+INFO)//2
EXEC = INFO+1
addLevelName(NOTE, "NOTE")
addLevelName(EXEC, "EXEC")

logg = getLogger("TEST")
KEEP = 0
NIX = ""
GIT = "git"
RUN = "--no-pager"
PYTHON = "python3"
MERGE = "git_fast_export_merge.py"

def sx__(cmd: str, cwd: Optional[str] = None, shell: bool = True, env={"LANG":"C"}, **args: Any) -> str:
    try:
        return sh__(cmd, cwd=cwd, shell=shell, env=env, **args)
    except Exception as e:
        logg.debug("sh failed: %s", cmd)
        return ""
def sh__(cmd: str, cwd: Optional[str] = None, shell: bool = True, env={"LANG":"C"}, **args: Any) -> str:
    logg.debug("sh %s", cmd)
    return check_output(cmd, cwd=cwd, shell=shell, env=env, **args).decode("utf-8")
class Run(NamedTuple):
    out: str
    err: str
    code: int
def sh(cmd: Union[str, List[str]], cwd: Optional[str] = None, shell: Optional[bool] = None, 
       input: Optional[str] = None, env={"LANG":"C"}) -> Run:
    std = run(cmd, cwd, shell, input, env)
    if std.code:
        raise CalledProcessError(std.code, cmd, std.out, std.err)
    return std
def run(cmd: Union[str, List[str]], cwd: Optional[str] = None, shell: Optional[bool] = None, 
       input: Optional[str] = None, env={"LANG":"C"}) -> Run:
    if isinstance(cmd, str):
        logg.log(EXEC, ": %s", cmd)
        shell = True if shell is None else shell
    else:
        logg.log(EXEC, ": %s", " ".join(["'%s'" % item for item in cmd]))
        shell = False if shell is None else shell
    if input is not None:
        run = Popen(cmd, cwd=cwd, shell=shell, stdout=PIPE, stderr=PIPE, stdin=PIPE, env=env)
        out, err = run.communicate(input.encode("utf-8"))
    else:
        run = Popen(cmd, cwd=cwd, shell=shell, stdout=PIPE, stderr=PIPE, env=env)
        out, err = run.communicate()
    text_out = decodes(out)
    text_err = decodes(err)
    logg.debug("stdout = %s", text_out.splitlines())
    if text_err:
        logg.debug("stderr = %s", text_err.splitlines())
    if run.returncode:
        logg.debug("return = %s", run.returncode)
    return Run(text_out, text_err, run.returncode)
def decodes(text: Union[bytes, str]) -> str:
    if text is None: return None
    if isinstance(text, bytes):
        encoded = sys.getdefaultencoding()
        if encoded in ["ascii"]:
            encoded = "utf-8"
        try:
            return text.decode(encoded)
        except:
            return text.decode("latin-1")
    return text


def _lines(lines: Union[str, List[str]]) -> List[str]:
    if isinstance(lines, str):
        xlines = lines.split("\n")
        if len(xlines) and xlines[-1] == "":
            xlines = xlines[:-1]
        return xlines
    return lines
def lines(text: Union[str, List[str]]) -> List[str]:
    lines = []
    for line in _lines(text):
        lines.append(line.rstrip())
    return lines
def grep(pattern: str, lines: Union[str, List[str]]) -> Iterator[str]:
    for line in _lines(lines):
        if re.search(pattern, line.rstrip()):
            yield line.rstrip()
def greps(lines: Union[str, List[str]], pattern: str) -> List[str]:
    return list(grep(pattern, lines))
def greplines(lines: Union[str, List[str]], *pattern: str) -> List[str]:
    eachline = [line.rstrip() for line in _lines(lines) if line.rstrip()]
    if not pattern:
        logg.info("[*]=> %s", eachline)
        return eachline
    found = []
    done = len(pattern)
    look = 0
    if done == 1 and pattern[0] == "" and not eachline:
        return ["EMPTY"]
    for line in eachline:
        if not pattern[look]:
            if not line.strip():
                found.append(line)
                look += 1
                if look == done:
                    return found
        else:
            if re.search(pattern[look], line.rstrip()):
                found.append(line)
                look +=1
                if look == done:
                    return found
    logg.debug("[?]<< %s", pattern)
    logg.debug("[?]=> %s", eachline)
    return []

def get_caller_name() -> str:
    frame = inspect.currentframe().f_back.f_back  # type: ignore
    return frame.f_code.co_name  # type: ignore
def get_caller_caller_name() -> str:
    frame = inspect.currentframe().f_back.f_back.f_back  # type: ignore
    return frame.f_code.co_name  # type: ignore

class GitExportMergeTest(TestCase):
    def caller_testname(self) -> str:
        name = get_caller_caller_name()
        x1 = name.find("_")
        if x1 < 0: return name
        x2 = name.find("_", x1 + 1)
        if x2 < 0: return name
        return name[:x2]
    def testname(self, suffix: Optional[str] = None) -> str:
        name = self.caller_testname()
        if suffix:
            return name + "_" + suffix
        return name
    def testdir(self, testname: Optional[str] = None, keep: bool = False) -> str:
        testname = testname or self.caller_testname()
        newdir = "tmp/tmp." + testname
        if fs.isdir(newdir) and not keep:
            shutil.rmtree(newdir)
        if not fs.isdir(newdir):
            os.makedirs(newdir)
        return newdir
    def rm_testdir(self, testname: Optional[str] = None) -> str:
        testname = testname or self.caller_testname()
        newdir = "tmp/tmp." + testname
        if fs.isdir(newdir):
            if not KEEP:
                shutil.rmtree(newdir)
        return newdir
    def test_100(self) -> None:
        tmp = self.testdir()
        A = fs.join(tmp, "A")
        std = sh(F"{GIT} {RUN} init -b main A", cwd=tmp)
        self.assertTrue(greplines(std.out,"Initialized empty Git repository"))
        std = sh(F"echo 'hello' > world.txt", cwd=A)
        self.assertTrue(greplines(std.out, ""))
        std = sh(F"{GIT} {RUN} add world.txt", cwd=A)
        self.assertTrue(greplines(std.out, ""))
        std = sh(F"{GIT} {RUN} commit -m hello-A world.txt", cwd=A)
        self.assertTrue(greplines(std.out, "main .* hello-A"))
        std = sh(F"{GIT} {RUN} log", cwd=A)
        self.assertTrue(greplines(std.out, "commit ", " hello-A"))
        #
        sleep(2)
        #
        B = fs.join(tmp, "B")
        std = sh(F"{GIT} {RUN} init -b main B", cwd=tmp)
        self.assertTrue(greplines(std.out,"Initialized empty Git repository"))
        std = sh(F"echo 'hello' > world.txt", cwd=B)
        self.assertTrue(greplines(std.out, ""))
        std = sh(F"{GIT} {RUN} add world.txt", cwd=B)
        self.assertTrue(greplines(std.out, ""))
        std = sh(F"{GIT} {RUN} commit -m hello-B world.txt", cwd=B)
        self.assertTrue(greplines(std.out, "main .* hello-B"))
        std = sh(F"{GIT} {RUN} log", cwd=B)
        self.assertTrue(greplines(std.out, "commit ", " hello-B"))
        #
        std = sh(F"{GIT} {RUN} fast-export HEAD > ../A.fi", cwd=A)
        self.assertTrue(greplines(std.out, ""))
        catA = sh(F"cat A.fi", cwd=tmp)
        self.assertTrue(greplines(catA.out, "hello-A"))
        std = sh(F"{GIT} {RUN} fast-export HEAD > ../B.fi", cwd=B)
        self.assertTrue(greplines(std.out, ""))
        catB = sh(F"cat B.fi", cwd=tmp)
        self.assertTrue(greplines(catB.out, "hello-B"))
        self.assertNotEqual(greplines(catA.out, "committer .*"), greplines(catB.out, "committer .*"))
        #
        N = fs.join(tmp, "N")
        merge = fs.abspath(MERGE)
        std = sh(F"{GIT} {RUN} init -b main N", cwd=tmp)
        self.assertTrue(greplines(std.out, "Initialized empty"))
        std = sh(F"{PYTHON} {merge} A.fi B.fi -o N.fi", cwd=tmp)
        self.assertTrue(greplines(std.out, ""))
        catN = sh(F"cat N.fi", cwd=tmp)
        self.assertTrue(greplines(catN.out, "hello-A", "hello-B"))
        std = sh(F"{GIT} {RUN} fast-import < ../N.fi", cwd=N)
        self.assertTrue(greplines(std.out, ""))
        std = sh(F"{GIT} {RUN} log", cwd=N)
        self.assertTrue(greplines(std.out, "hello-B", "hello-A"))
        self.assertFalse(greplines(std.out, "license"))
        self.rm_testdir()
    def test_110(self) -> None:
        tmp = self.testdir()
        A = fs.join(tmp, "A")
        std = sh(F"{GIT} {RUN} init -b main A", cwd=tmp)
        self.assertTrue(greplines(std.out,"Initialized empty Git repository"))
        std = sh(F"echo 'hello' > world.txt", cwd=A)
        self.assertTrue(greplines(std.out, ""))
        std = sh(F"{GIT} {RUN} add world.txt", cwd=A)
        self.assertTrue(greplines(std.out, ""))
        std = sh(F"{GIT} {RUN} commit -m hello-A world.txt", cwd=A)
        self.assertTrue(greplines(std.out, "main .* hello-A"))
        std = sh(F"{GIT} {RUN} log", cwd=A)
        self.assertTrue(greplines(std.out, "commit ", " hello-A"))
        #
        sleep(2)
        #
        B = fs.join(tmp, "B")
        std = sh(F"{GIT} {RUN} init -b main B", cwd=tmp)
        self.assertTrue(greplines(std.out,"Initialized empty Git repository"))
        std = sh(F"echo 'hello' > world.txt", cwd=B)
        self.assertTrue(greplines(std.out, ""))
        std = sh(F"{GIT} {RUN} add world.txt", cwd=B)
        self.assertTrue(greplines(std.out, ""))
        std = sh(F"{GIT} {RUN} commit -m hello-B world.txt", cwd=B)
        self.assertTrue(greplines(std.out, "main .* hello-B"))
        std = sh(F"{GIT} {RUN} log", cwd=B)
        self.assertTrue(greplines(std.out, "commit ", " hello-B"))
        #
        std = sh(F"{GIT} {RUN} fast-export HEAD > ../A.fi", cwd=A)
        self.assertTrue(greplines(std.out, ""))
        catA = sh(F"cat A.fi", cwd=tmp)
        self.assertTrue(greplines(catA.out, "hello-A"))
        std = sh(F"{GIT} {RUN} fast-export HEAD > ../B.fi", cwd=B)
        self.assertTrue(greplines(std.out, ""))
        catB = sh(F"cat B.fi", cwd=tmp)
        self.assertTrue(greplines(catB.out, "hello-B"))
        #
        merge = fs.abspath(MERGE)
        N = fs.join(tmp, "N")
        std = sh(F"{GIT} {RUN} init -b main N", cwd=tmp)
        self.assertTrue(greplines(std.out, "Initialized empty"))
        std = sh(F"echo OK > LICENSE", cwd=N)
        self.assertTrue(greplines(std.out, ""))
        std = sh(F"{GIT} {RUN} add LICENSE", cwd=N)
        self.assertTrue(greplines(std.out, ""))
        std = sh(F"{GIT} {RUN} commit -m license LICENSE", cwd=N)
        self.assertTrue(greplines(std.out, "main .* license"))
        std = sh(F"{GIT} {RUN} rev-parse HEAD", cwd=N)
        self.assertTrue(greplines(std.out,"..........."))
        head = std.out.strip()
        std = sh(F"{PYTHON} {merge} A.fi B.fi -o N.fi -H {head} -L", cwd=tmp)
        self.assertTrue(greplines(std.out, ""))
        self.assertTrue(greplines(std.err, ""))
        catN = sh(F"cat N.fi", cwd=tmp)
        self.assertTrue(greplines(catN.out, "hello-A", "hello-B"))
        std = sh(F"{GIT} {RUN} fast-import < ../N.fi", cwd=N)
        self.assertTrue(greplines(std.out, ""))
        self.assertTrue(greplines(std.err, "commits: *2"))
        std = sh(F"{GIT} {RUN} log", cwd=N)
        self.assertTrue(greplines(std.out, "hello-B", "hello-A", "license"))
        self.rm_testdir()

if __name__ == "__main__":
    # unittest.main()
    from optparse import OptionParser
    cmdline = OptionParser("%s test...")
    cmdline.add_option("-v", "--verbose", action="count", default=0, help="more verbose logging")
    cmdline.add_option("-^", "--quiet", action="count", default=0, help="less verbose logging")
    cmdline.add_option("-k", "--keep", action="count", default=0, help="keep testdir")
    cmdline.add_option("--failfast", action="store_true", default=False,
                       help="Stop the test run on the first error or failure. [%default]")
    cmdline.add_option("--xmlresults", metavar="FILE", default=None,
                       help="capture results as a junit xml file [%default]")
    opt, args = cmdline.parse_args()
    basicConfig(level=max(0,WARNING - 10 * opt.verbose + 10 * opt.quiet))
    KEEP = opt.keep
    if not args:
        args = ["test_*"]
    suite = TestSuite()
    for arg in args:
        if len(arg) > 2 and arg[0].isalpha() and arg[1] == "_":
            arg = "test_" + arg[2:]
        for classname in sorted(globals()):
            if not classname.endswith("Test"):
                continue
            testclass = globals()[classname]
            for method in sorted(dir(testclass)):
                if "*" not in arg: arg += "*"
                if arg.startswith("_"): arg = arg[1:]
                if fnmatch(method, arg):
                    suite.addTest(testclass(method))
    # running
    xmlresults = None
    if opt.xmlresults:
        if os.path.exists(opt.xmlresults):
            os.remove(opt.xmlresults)
        xmlresults = open(opt.xmlresults, "wb")
    if xmlresults:
        import xmlrunner  # type: ignore[import]
        Runner = xmlrunner.XMLTestRunner
        result = Runner(xmlresults).run(suite)
        logg.info(" XML reports written to %s", opt.xmlresults)
    else:
        Runner = TextTestRunner
        result = Runner(verbosity=opt.verbose, failfast=opt.failfast).run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
