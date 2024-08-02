SCRIPT=git_fast_export_merge.py
PYTHON=python3
TESTS=$(SCRIPT:.py=.tests.py)
V=-v

-include Makefile.tmp

help:
	$(PYTHON) $(SCRIPT) --help

test: ; $(PYTHON) $(TESTS) $V
test_%: ; $(PYTHON) $(TESTS) --failfast --showgraph $V $@ 
