# Makefile for mempalace-paper.tex
# Usage:
#   make        — build the PDF (3-pass pdflatex + bibtex)
#   make clean  — remove auxiliary files
#   make view   — open the PDF (macOS: open, Linux: xdg-open)

.PHONY: all pdf clean view

PAPER = mempalace-paper

all: pdf

pdf:
	TEXINPUTS=.:$(TEXINPUTS) pdflatex $(PAPER).tex
	TEXINPUTS=.:$(TEXINPUTS) bibtex $(PAPER)
	TEXINPUTS=.:$(TEXINPUTS) pdflatex $(PAPER).tex
	TEXINPUTS=.:$(TEXINPUTS) pdflatex $(PAPER).tex
	@echo "PDF built: $(PAPER).pdf"

clean:
	rm -f *.aux *.log *.bbl *.blg *.out *.toc *.fls *.fdb_latexmk *.synctex.gz

view: pdf
	@if command -v open > /dev/null 2>&1; then \
		open $(PAPER).pdf; \
	elif command -v xdg-open > /dev/null 2>&1; then \
		xdg-open $(PAPER).pdf; \
	else \
		echo "Cannot find PDF viewer. Open $(PAPER).pdf manually."; \
	fi
