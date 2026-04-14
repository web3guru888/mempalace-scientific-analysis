# arXiv Submission Instructions

## Paper Title
**Spatial Metaphors for LLM Memory: A Critical Analysis of the MemPalace Architecture**

## Authors
Robin Dey (VBRL Holdings, Thailand) — robin@vbrl.ai

---

## Subject Classification

### Primary
**cs.AI** — Artificial Intelligence

### Secondary
- **cs.IR** — Information Retrieval
- **cs.CL** — Computation and Language

---

## Files to Upload to arXiv

Upload **all** of the following files as a `.tar.gz` bundle:

| File | Description |
|------|-------------|
| `mempalace-paper.tex` | Main LaTeX source |
| `mempalace-paper.bib` | BibTeX bibliography |
| `jmlr2e.sty` | JMLR style file (included here for arXiv compatibility) |

> **Note**: Do not include `.pdf`, `.aux`, `.log`, `.bbl`, or `.blg` files in the
> arXiv upload. arXiv will compile the PDF itself using the `.tex` source.

---

## arXiv Submission Steps

1. Go to **https://arxiv.org/submit**
2. Click **"Start New Submission"**
3. Select **cs.AI** as primary subject class
4. Add **cs.IR** and **cs.CL** as secondary classes
5. Upload your source files as a `.tar.gz`:
   ```bash
   cd paper/
   tar -czf mempalace-arxiv-submission.tar.gz \
       mempalace-paper.tex \
       mempalace-paper.bib \
       arxiv-submission/jmlr2e.sty
   ```
   Then upload `mempalace-arxiv-submission.tar.gz`
6. Verify the preview compiles correctly
7. Fill in:
   - **Title**: `Spatial Metaphors for LLM Memory: A Critical Analysis of the MemPalace Architecture`
   - **Abstract**: *(copy from paper, see below)*
   - **Authors**: `Robin Dey`
   - **Affiliation**: `VBRL Holdings, Thailand`
   - **Comments**: `18 pages, 9 tables. Code and data at https://github.com/web3guru888/mempalace-scientific-analysis`
8. Submit

---

## Abstract (for arXiv form)

```
MemPalace is an open-source AI memory system that applies the ancient method of
loci (memory palace) spatial metaphor to organize long-term memory for large
language models. Launched in April 2026, the project accumulated over 42,000
GitHub stars and claims state-of-the-art retrieval performance on the LongMemEval
benchmark (96.6% Recall@5) without requiring any LLM inference at write time.
We present a comprehensive technical analysis of the MemPalace architecture,
examining the mapping between its cognitive-science-inspired hierarchical structure
(Wings→Rooms→Drawers) and its actual implementation in code. Through independent
codebase analysis, benchmark replication, and comparison with competing systems,
we find that MemPalace's headline retrieval performance is attributable primarily
to its verbatim storage philosophy combined with ChromaDB's default embedding
model (all-MiniLM-L6-v2), rather than to its spatial organizational metaphor per
se. The palace hierarchy operates as standard vector database metadata
filtering—an effective but well-established technique. However, we argue that
MemPalace makes several genuinely novel contributions: (1) a contrarian
verbatim-first storage philosophy that outperforms extraction-based competitors,
(2) an extremely low wake-up cost (~170 tokens) through its four-layer memory
stack, (3) a fully deterministic, zero-LLM write path enabling offline operation
at zero API cost, and (4) the first systematic application of spatial memory
metaphors as an organizing principle for AI memory systems. Our analysis concludes
that MemPalace represents significant architectural insight wrapped in overstated
claims—a pattern common in rapidly adopted open-source projects where marketing
velocity exceeds scientific rigor.
```

---

## Build Instructions (local verification)

Before uploading, verify the paper compiles locally:

```bash
cd paper/
pdflatex mempalace-paper.tex
bibtex mempalace-paper
pdflatex mempalace-paper.tex
pdflatex mempalace-paper.tex
# → mempalace-paper.pdf (18 pages)
```

Or use the Makefile:
```bash
cd paper/
make pdf
```

---

## Notes on Style File

`jmlr2e.sty` is the JMLR (Journal of Machine Learning Research) preprint style.
It is included in this `arxiv-submission/` directory to ensure arXiv can compile
the paper without package resolution issues.

The paper uses `\usepackage[preprint]{jmlr2e}` which generates the standard
arXiv preprint layout (two-sided, 11pt, with JMLR header macros).

---

## License

The paper text is licensed under **CC BY 4.0**.  
The benchmark code and experiments are licensed under **MIT**.

See `LICENSE` and `LICENSE-CODE` in the repository root.
