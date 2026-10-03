# make reproduce   -> full run (all 19 datasets; see README for run times)
# make quick       -> smoke run (a few minutes)
# make setup       -> install the pinned Python packages
PYTHON ?= python

.PHONY: reproduce quick setup analysis clean serve
reproduce:
	$(PYTHON) reproduce.py
quick:
	$(PYTHON) reproduce.py --quick
setup:
	$(PYTHON) -m pip install -r requirements.txt
analysis:
	$(PYTHON) reproduce.py --analysis-only
serve:
	$(PYTHON) -m http.server 8080
clean:
	rm -rf results outputs
