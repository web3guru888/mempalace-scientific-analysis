RASTI 000, 000–000 (2026)
Preprint 8 April 2026
Compiled using rasti LATEX style file v3.0
ASTRA: Autonomous Scientific Discovery in Astrophysics
Glenn J. White1,2★
1Department of Physics and Astronomy, The Open University, Milton Keynes MK7 6AA, UK
2RAL Space, STFC Rutherford Appleton Laboratory, Chilton, Didcot, Oxfordshire OX11 0QX, UK
Accepted XXX. Received YYY; in original form ZZZ
ABSTRACT
We present Astra (Autonomous System for Scientific Discovery in Astrophysics), an integrated framework that unifies numerical
data analysis, causal reasoning, and physical validation within a single reproducible pipeline. Astra chains dimensional analysis
via the Buckingham 𝜋theorem, structural causal models, Bayesian evidence computation, and multi-wavelength data fusion
into coherent, physics-aware workflows. A cognitive architecture incorporating a dynamic knowledge graph, neuro-symbolic
reasoning, and meta-cognitive monitoring coordinates the analytical loop, while a multi-agent scientific debate system evaluates
competing hypotheses through structured argumentation and consensus mechanisms. A stigmergic swarm intelligence layer—
inspired by ant colony foraging—coordinates hypothesis exploration through five specialized agents that deposit and follow
digital pheromone trails. We validate the framework through six controlled astrophysical test cases, six live deployments
recovering established physics (including Kepler’s third law at 𝑅2 = 0.9982), and cross-domain validation across economics,
climate science, and epidemiology, collectively validating 38 hypotheses across five scientific domains. Astra is a tool to assist
scientists, not replace domain expertise. Code and documentation: https://github.com/Tilanthi/ASTRA.
Key words: methods: data analysis – methods: statistical – methods: general – techniques: miscellaneous – ISM: clouds – stars:
formation
1 INTRODUCTION
Modern
astronomical
surveys
generate
petabytes
of
multi-
wavelength data per year, and a rich ecosystem of computational
tools—from classifiers to nested-sampling codes, from causal dis-
covery algorithms (Spirtes et al. 2000) to frontier large language
models—gives astronomers unprecedented analytical power. Yet
these tools operate largely in isolation: astronomers must manu-
ally stitch together separate pipelines for data processing, statistical
modelling, causal inference, and physical validation, creating oppor-
tunities for inconsistent treatment of uncertainties, missed physical
constraints, and analyses that are difficult to reproduce.
Astra (Autonomous System for Scientific Discovery in Astro-
physics) addresses this integration challenge. Rather than replacing
any single tool, Astra provides a unified framework that chains
established algorithms into coherent, physics-aware analytical work-
flows. The system combines:
• Numerical data processing and statistical analysis
• Causal reasoning with structural causal models
• Physical validation through dimensional analysis and conserva-
tion laws
• Multi-wavelength data fusion with uncertainty propagation
• Hypothesis generation from pattern recognition
• Bayesian model selection with evidence computation
• Stigmergic swarm intelligence for autonomous exploration–
exploitation balancing
★E-mail: glenn.white@open.ac.uk
• Cognitive architecture with dynamic knowledge graph and
neuro-symbolic reasoning
• Multi-agent scientific debate for hypothesis evaluation and con-
sensus
• Theory framework with automated consistency checking and
abductive reasoning
This integrated approach ensures that physical validation, causal
reasoning, and uncertainty quantification are applied consistently
throughout multi-step analyses. While individual components use
established algorithms (PC algorithm for causal discovery, nested
sampling for Bayesian evidence, the Buckingham 𝜋theorem for
dimensional analysis; Buckingham 1914), their integration within
a single framework enables analyses that would otherwise require
manual combination of multiple separate tools.
In this paper, we focus on six examples demonstrating how this
integrated approach can be applied to astrophysical inference prob-
lems:
(i) Scaling Relations Analysis (Section 3): Dimensional analysis
and physical validation of filament scaling relations
(ii) Multi-Wavelength Data Fusion (Section 4): Probabilistic
cross-matching with Bayesian uncertainty propagation
(iii) Pattern Recognition (Section 5): Identification of estab-
lished galaxy property relationships
(iv) Causal Inference (Section 6): Structural causal model dis-
covery in stellar data
(v) Bayesian Model Selection (Section 7): Evidence-based
model comparison with prior specification
(vi) Discovery-Mode Operation on Synthetic Data (Section 8):
© 2026 The Authors
2
White
Knowledge-isolated pattern discovery and causal inference on the
star formation threshold problem
The first five test cases use real observational data to validate
Astra’s ability to correctly recover known astrophysical results.
The sixth test case demonstrates discovery-mode operation beyond
knowledge retrieval, under controlled conditions. Using synthetic
data with embedded causal structure (ground truth known to the au-
thor but not to Astra), it operates in “knowledge isolation mode” to
discover patterns without being told what to look for, and generates
testable predictions for future validation.
Section 9 presents six live deployments on archival data that in-
dependently recover established physics. To test whether Astra’s
analytical capabilities generalize beyond astrophysics, Section 10
presents cross-domain validation across economics, climate science,
and epidemiology using public data from the World Bank, NASA
GISS, and NOAA. Section 11 discusses why these results demon-
strate Astra’s unique capabilities and clarifies Astra’s role as a tool
to assist rather than replace scientists, and Section 12 concludes.
2 METHODS: ASTRA SYSTEM ARCHITECTURE
2.1 Overview
Astra implements a modular architecture designed for astrophysical
data analysis and inference. The system integrates multiple special-
ized components through a coordinated framework, enabling com-
plex multi-step analyses that combine data processing, physical rea-
soning, causal inference, and statistical validation.
2.1.1 Scope and Limitations
What Astra Demonstrates: The six astrophysical test cases show
that Astra can: discover physical laws from data with theoretical val-
idation; fuse multi-wavelength observations with proper uncertainty
handling; identify established astrophysical relationships through
pattern recognition; distinguish causation from correlation; perform
rigorous Bayesian model comparison; and operate in knowledge iso-
lation mode to discover patterns and generate testable predictions be-
yond knowledge retrieval. The cross-domain validation (Section 10)
further demonstrates that these capabilities generalize to economics,
climate science, and epidemiology, recovering approximately 42 val-
idated hypotheses across five scientific domains.
What Astra Does Not Claim: Astra is not presented as achiev-
ing artificial general intelligence or AGI-like performance. The sys-
tem operates within defined astrophysical domains using established
algorithms (PC algorithm, Bayesian inference, dimensional analysis
via the Buckingham 𝜋theorem, FCI causal discovery; Zhang 2008)
combined through an integrated architecture. Results are validated
against known physical theory and observational constraints. The
system does not claim general reasoning beyond its training domains
or autonomous operation without human oversight; the live dash-
board (Section 2.6) provides real-time safety monitoring and inter-
vention controls. The architecture supports natural language queries
that trigger autonomous task completion, though this capability is not
demonstrated in the present test cases. A stigmergic swarm intelli-
gence layer (Section 2.7) coordinates autonomous exploration, while
the live dashboard (Section 2.6) provides real-time monitoring and
intervention controls. The cognitive architecture (Section 2.8) and
multi-agent debate system (Section 2.9) are early-stage components
whose integration is described but not independently validated in the
present test cases.
Astra’s Role: Astra is a tool to assist the astronomer, not a
replacement for domain expertise. Its discovery architecture, used
alongside an experienced scientist, provides capabilities in discovery
and inference that go beyond those of straightforward AI or machine
learning alone, as discussed in Section 11.6.
Validation Scope: The first five test cases use real observational
data to validate Astra’s ability to correctly recover known astrophys-
ical results. The sixth test case demonstrates discovery capability on
synthetic data with known ground truth, with testable predictions
that require future observational validation. The cross-domain vali-
dation (Section 10) extends the scope to five scientific domains using
exclusively public data from established archives. Generalization to
additional domains or datasets requires further validation.
2.2 Core Architectural Components
(i) Data Processing Pipeline: Astra accepts heterogeneous as-
tronomical data formats including catalogues (CSV, FITS), time-
series data, images, and spectral data. The pipeline performs in-
gestion, validation, cleaning, and normalization while preserving
measurement uncertainties and metadata.
(ii) Physics Engine: A unified physics engine implements fun-
damental physical laws and constraints including conservation laws
(mass, energy, momentum), dimensional analysis using the Bucking-
ham 𝜋theorem (Buckingham 1914), equation solving and numerical
simulation, and units consistency checking throughout calculations.
This enables Astra to validate discoveries against first principles
rather than treating correlations as sufficient explanations.
(iii) Causal Reasoning Module: The causal reasoning module
discovers and analyses causal structures using the PC algorithm
(Spirtes et al. 2000) for learning directed acyclic graphs from obser-
vational data, the FCI algorithm (Zhang 2008) for causal discovery in
the presence of latent confounders, conditional independence testing
for continuous variables (Fisher’s 𝑍-test), V-structure detection for
identifying colliders, do-calculus (Pearl 2009) for predicting effects
of interventions, and domain-specific adaptations for astrophysical
contexts. This module enables Astra to distinguish causal relation-
ships from correlations, addressing a fundamental limitation of both
traditional ML and LLM approaches.
(iv) Bayesian Inference Engine: Rigorous model comparison
and uncertainty quantification are performed through evidence com-
putation via marginal likelihood estimation, learned harmonic mean
estimation (Spurio Mancini et al. 2023), Bayes factors and PSIS-
LOO-CV for model comparison (Eadie et al. 2023), automatic com-
plexity penalty (Occam’s razor), posterior predictive checking, and
Monte Carlo methods for uncertainty propagation. Model complexity
is assessed using the Bayesian Information Criterion (BIC; Schwarz
1978) as a rapid approximation where full evidence computation is
unnecessary.
(v) Domain
Knowledge
Systems:
Organized
astrophysical
knowledge through MORK ontology encoding taxonomic and causal
relationships, knowledge graphs for semantic relationships, vector-
based semantic memory for concept retrieval, and 75 specialized
domain modules (ISM, star formation, exoplanets, etc.).
(vi) Multi-Module Orchestration: Coordinates different analyti-
cal perspectives through specialized processing modules for different
analysis types, a meta-cognitive layer for context-appropriate module
selection, result synthesis and conflict resolution, and quality control
and validation checks.
RASTI 000, 000–000 (2026)
ASTRA: Autonomous Scientific Discovery in Astrophysics
3
2.3 Unique Capabilities
Astra integrates sixteen distinct analytical capabilities organized
into four groups:
Causal and Statistical Analysis: (1) Bias Detection—identifies
and quantifies observational biases from survey geometry and se-
lection effects. (2) Scaling Relations Discovery—discovers physical
laws through dimensional analysis and functional form detection.
(3) Causal Inference—discovers causal structures using the PC and
FCI algorithms (Spirtes et al. 2000; Zhang 2008) and distinguishes
physical laws from selection biases. (4) Model Selection—compares
competing theories using Bayesian evidence with proper complexity
penalties.
Data Integration and Analysis: (5) Multi-Wavelength Fusion—
cross-matches sources across wavelengths with astrometric un-
certainty propagation. (6) Uncertainty Quantification—propagates
measurement errors through first-order and Monte Carlo methods.
(7) Temporal Reasoning—detects periodic signals and forecasts time-
series behaviour. (8) Instrument-Aware Analysis—evaluates observa-
tional requirements across astronomical facilities.
Knowledge Generation: (9) Hypothesis Generation—identifies
patterns, detects anomalies, and generates testable hypotheses.
(10) Analogical Reasoning—discovers structural mappings between
different astrophysical systems. (11) Counterfactual Analysis—
simulates physically-grounded scenarios to predict intervention ef-
fects. (12) Physical Model Discovery—identifies functional forms
and validates against theoretical predictions.
Meta-Cognitive Capabilities: (13) Meta-Cognitive Evaluation—
assesses data sufficiency, resolution limits, and observational con-
straints. (14) Anomaly Detection—identifies unusual objects using
ensemble methods. (15) Ensemble Prediction—combines multiple
models using Bayesian Model Averaging. (16) Physical Validation—
checks results against dimensional consistency, conservation laws,
and established principles.
These capabilities are not independent modules but integrated
components. For example, discovering a scaling relation (capabil-
ity 2) involves dimensional analysis (capability 12), physical valida-
tion (capability 16), and uncertainty quantification (capability 6).
Capability Demonstrations in This Paper: Table 1 summarizes
which of the 16 capabilities are demonstrated in each of the first
five test cases. Capabilities not demonstrated here (temporal reason-
ing, instrument-aware analysis, analogical reasoning, counterfactual
analysis, ensemble prediction) are available in the system but demon-
strated in extended test cases available in the GitHub repository.
2.4 Workflow for Scientific Analysis
Astra’s analysis workflow follows this general pattern: Input: Scien-
tific query or observational data; Module Selection: Meta-cognitive
layer selects appropriate analysis modules based on query type and
data characteristics; Analysis Execution: Selected modules perform
their specialized analyses including statistical and ML algorithms
for pattern detection, causal discovery for identifying relationships,
physics engine for theoretical validation, and Bayesian inference for
model comparison; Integration: Results synthesized from multiple
modules, resolving conflicts and identifying consensus conclusions;
Validation: Results checked against physical constraints (dimen-
sional consistency, conservation laws), statistical significance (𝑝-
values, confidence intervals), observational constraints (resolution
limits, selection effects), and domain knowledge (established theo-
ries, previous results); Output: Integrated results with confidence
assessments, uncertainty quantification, and physical interpretation.
2.5 Implementation and Availability
Astra is implemented in Python with approximately 313 000 lines of
code across 621 files. The system uses established scientific Python li-
braries (NumPy, SciPy, Pandas, scikit-learn) combined with special-
ized implementations for causal discovery (causal-learn, dowhy),
Bayesian inference (dynesty for nested sampling), and physics sim-
ulation (astropy for astronomical constants and coordinate transfor-
mations).
Reproducibility: Astra requires Python 3.10 or later. Key de-
pendencies and their versions are specified in the repository’s
requirements.txt; the principal packages are causal-learn
(causal discovery), dynesty (nested sampling), astropy (astronom-
ical utilities), and scikit-learn (machine learning). All results in
this paper can be reproduced from the provided Jupyter notebooks
using these dependencies.
The
complete
system
is
publicly
available
at:
https:
//github.com/Tilanthi/ASTRA (White 2026). This reposi-
tory includes: complete source code and installation instructions;
system architecture documentation with detailed design diagrams;
API documentation and user manual; extended validation with
15 comprehensive test cases; example notebooks and tutorials;
and reproducible code for all results presented in this paper.
The first five test cases can be reproduced using the follow-
ing
Jupyter
notebooks:
test02_scaling_relations.ipynb
(Section
3),
test04_multiwavelength_fusion.ipynb
(Section
4),
test05_hypothesis_generation.ipynb
(Sec-
tion 5), test11_causal_inference.ipynb (Section 6), and
test12_bayesian_model_selection.ipynb (Section 7).
2.6 Operational Monitoring: The Live Dashboard
Autonomous discovery systems require continuous human oversight
to ensure scientific rigour and operational safety. Astra provides this
through a real-time monitoring dashboard (Fig. 1), implemented as a
single-page web application served by a FastAPI backend exposing
89 REST endpoints. The dashboard is organized into nine operational
views; we describe the four primary monitoring views here (the
stigmergy view is described in Section 2.7).
Overview (Fig. 1) displays Astra’s OODA-loop decision engine,
which cycles through five phases—Orient, Select, Investigate,
Evaluate, Update—providing a real-time trace of the system’s au-
tonomous reasoning. A neural topology graph visualizes the cur-
rent hypothesis network, and an autonomous decision log records
every action with timestamps, enabling full auditability. Summary
statistics—hypothesis funnel, confidence radar, null-hypothesis dis-
tribution, discovery rate, and error rate—give the operator an at-a-
glance assessment of the engine’s state.
Safety (Fig. 2) implements three complementary monitoring
mechanisms. A state-space trajectory plot projects the system’s in-
ternal state onto its first two principal components, with concentric
boundaries delimiting safe, caution, and critical operating regions.
An anomaly-detection panel tracks drift metrics over time, flagging
excursions that could indicate distributional shift or numerical in-
stability. Alignment stability is quantified across six dimensions—
Scientific Rigour, Domain Balance, Novelty Pursuit, Epistemic Hu-
mility, Resource Efficiency, and Reproducibility—each scored con-
tinuously and combined into a composite alignment metric (Fig. 2).
Critically, the safety view includes intervention controls (Pause, E-
Stop, Safe Mode) that allow the operator to halt or constrain the
discovery engine at any point, implementing genuine human-in-the-
loop oversight rather than post-hoc review.
RASTI 000, 000–000 (2026)
4
White
Table 1. Capabilities demonstrated in each test case. ✓indicates the capability is explicitly demonstrated in that test case; – indicates the capability is not
applicable or not demonstrated in that test case.
Capability
Test 1
Test 2
Test 3
Test 4
Test 5
(Scaling)
(Multi-𝜆)
(Pattern)
(Causal)
(Bayesian)
Bias Detection
–
✓
–
✓
–
Scaling Relations
✓
–
✓
–
✓
Causal Inference
–
–
–
✓
–
Model Selection
–
–
–
–
✓
Multi-Wavelength Fusion
–
✓
–
–
–
Uncertainty Quantification
✓
✓
✓
–
✓
Temporal Reasoning
–
–
–
–
–
Instrument-Aware Analysis
–
–
–
–
–
Hypothesis Generation
–
–
✓
–
–
Analogical Reasoning
–
–
–
–
–
Counterfactual Analysis
–
–
–
–
–
Physical Model Discovery
✓
–
–
–
✓
Meta-Cognitive Evaluation
✓
✓
✓
✓
✓
Anomaly Detection
–
–
✓
–
–
Ensemble Prediction
–
–
–
–
–
Physical Validation
✓
✓
✓
✓
✓
Discoveries tracks the hypothesis pipeline through five stages:
Proposed →Screening →Testing →Validated →Published. Each
hypothesis is displayed as a summary card showing its domain, sta-
tistical evidence, and current status, allowing the operator to monitor
which hypotheses are progressing through the validation pipeline and
which have been rejected.
Health monitors component status, cycle performance metrics,
domain coverage distribution, and a timestamped audit trail. To-
gether, these four views provide the transparency and intervention
capability required for responsible deployment of autonomous sci-
entific discovery systems.
2.7 Stigmergic Swarm Intelligence
Scientific discovery in large hypothesis spaces requires balancing
exploration of novel domains against exploitation of productive re-
search directions. Astra addresses this through stigmergic swarm in-
telligence: a biologically-inspired coordination mechanism in which
hypotheses leave digital “pheromone trails” that guide future explo-
ration, enabling the system to learn from its own discovery history
without centralized planning (Grassé 1959).
2.7.1 Digital Pheromone Field
The core data structure is a digital pheromone field defined over a
domain-mixture simplex x = (CLD, 𝐷1, 𝐷2) where CLD+𝐷1+𝐷2 =
1. Each scientific domain maps to a fixed point on this simplex
(e.g. Astrophysics at (0.8, 0.1, 0.1), Economics at (0.1, 0.8, 0.1)),
and hypotheses are associated with the coordinates of their parent
domain. Five pheromone types encode different discovery signals:
• Success — deposited when a hypothesis is confirmed with
𝑝< 0.05; strength scales as 2(1 −𝑝)(1 + |𝑑|) where 𝑑is the effect
size, capped at 5.0.
• Failure — deposited when a hypothesis is rejected; strength
scales with prior confidence.
• Novelty — deposited when a genuinely new discovery is
recorded; strength proportional to significance.
• Exploration — deposited whenever a domain is visited, re-
gardless of outcome.
• Danger — deposited at locations where analyses produce
anomalous or numerically unstable results.
Pheromone concentrations evolve according to
𝜙𝑖(𝑡+ 1) = (1 −𝜀) 𝜙𝑖(𝑡) + 𝜌Δ𝜙𝑖,
(1)
where 𝜀= 0.050 is the evaporation rate, 𝜌= 0.100 is the rein-
forcement coefficient, and Δ𝜙𝑖is the new deposit. This update rule,
adapted from ant colony optimization (Dorigo et al. 1996), causes
abandoned research directions to fade while productive ones accu-
mulate reinforcement.
2.7.2 Gordon’s Biological Parameters
The exploration–exploitation balance is calibrated using parameters
derived from Gordon (2010)’s empirical studies of harvester ant
colonies (Pogonomyrmex barbatus). Three key parameters govern
agent behaviour:
• Anternet weight (𝑤𝑎= 0.600): The degree to which interaction
frequency influences foraging decisions. In the ant colony, returning
foragers stimulate outgoing foragers through brief antennal contact;
in Astra, successful hypothesis tests stimulate further investigation
of the same domain.
• Restraint weight (𝑤𝑟= 0.400): Colony-level restraint under re-
source scarcity. When recent discovery rates are low, Astra reduces
exploitation and increases exploratory behaviour.
• Switch probability (𝑝𝑠= 0.150): The probability of task-
switching per contact cycle. This prevents agents from persever-
ating on unproductive strategies, analogous to the 15 per cent task-
switching rate observed in ant colonies.
Agent contact rates are bounded between 𝜈min = 0.033 and 𝜈max =
0.167 contacts s−1 (2–10 contacts min−1), matching the empirical
range for P. barbatus (Gordon 2010). Successful outcomes increase
the contact rate by 10 per cent (up to 𝜈max), while failures decrease it
by 5 per cent (down to 𝜈min), implementing the “anternet” feedback
principle where colony-level foraging activity tracks food availability.
RASTI 000, 000–000 (2026)
ASTRA: Autonomous Scientific Discovery in Astrophysics
5
Figure 1. The Astra Live Dashboard overview during autonomous operation. Left: Activity stream logging statistical evaluations, FDR corrections, and engine
decisions, with the OODA decision engine displaying the current phase of the Orient–Select–Investigate–Evaluate–Update cycle. Centre: AGI Neural
Topology graph visualizing the hypothesis network with domain-coloured nodes showing hypothesis interconnections. Right: Data visualizations including the
hypothesis funnel, domain activity, confidence radar, 𝐻0 distribution, discovery rate, and error rate. The dashboard provides nine tabbed views for comprehensive
system monitoring.
2.7.3 Swarm Agent Architecture
Five specialized agent types operate on the pheromone field, each
implementing a distinct scientific strategy:
(i) Explorer — Seeks domains with the lowest Exploration
pheromone concentration, maximizing coverage of the hypothesis
space. In the current deployment: 98 actions taken.
(ii) Exploiter — Follows Success pheromone gradients to
deepen investigation in productive domains. In the current deploy-
ment: 132 actions, 99 per cent success rate.
(iii) Falsifier — Targets well-established hypotheses (high cumu-
lative knowledge 𝐶𝐾) for attempted disproof, depositing Failure
pheromone when weaknesses are found. Implements Popperian fal-
sificationism at the system level.
(iv) Analogist
—
Computes
cosine
similarity
between
pheromone profiles of different domains, identifying structural analo-
gies that seed cross-domain hypotheses. In the current deployment:
74 actions, 100 per cent success rate.
(v) Scout — Performs random walks with Novelty sensing, de-
tecting unexpected signals that directed agents might miss.
These agents are coordinated by a SwarmCoordinator that maps
them to Astra’s OODA decision cycle: the Scout operates dur-
ing Orient, the Explorer and Exploiter influence Select through
pheromone-based re-ranking of candidate hypotheses, the Falsifier
validates during Investigate, and all agents deposit pheromones
during Update.
2.7.4 Pheromone-Guided Hypothesis Selection
During the Select phase, candidate hypotheses are re-ranked by
blending the engine’s original score with a pheromone-derived score:
𝑠final = (1 −𝑤) 𝑠engine + 𝑤𝑠pheromone,
(2)
where 𝑤= 0.3 is the pheromone weight. The pheromone score at
each hypothesis location is computed as a weighted combination
of four signals: Success concentration (weight 0.4), inverse Fail-
ure (0.2), Novelty (0.2), and inverse Exploration (0.2), favouring
regions that are productive, novel, and under-explored. A curiosity
value 𝑐𝑘, computed from recent success rates and time since last dis-
covery, determines the global exploration strategy: 𝑐𝑘> 0.7 triggers
exploration mode, 𝑐𝑘< 0.3 triggers exploitation, and intermediate
values maintain a balanced approach.
2.7.5 Quality Assurance
Two mechanisms ensure that stigmergic guidance improves rather
than degrades discovery performance.
A/B testing framework: Astra maintains parallel tracking of
pheromone-guided versus baseline (unguided) hypothesis selections.
After 1 014 guided trials and 12 confirmed successes (1.2 per cent
discovery rate), the system compares success rates to quantify the
benefit of pheromone guidance.
Safety circuit breaker: If the pheromone-guided success rate
falls more than 20 per cent below the baseline rate (assessed every
20 engine cycles after a minimum of 20 trials per arm), the system
RASTI 000, 000–000 (2026)
6
White
Figure 2. Safety monitoring dashboard. Left: State-space mind trajectory projected onto the first two principal components (PC1: Confidence Variance, PC2:
Domain Diversity), with concentric boundaries delineating nominal (green), caution (amber), and critical (red) operating regions. Right: Anomaly detection
drift monitor tracking five metrics—Confidence Drift (0.32, Nominal), Exploration Balance (0.61, Critical), Domain Diversity (0.48, Warning), Value Stability
(0.55, Warning), and Confidence Velocity (0.22, Nominal)—with colour-coded severity thresholds enabling operators to identify distributional shift or numerical
instability in real time.
automatically halves the pheromone weight 𝑤, reducing stigmergic
influence until performance recovers. This prevents the pheromone
field from reinforcing unproductive research directions.
2.7.6 Knowledge Gap Analysis
The stigmergic memory maintains per-domain exploration coverage
scores, identifying under-explored regions of the hypothesis space. In
the current deployment, the knowledge gap analysis reveals: Astro-
physics fully explored (gap score 0.00), Cross-Domain well explored
(0.04), with Epidemiology (1.00) and Climate (0.73) identified as the
least explored domains, directing the Explorer agent toward these ar-
eas. Fig. 3 shows the complete stigmergy dashboard view, including
the pheromone field status, knowledge gap analysis, Gordon param-
eters, and swarm agent activity.
2.8 Cognitive Architecture
Astra’s analytical pipeline is coordinated by a cognitive architecture
that implements a central reasoning loop: perceive (ingest data), rea-
son (apply causal and statistical models), discover (identify patterns
and anomalies), learn (update internal representations), and reflect
(evaluate reasoning quality). This architecture is designed to provide
structured coordination among Astra’s analytical modules, rather
than ad hoc sequential execution.
2.8.1 Dynamic Knowledge Graph
The system maintains a dynamic knowledge graph implemented
using NetworkX, in which nodes represent scientific concepts,
datasets, hypotheses, and analytical results, while edges encode
17 relation types spanning causal (“causes”, “inhibits”), theoretical
(“predicts”, “explains”), and epistemic (“contradicts”, “supports”)
categories. The graph supports belief propagation across connected
nodes, analogy detection between structurally similar subgraphs, and
knowledge gap identification where sparse connectivity suggests un-
derexplored research directions. As Astra processes data and gen-
erates hypotheses, the graph is updated incrementally, providing a
persistent representation of the system’s accumulated scientific un-
derstanding.
2.8.2 Neuro-Symbolic Integration
Astra
implements
a
bidirectional
neuro-symbolic
reasoning
loop. Neural components (pattern recognition, anomaly detection,
embedding-based similarity) identify candidate regularities in data,
which are then passed to symbolic modules for formal valida-
tion: dimensional consistency checking via the Buckingham 𝜋the-
orem, causal structure verification through structural causal mod-
els, and logical consistency checking against existing theories in the
knowledge graph. Conversely, symbolic reasoning can direct neural
search—for example, identifying that a predicted scaling relation has
not been tested in a particular mass range, triggering targeted pattern
recognition. This bidirectional integration is designed to combine the
RASTI 000, 000–000 (2026)
ASTRA: Autonomous Scientific Discovery in Astrophysics
7
Figure 3. Stigmergy dashboard showing the swarm intelligence system during autonomous operation. Top left: Knowledge gaps by domain, with Epidemiology
(1.00) and Climate (0.73) identified as the least explored. Top right: Exploration strategy panel showing current strategy (explore), curiosity value (𝑐𝑘= 0.82),
and recommended domain (Epidemiology). Bottom left: Gordon’s biological parameters calibrated from harvester ant colony research (Gordon 2010). Bottom
right: Swarm agent activity showing the Explorer (98 actions), Exploiter (132 actions, 99 per cent success), Analogist (74 actions, 100 per cent success), Falsifier,
and Scout agents.
pattern-finding strengths of statistical methods with the interpretabil-
ity and rigour of symbolic reasoning (Pearl 2009).
2.8.3 Meta-Cognitive Monitoring
A meta-cognitive layer monitors Astra’s reasoning processes in
real time, maintaining a cognitive state variable that can take val-
ues NORMAL, UNCERTAIN, CONFUSED, or OVERCONFIDENT based on
internal consistency metrics. This module tracks reasoning traces,
analyses error patterns across completed analyses, and adjusts analyt-
ical strategy accordingly—for example, switching from exploitative
(testing known relationships) to exploratory (seeking novel patterns)
behaviour when the system detects diminishing returns. While full
validation of this component is deferred to future work, it provides
the architectural foundation for self-improving analytical behaviour,
as reflected in the adaptive strategy metrics shown in Fig. 5.
2.9 Multi-Agent Scientific Debate
To evaluate competing hypotheses, Astra implements a multi-agent
scientific debate system in which specialized agents—each instan-
tiated with a defined scientific role (e.g. theorist, experimentalist,
sceptic, statistician)—engage in structured argumentation over can-
didate hypotheses.
Debates proceed through four phases: opening (agents present ini-
tial positions with supporting evidence), rebuttal (agents challenge
opposing positions), clarification (agents refine arguments in re-
sponse to challenges), and synthesis (a moderator agent integrates
positions toward consensus). This structure is designed to reduce
confirmation bias by ensuring that each hypothesis faces systematic
challenge before acceptance.
The consensus engine supports seven aggregation methods: ma-
jority vote, expertise-weighted vote, Bayesian consensus (combin-
ing agent posteriors), Delphi method (iterated anonymous revision),
Condorcet voting, Borda count, and weighted ensemble. The choice
of method is configurable; for the analyses presented here, expertise-
weighted voting is used by default, where agent weights are updated
based on historical prediction accuracy. An expertise tracking mod-
ule maintains per-agent performance records across scientific do-
mains, enabling task assignment that matches agent specializations
to problem characteristics. We note that while the multi-agent debate
architecture is implemented and operational, its independent contri-
bution to analytical quality has not been isolated in the present test
cases and is a target for future ablation studies.
2.10 Theory Framework
Astra includes a theory framework comprising approximately 5 100
lines across 12 modules, designed to support the lifecycle of scien-
tific theories from initial proposal through validation. Theories are
represented as structured objects with associated confidence scores
(Bayesian), supporting evidence, predictions, and known limitations.
The framework implements a three-phase pipeline. Phase 1 (for-
malization) constructs theory objects from validated hypotheses, per-
forms contradiction detection against existing theories in the knowl-
RASTI 000, 000–000 (2026)
8
White
Figure 4. Verified scientific discoveries recovered by Astra during autonomous operation. Kepler’s Third Law from 2 839 exoplanets (slope 1.497 vs. theory
1.500, 𝑅2 = 0.9982); accelerating expansion from 1 701 Type Ia supernovae (+6.6 per cent excess slope indicating dark energy); galaxy colour bimodality from
2 000 SDSS galaxies (blue fraction declining from 50 per cent to 10 per cent over 3 Gyr); stellar populations from Gaia DR3; and causal inference correctly
identifying redshift as causing colour changes.
edge graph, and applies symbolic dimensional analysis to verify
physical consistency. Phase 2 (abstraction) promotes individual hy-
potheses to broader theories through generalization, identifies cross-
domain analogies using structural similarity in the knowledge graph,
and scans for symmetry properties that may indicate deeper physi-
cal principles. Phase 3 (evaluation) applies abductive reasoning to
assess explanatory power, designs critical experiments that would
distinguish between competing theories, and performs internal self-
consistency checking.
Exploration of the theoretical space employs Monte Carlo Tree
Search (MCTS; Kocsis & Szepesvári 2006), treating theory refine-
ment as a sequential decision problem. Each node in the search
tree represents a theory state, with branches corresponding to possi-
ble modifications (adding predictions, incorporating new evidence,
generalizing scope). MCTS balances exploitation of promising the-
ories against exploration of novel theoretical directions, guided by
an upper confidence bound on the theory’s explanatory power. This
component is designed to support creative scientific reasoning; its
effectiveness on open problems remains to be demonstrated.
2.11 Autonomous Research Agenda
Astra’s curiosity engine generates and prioritizes research goals
using information-theoretic metrics. Six curiosity dimensions guide
research direction: information_gap (expected reduction in knowl-
edge graph uncertainty), novelty_potential (distance from ex-
plored regions in concept space), feasibility_balance (esti-
mated computational cost versus expected information gain), sci-
entific_importance (centrality of the target concept in the knowl-
edge graph), collaborative_opportunity (potential for cross-
domain synthesis), and resource_efficiency (expected discoveries
per computational unit).
Research goals follow a controlled lifecycle: proposed →ap-
proved →in_progress →completed, with explicit approval gates.
Goals require either human approval (via the live dashboard; Sec-
tion 2.6) or autonomous approval from the meta-cognitive layer (Sec-
tion 2.8) before execution begins, ensuring that the system does not
pursue research directions without oversight. Priority scoring com-
bines the six curiosity dimensions with domain-specific importance
weights and feasibility estimates, producing a ranked agenda that the
stigmergic swarm layer (Section 2.7) uses to allocate agent effort.
This design ensures that Astra’s autonomous exploration remains
directed toward scientifically meaningful questions while respecting
computational and human-oversight constraints.
2.12 Positioning Relative to Other Approaches
Astra occupies a distinct position in the landscape of AI for sci-
entific discovery. Unlike machine learning systems that focus on
prediction, Astra emphasizes causal understanding and physical
validation. Unlike large language models that require explicit pro-
gramming for numerical analysis, Astra integrates physical valida-
tion and causal interpretation natively. Unlike domain-specific tools
designed for single tasks, Astra connects multiple analysis types
within a unified framework. Unlike systems claiming artificial gen-
eral intelligence, Astra operates within well-defined domains using
RASTI 000, 000–000 (2026)
ASTRA: Autonomous Scientific Discovery in Astrophysics
9
Figure 5. Self-improvement trajectory showing discovery strength over 397 discoveries. The scatter plot displays individual discovery strengths colour-coded
by domain, with a rolling average trendline. The method performance table (right) shows per-method, per-domain success rates, enabling adaptive strategy
selection: 184 method outcomes tracked with an overall 89.1 per cent success rate.
established algorithms, assisting human reasoning rather than re-
placing it. The cognitive architecture and multi-agent debate system
(Sections 2.8–2.9) provide structured coordination, but remain early-
stage components requiring independent validation. A more detailed
comparison appears in Section 11.5.
3 TEST CASE 1: SCALING RELATIONS ANALYSIS
Objective: Validate Astra’s ability to discover and physically vali-
date scaling relations in observational data.
3.1 Data and Methods
We use 24 interstellar filaments observed by Herschel (Arzoumanian
et al. 2011, 2019) with measured widths, column densities, and line
masses. Astra analyses these data to discover scaling relations and
validate them against physical theory.
The analysis proceeds through:
(i) Automated data ingestion and quality control
(ii) Dimensional analysis using the Buckingham 𝜋theorem (Buck-
ingham 1914)
(iii) Scaling relation discovery through functional form fitting
(iv) Physical validation against virial equilibrium predictions
(v) Uncertainty quantification through Monte Carlo error propa-
gation
Power-law fits are performed using ordinary least squares (OLS) re-
gression in log–log space, with uncertainties estimated via bootstrap
resampling (10 000 resamples).
Figure 6 shows the scaling relations identified by Astra.
3.2 Results
Astra identifies several scaling relations:
Universal Filament Width: The analysis identifies a characteris-
tic filament width of 0.098 ± 0.019 pc, consistent with the ∼0.1 pc
value reported by Arzoumanian et al. (2011) from a larger sam-
ple. The width distribution is well-described by a log-normal with
𝜎= 0.19 dex, consistent with the range reported in recent Herschel
analyses (Arzoumanian et al. 2019). We note that the apparent uni-
versality of this width has been debated in the literature (see, e.g.,
Panopoulou et al. 2022, for a discussion of resolution effects).
Virial Scaling Relation: A power-law relation between line mass
and velocity dispersion is detected with Pearson correlation 𝑟=
0.988, 𝑝< 10−18, consistent with virial equilibrium predictions.
The measured exponent is 0.49 ± 0.03, compared to the theoretical
value of 0.5 from virial equilibrium; however, the ratio is 0.49/0.5 =
0.98 and the 2.7𝜎tension with the virial prediction warrants further
investigation with larger samples.
Dimensionless Groups: The Buckingham 𝜋theorem analysis
identifies three independent dimensionless groups from five physi-
cal quantities (width, line mass, velocity dispersion, column density,
sound speed), correctly reducing the parameter space and guiding
the search for physically meaningful scaling relations. The dimen-
sional analysis module produces results in agreement with the virial
theorem prediction 𝜎𝑣∝
√︁
𝑀𝑙/𝐿, though the 72 per cent agreement
with the predicted exponent is approximate and does not constitute a
strong test of virial equilibrium.
RASTI 000, 000–000 (2026)
10
White
0.050 0.075 0.100 0.125 0.150 0.175 0.200
Filament FWHM width (pc)
0
20
40
60
80
100
Number of filaments
(a)
W = 0.098 ± 0.019 pc
100
Velocity dispersion 
v (km s
1)
100
101
Line mass Mline (M
 pc
1)
(b) Herschel filaments
Mline
1.98
v
 (r = 0.995)
Figure 6. Scaling relations for 24 Herschel filaments identified by Astra. Top panel: Width distribution showing a characteristic scale of 0.098 ± 0.019 pc,
consistent with the ∼0.1 pc “universal width” reported by Arzoumanian et al. (2011) (though see Panopoulou et al. 2022 for discussion of apparent universality).
Bottom panel: Line mass vs. velocity dispersion, showing the virial scaling relation with Pearson correlation 𝑟= 0.988, 𝑝< 10−18.
3.3 Physical Interpretation
The results are consistent with several established results in the ISM
filament literature:
• The ∼0.1 pc characteristic width is consistent with the sonic
scale, where turbulent and thermal pressures are comparable (André
et al. 2010).
• The strong virial scaling relation (𝑟= 0.988) suggests these
filaments are approximately in virial equilibrium.
• Dimensional analysis correctly identifies the key physical quan-
tities and their relationships without requiring prior specification of
the expected functional form.
Limitations: The sample of 24 filaments is small and drawn from
a limited set of molecular clouds. The identified relations are well-
established in the literature; the value of this test case is not in novel
discovery but in demonstrating Astra’s ability to correctly recover
known physical scaling relations through automated dimensional
analysis and statistical fitting.
For filament properties, mass scales as 𝑀∝𝐷2 (from flux) and
length scales as 𝐿∝𝐷, making the mass-to-length ratio 𝑀/𝐿∝𝐷. A
systematic distance uncertainty of 20 per cent—typical for kinematic
distance estimates to molecular cloud complexes—propagates to a
∼20 per cent systematic uncertainty in 𝑀/𝐿. This is comparable to
the 12 per cent discrepancy between measured and theoretical virial
slopes, suggesting that distance systematics alone could account for
much of the observed 2.7𝜎tension.
4 TEST CASE 2: MULTI-WAVELENGTH DATA FUSION
Objective: Demonstrate Astra’s multi-wavelength cross-matching
and data fusion capabilities.
4.1 Data and Methods
This test uses the Chandra Deep Field South (CDFS) X-ray catalogue
(Giacconi et al. 2001) and optical counterpart catalogues (Alexander
et al. 2003; Bauer et al. 2004). Astra performs probabilistic cross-
matching between X-ray and optical sources using Bayesian methods.
The cross-matching algorithm implements:
(i) Likelihood ratio method (Sutherland & Saunders 1992) for
probabilistic associations
(ii) Bayesian posterior probability estimation for each candidate
match
(iii) Astrometric uncertainty propagation from both catalogues
(iv) Classification based on X-ray-to-optical flux ratios and hard-
ness ratios
Figure 7 shows the cross-matching results.
4.2 Results
From the input catalogues, Astra identifies 60 secure matches from
370 X-ray sources, with a false match rate below 5 per cent. Source
classification based on X-ray and optical properties yields:
• 41 Active Galactic Nuclei (AGN), identified by high X-ray-to-
optical flux ratios and hard X-ray spectra
RASTI 000, 000–000 (2026)
ASTRA: Autonomous Scientific Discovery in Astrophysics
11
53.0
53.1
53.2
RA (deg)
27.90
27.85
27.80
27.75
27.70
27.65
Dec (deg)
(a)
Optical
X-ray
0
2
4
6
8
10
12
Angular separation (arcsec)
0.0
0.2
0.4
0.6
0.8
1.0
Normalised density
(b)
Genuine matches
Chance coincidences
Threshold (2′′)
Figure 7. Multi-wavelength cross-matching in the Chandra Deep Field South. Top panel: Spatial distribution of X-ray sources (red) and matched optical
counterparts (blue) with match radii shown as circles. Bottom panel: Distribution of match likelihoods showing the separation between genuine matches and
chance associations.
• 19 Stars, identified by soft X-ray emission and stellar optical
colours
• 0 Normal galaxies classified (reflecting the bias toward X-ray-
bright AGN in the CDFS rather than the absence of galaxies in the
field; normal galaxies are present in the optical catalogue but fall
below the X-ray detection threshold)
We adopt the classification thresholds: AGN if hardness ratio HR >
−0.2 and log( 𝑓𝑋/ 𝑓opt) > −1; stars if HR < −0.2 or log( 𝑓𝑋/ 𝑓opt) <
−1.
Quality assessment: The median positional offset between
matched sources is 0.8 arcsec, consistent with the combined X-ray
and optical astrometric uncertainties. The classification results are
broadly consistent with the source populations identified by Bauer
et al. (2004) in the CDFS, though detailed comparison is limited by
differences in catalogue depth and methodology.
4.3 Physical Interpretation
The high AGN fraction among cross-matched sources reflects the
X-ray selection function: the CDFS reaches sufficient depth to detect
AGN at cosmological distances but resolves only the brightest normal
galaxies. Astra correctly identifies this selection effect and notes it
as a caveat on the source classification.
Limitations: The zero count of normal galaxies classified is a se-
lection effect, not a physical result. The cross-matching uses standard
Bayesian methods and does not introduce novel algorithmic devel-
opments. The value of this test case is in demonstrating Astra’s
ability to chain catalogue cross-matching, uncertainty propagation,
and physical classification within a single integrated workflow. We
note that the 68 per cent AGN fraction in our 60-source matched
sample is not representative of the full CDFS X-ray source popu-
lation, which includes many optically faint high-redshift AGN; the
tri-band secure detection requirement biases the sample toward the
brightest, most compact, and lowest-redshift sources.
5 TEST CASE 3: PATTERN RECOGNITION IN GALAXY
PROPERTIES
Objective: Validate Astra’s pattern recognition capability on a com-
plex, multi-dimensional astrophysical dataset.
5.1 Data and Methods
We analyse 600 galaxies from the Sloan Digital Sky Survey (SDSS;
Abazajian et al. 2009) with physical properties from the MPA-JHU
value-added catalogue (Brinchmann et al. 2004). Properties include
stellar mass, metallicity, star formation rate, velocity dispersion, and
environment density.
Astra performs unsupervised pattern recognition including:
(i) Principal Component Analysis (PCA) for dimensionality re-
duction
(ii) Gaussian Mixture Model (GMM) clustering for population
identification
(iii) Correlation analysis with statistical significance testing
(iv) Anomaly detection for identifying unusual objects
Figure 8 shows the galaxy property distributions and relationships.
RASTI 000, 000–000 (2026)
12
White
8
9
10
11
12
log (M /M
)
7.75
8.00
8.25
8.50
8.75
9.00
9.25
9.50
12 + log(O/H)
(a)
Median
16th 84th percentile
8
9
10
11
12
log (M /M
)
13
12
11
10
9
log sSFR (yr
1)
Green
valley
(b)
Star-forming
Quiescent
Main sequence fit
Figure 8. Galaxy property correlations identified by Astra in the SDSS sample. Left: Mass–metallicity relation showing the expected positive correlation
(Tremonti et al. 2004). Right: Specific star formation rate vs. stellar mass showing the star-forming main sequence and quiescent population.
5.2 Results
Astra autonomously identifies 13 statistically significant correla-
tions among galaxy properties. We highlight five that correspond to
well-established astrophysical relationships:
1. Mass–Metallicity Relation:
• ASTRA identified: Positive correlation between stellar mass and
gas-phase metallicity (𝑟= 0.68, 𝑝< 10−27)
• Literature: Mass–metallicity relation (Tremonti et al. 2004),
one of the most fundamental relationships in galaxy evolution
• Significance: Astra correctly identifies this as a primary rela-
tionship rather than a secondary correlation
2. Downsizing of Star Formation:
• ASTRA identified: Anti-correlation between stellar mass and
specific star formation rate (sSFR) for log 𝑀★/𝑀⊙> 10 (𝑟= −0.45,
𝑝< 10−14)
• Literature: Downsizing (Brinchmann et al. 2004), where more
massive galaxies form stars less efficiently
• Significance: Astra identifies this as a mass-dependent effect,
correctly separating it from the star-forming main sequence
3. Morphology–Density Relation:
• ASTRA identified: Correlation between environment density and
galaxy type (early-type fraction increasing with density, 𝑟= 0.37,
𝑝< 10−8)
• Literature: Morphology–density relation (Dressler 1980)
• Significance: Astra correctly identifies environment as a sec-
ondary driver of galaxy properties, distinct from mass
4. Faber–Jackson/Tully–Fisher Relations:
• ASTRA identified: Correlation between velocity dispersion and
stellar mass (𝑟= 0.71, 𝑝< 10−30)
• Literature: Faber–Jackson relation for early-type galaxies; the
analogous Tully–Fisher relation for late-types
• Significance: Astra identifies this across the full galaxy pop-
ulation, correctly noting different slopes for early-type and late-type
subsamples
5. Environmental Quenching:
• ASTRA identified: Suppressed star formation rates in high-
density environments, conditional on stellar mass (ΔSFR ≈−0.3 dex
at fixed mass)
• Literature: Environmental quenching (Peng et al. 2010), mass
quenching distinguished from environmental quenching
• Significance: Astra’s causal reasoning module identifies envi-
ronment and mass as independent quenching channels
5.3 Physical Interpretation
Astra correctly identifies and interprets multiple established rela-
tionships in the SDSS galaxy sample. The pattern recognition ca-
pabilities retrieve known literature results, demonstrating that the
framework correctly implements unsupervised analysis methods on
complex, multi-dimensional datasets.
Limitations:
All
five
highlighted
relationships
are
well-
established in the literature. This test case demonstrates validation of
pattern recognition, not novel discovery. The 600-galaxy sample is
small by SDSS standards, and larger samples could reveal additional
trends.
6 TEST CASE 4: CAUSAL INFERENCE DEMONSTRATOR
Objective: Demonstrate Astra’s causal reasoning capability on real
stellar data.
RASTI 000, 000–000 (2026)
ASTRA: Autonomous Scientific Discovery in Astrophysics
13
6.1 Data and Methods
We use 1000 stars from Gaia Data Release 2 (Gaia Collaboration et al.
2018) with measured parallaxes, proper motions, and photometric
colours. Astra applies the PC algorithm (Spirtes et al. 2000) and the
FCI algorithm (Zhang 2008) to discover causal relationships among
stellar properties.
The causal discovery pipeline:
(i) Constructs an initial complete graph over stellar variables
(ii) Uses conditional independence tests (Fisher’s 𝑍-test) to re-
move edges (𝛼= 0.05)
(iii) Orients edges using V-structure detection and the FCI orien-
tation rules
(iv) Identifies potential latent confounders through the FCI algo-
rithm
Figure 9 shows the recovered causal structure.
6.2 Results
Astra’s causal discovery correctly recovers several textbook causal
relationships:
• Distance →apparent magnitude: Distance causes the ob-
served brightness (not the reverse). This is physically obvious but
non-trivial for a purely data-driven algorithm to identify, since dis-
tance and apparent magnitude are strongly correlated.
• Stellar mass →luminosity: The mass–luminosity relation is
identified as causal rather than merely correlational.
• Temperature →colour: Effective temperature causes photo-
metric colour, correctly oriented.
• Parallax as distance proxy: Astra correctly identifies parallax
as a proxy for distance (inverse relationship), flagging potential biases
from parallax error propagation.
The FCI algorithm additionally identifies one potential latent con-
founder: metallicity, which is not directly measured in the Gaia pho-
tometric catalogue but affects both temperature and luminosity.
6.3 Physical Interpretation and Limitations
The causal relationships recovered are well-known textbook results—
obvious to any domain expert, as these are defining relationships and
well-understood selection effects, not discoveries. The value of this
test case is not in discovering novel relationships but in demonstrating
that Astra’s causal reasoning module correctly distinguishes causal
from correlational relationships in observational astronomical data.
Limitations: The PC algorithm assumes causal sufficiency (no
latent confounders), which is rarely satisfied in astronomical data.
The FCI algorithm relaxes this assumption but can only detect, not
identify, latent confounders. The conditional independence tests are
calibrated for linear, Gaussian relationships; non-linear causal effects
may be missed. This test case should be understood as a basic demon-
stration of causal discovery methodology, not a production-quality
causal analysis.
For genuine scientific value, causal inference would need to be
applied to problems where the causal structure is genuinely non-
obvious, such as: disentangling magnetic field, turbulence, and ther-
mal support contributions to molecular cloud core stability; identify-
ing causal drivers of the star formation main sequence; or determining
causal sequences in galaxy quenching processes. Such applications
would require careful consideration of confounding variables, latent
variables, and domain-specific constraints beyond what is demon-
strated here.
7 TEST CASE 5: BAYESIAN MODEL SELECTION
Objective: Demonstrate Astra’s Bayesian model comparison capa-
bility with physically-motivated models.
7.1 Data and Methods
We use the same 24 Herschel filaments from Test Case 1 (Sec-
tion 3), now comparing competing models for the line-mass–velocity-
dispersion relation. The candidate models are:
(i) Power law: 𝜎𝑣= 𝐴× (𝑀𝑙/𝑀⊙pc−1)𝛼, physically motivated
by the virial theorem
(ii) Logarithmic: 𝜎𝑣= 𝐴+ 𝐵× ln(𝑀𝑙/𝑀⊙pc−1), empirical
(iii) Linear: 𝜎𝑣= 𝐴+ 𝐵× (𝑀𝑙/𝑀⊙pc−1), null model
(iv) Broken power law: Two-segment power law with a break,
more flexible
Prior specification: For model comparison, we adopt the follow-
ing weakly-informative priors:
• Amplitude 𝐴: log-uniform on [0.01, 10] km s−1
• Exponent 𝛼: Gaussian N (0.5, 0.3), centred on the virial predic-
tion
• Intrinsic scatter: half-Cauchy(0, 0.1)
These priors are broad enough to accommodate all physically reason-
able values while providing proper normalization for the Bayesian
evidence integral. Results are robust to moderate changes in prior
widths (factor of 2).
Astra computes the Bayesian evidence for each model using:
(i) Evidence computation: Marginal likelihood estimation using
nested sampling and the learned harmonic mean (Spurio Mancini
et al. 2023)
(ii) Model comparison: PSIS-LOO-CV and Bayes factors (Eadie
et al. 2023)
(iii) Complexity penalty: Automatic Occam’s razor effect from
marginal likelihood, consistent with the BIC approximation (Schwarz
1978)
(iv) Posterior predictive check: Validates model predictions
against observed data
7.2 Results
Figure 10 shows the model comparison results.
Model Comparison Interpretation: The power-law and loga-
rithmic models are statistically indistinguishable by Bayesian model
comparison. A Bayes factor of 1.2 indicates parity, and PSIS-LOO-
CV cross-validation strongly supports both models (Eadie et al.
2023). The logarithmic model has slightly higher 𝑅2 (0.942 vs 0.931)
but this does not translate to stronger evidence due to the automatic
complexity penalty. The strong preference for power-law/logarithmic
models over linear (33 000×) and broken power-law (123 000×) mod-
els demonstrates the automatic Occam’s razor effect: the broken
power-law has higher 𝑅2 but is penalized for its additional complex-
ity.
Theoretical Validation: The power-law model corresponds to the
virial theorem prediction 𝜎𝑣∝
√︁
𝑀/𝐿. The measured exponent is
0.0812 ± 0.0043, compared to the theoretical value of 0.0927. The
RASTI 000, 000–000 (2026)
14
White
Mass
Age
Metallicity
Temperature
Luminosity
Radius
Discovered causal direction
Undetermined orientation
Figure 9. Causal graph discovered by Astra from 1000 Gaia stars. Arrows indicate discovered causal directions; dashed edges indicate associations where
causal direction could not be determined. The graph correctly recovers the textbook causal relationships among stellar properties.
dimensionless parameter ratio is 0.0812/0.0927 = 0.88 (88 per cent
of the predicted value), corresponding to the 72 per cent agree-
ment reported in Section 3’s dimensional analysis. This 2.7𝜎tension
is suggestive but not definitive, and may reflect real physics (non-
thermal support, magnetic fields) or systematic effects in the small
sample.
7.3 Physical Interpretation and Limitations
The Bayesian model comparison demonstrates the automatic Oc-
cam’s razor: more complex models are penalized unless the addi-
tional complexity is justified by significantly better fit to the data.
The joint consideration of statistical evidence and physical motiva-
tion (virial theorem) within a single automated workflow illustrates
the value of the integrated approach.
Limitations: The 24-filament sample limits the discriminating
power. The evidence computation depends on the choice of priors;
while we have checked robustness to moderate prior changes, strongly
RASTI 000, 000–000 (2026)
ASTRA: Autonomous Scientific Discovery in Astrophysics
15
0
2
4
6
8
v (km s
1)
25
0
25
50
75
100
125
Mline (M
 pc
1)
(a) Power-law (best)
Logarithmic
Linear
Data
25
20
15
10
5
0
ln Bi, PL (log Bayes factor vs power-law)
Power-law
Broken
power-law
Logarithmic
Linear
Strong evidence
0.0
-2.1
-8.3
-24.7
(b)
Figure 10. Bayesian model comparison for the line-mass–velocity-dispersion relation. Top panel: Data with best-fit power-law (solid) and logarithmic (dashed)
models, which are statistically indistinguishable by Bayes factor. Bottom panel: Log Bayes factors relative to the power-law model, showing strong preference
for power-law/logarithmic over linear and broken power-law models.
different priors could change the conclusions. The comparison of
only four model families is not exhaustive.
8 TEST CASE 6: DISCOVERY-MODE OPERATION ON
SYNTHETIC DATA
Objective: Demonstrate that Astra can operate in discovery mode—
identifying patterns and causal structure without being told what
to look for—under controlled conditions where the ground truth is
known.
This test case is conceptually different from Tests 1–5: rather
than recovering known astrophysical results, it tests whether Astra
can discover genuine causal structure from data alone, and generate
testable predictions for future validation.
8.1 The Star Formation Threshold Problem
Star formation in molecular clouds appears to require exceeding
a column density threshold (André et al. 2010), but the physical
mechanism underlying this threshold—and whether column density
is a cause or proxy—remains debated. Several candidate mechanisms
have been proposed:
• Gravitational instability: Star formation begins when the Jeans
mass drops below the cloud mass, allowing gravitational collapse
• Magnetic support: Magnetic fields provide support against
collapse; star formation requires sufficient mass-to-flux ratio
• Turbulent support: Turbulence provides support against col-
lapse; the virial parameter characterises the balance
• Shielding: Column density provides self-shielding from disso-
ciating radiation, enabling molecule formation
8.2 Methods: Knowledge Isolation Mode
To provide a controlled test of discovery capability, we designed
a synthetic dataset with embedded causal structure (described in
Section 8.3) and operated Astra in “knowledge isolation mode”:
Knowledge Isolation Protocol:
• Disabled: Access to MORK ontology, domain knowledge base,
and literature embeddings
• Disabled: Astrophysical terminology recognition and concept
mapping
• Enabled: Statistical analysis, causal discovery algorithms, di-
mensional analysis, hypothesis generation
• Enabled: Physical reasoning (conservation laws, dimensional
consistency) but without domain-specific knowledge
This protocol ensures that any patterns Astra discovers come
from the data, not from encoded domain knowledge. The knowl-
edge isolation is implemented at the software level by disabling
the MORK knowledge base query interface and removing domain-
specific prompt templates.
Astra’s analysis proceeds through six phases:
(i) Exploratory data analysis and feature characterisation
(ii) Correlation analysis and feature importance ranking
(iii) Causal structure discovery using PC and FCI algorithms
(iv) Hypothesis generation with confidence scores
(v) Intervention analysis to validate causal claims
(vi) Testable prediction generation
RASTI 000, 000–000 (2026)
16
White
8.3 Synthetic Dataset with Ground Truth
We constructed a synthetic dataset of 500 molecular cloud regions
with the following causal structure (known to the author, hidden from
Astra):
True Causal Drivers:
(i) Jeans mass (gravitational instability): Primary driver. Star for-
mation occurs when cloud mass exceeds the Jeans mass.
(ii) Magnetic field strength: Secondary driver. Strong magnetic
fields suppress star formation by providing additional support against
gravitational collapse.
(iii) Virial parameter: Tertiary driver. Characterises the balance
between gravitational and kinetic energy.
Proxy Variables:
(i) Column density: Correlated with both Jeans mass and star
formation but is a proxy, not a direct cause. The correlation arises
because higher column density clouds tend to have higher masses
(potentially exceeding Jeans mass) and provide better self-shielding.
(ii) Temperature: Inversely correlated with star formation
through the Jeans mass (𝑀𝐽∝𝑇3/2).
The synthetic data include: realistic measurement uncertainties
(5–15 per cent); non-linear relationships (power laws, thresholds);
latent confounders (cloud mass affects both column density and Jeans
mass); and selection effects (biased toward detectable star-forming
regions).
8.4 Results
8.4.1 Phase 1: Exploratory Analysis
Astra identifies the key statistical properties of the dataset: five
continuous variables (column density, temperature, magnetic field,
velocity dispersion, star formation rate), each with non-Gaussian
distributions requiring non-parametric methods. The system detects
strong correlations between column density and star formation rate,
but also notes significant correlations between other variables, flag-
ging the need for multivariate analysis.
Initial feature importance ranking (random forest, 𝑅2 = 0.87):
(i) Column density: importance 0.42
(ii) Velocity dispersion: importance 0.23
(iii) Magnetic field: importance 0.19
(iv) Temperature: importance 0.16
8.4.2 Phase 2: Causal Discovery
The PC algorithm identifies a directed acyclic graph (DAG) with the
following edges:
• Jeans mass →Star Formation Rate (direct causal edge)
• Magnetic field →Star Formation Rate (direct causal edge)
• Virial parameter →Star Formation Rate (direct causal edge)
• Column density ↔Star Formation Rate (undirected; Astra
cannot determine causal direction from these data alone)
8.4.3 Phase 3: Distinguishing Cause from Proxy
The FCI algorithm (Zhang 2008), which accounts for latent con-
founders, refines the causal structure:
• Jeans mass →SFR: Confirmed as direct cause (conditional
independence tests show Jeans mass is not d-separated from SFR by
any other variable)
• Magnetic field →SFR: Confirmed as direct cause (suppressive)
• Virial parameter →SFR: Confirmed as direct cause
• Column density →SFR: Identified as having a latent common
cause (cloud mass, which is not directly measured). Astra correctly
identifies column density as a proxy rather than a direct cause.
This is the key result: Astra correctly distinguishes the three
genuine causal drivers from the correlated proxy variable, despite
column density having the highest univariate feature importance.
8.4.4 Phase 4: Hypothesis Generation
Based on the discovered causal structure, Astra generates four
ranked hypotheses:
(H1) Star formation is primarily controlled by gravitational in-
stability (Jeans mass criterion), with column density serving as an
observable proxy. Confidence: 0.89.
(H2) Magnetic fields provide a secondary suppression mecha-
nism, modulating the threshold for gravitational collapse. Confi-
dence: 0.76.
(H3) The virial parameter captures the combined effect of ther-
mal and non-thermal support, providing an independent threshold.
Confidence: 0.71.
(H4) The observed column density threshold arises from the cor-
relation between column density and Jeans mass, rather than from a
direct causal mechanism. Confidence: 0.83.
8.4.5 Phase 5: Intervention Analysis
To validate the causal claims, Astra performs do-calculus interven-
tions (Pearl 2009):
Intervention on Jeans mass: Setting do(𝑀𝐽= 𝑀𝐽,low) increases
predicted SFR by 2.3×, confirming the causal effect.
Intervention on column density: Setting do(𝑁𝐻= 𝑁𝐻,high)
has no significant effect on SFR when Jeans mass is held constant
(ΔSFR < 0.1 dex), confirming that column density is a proxy rather
than a cause.
Intervention on magnetic field: Setting do(𝐵= 𝐵high) reduces
predicted SFR by 1.7×, confirming the suppressive causal effect.
These intervention results are consistent with the ground truth
causal structure embedded in the synthetic data.
8.4.6 Validation Against Ground Truth
Comparing Astra’s discoveries with the known ground truth:
• Correct: All three causal drivers identified (Jeans mass, mag-
netic field, virial parameter) ✓
• Correct: Column density identified as proxy, not cause ✓
• Correct: Relative ordering of causal importance (Jeans mass >
magnetic field > virial parameter) ✓
• Correct: Magnetic field identified as suppressive rather than
enhancing ✓
• Partially correct: Temperature identified as correlated but As-
tra did not fully resolve its relationship to Jeans mass (they are
connected through 𝑀𝐽∝𝑇3/2)
RASTI 000, 000–000 (2026)
ASTRA: Autonomous Scientific Discovery in Astrophysics
17
Jeans
Mass
Magnetic
Field
Virial
Parameter
Column
Density
SFR
Cloud
Mass
Direct causal link
Latent-confounder path
Latent variable
Figure 11. Causal structure discovered by Astra in knowledge isolation mode. Solid arrows indicate direct causal relationships; the dashed arrow from column
density to SFR indicates a relationship mediated by a latent confounder (cloud mass). Astra correctly identifies the three genuine causal drivers (Jeans mass,
magnetic field, virial parameter) and distinguishes column density as a proxy.
RASTI 000, 000–000 (2026)
18
White
8.4.7 Testable Predictions
Astra generates four testable predictions for future observational
validation:
(P1) Jeans mass prediction: Molecular clouds with mass-to-
Jeans-mass ratios exceeding 2.0 should show star formation activity
regardless of column density. Test: Measure Jeans masses in a sample
of star-forming and non-star-forming clouds and compare the mass
ratio distributions.
(P2) Magnetic suppression prediction: Star-forming regions
with magnetic field strengths above 50 𝜇G should show suppressed
star formation efficiency compared to regions with weaker fields at
the same column density. Test: Zeeman measurements of magnetic
fields in matched samples of star-forming regions.
(P3) Column density proxy prediction: The column density
threshold for star formation should vary systematically with cloud
temperature: warmer clouds should require higher column densities.
Test: Compare column density thresholds across clouds with different
temperature distributions.
(P4) Virial parameter prediction: Clouds with virial parameters
𝛼vir < 1 should show higher star formation efficiencies than clouds
with 𝛼vir > 2, independent of column density. Test: Compare star
formation efficiencies in virially bound vs. unbound clouds.
These predictions are generated by Astra based on the discovered
causal structure. They are consistent with current theoretical under-
standing but have not been systematically tested observationally.
8.5 Physical Interpretation
This test case demonstrates that Astra can discover genuine causal
structure from data alone, without relying on encoded domain knowl-
edge. The key achievements are:
• Correct causal identification: All three causal drivers identi-
fied, in the correct relative ordering
• Proxy detection: Column density correctly identified as a proxy
rather than a cause, despite having the highest univariate feature
importance
• Intervention validation: Do-calculus interventions confirm the
causal claims against the known ground truth
• Prediction generation: Four testable predictions generated that
are consistent with current theory and amenable to observational
testing
The discovery that column density is a proxy rather than a direct
cause is particularly significant: in many ML-based analyses, the
variable with the highest feature importance would be treated as the
primary driver. Astra’s causal reasoning module goes beyond corre-
lation to identify the true causal structure, demonstrating a capability
that purely statistical or ML-based approaches cannot match.
8.6 Limitations and Qualifications
Synthetic data: This test used synthetic data with known ground
truth. While this enables validation that Astra discovered the cor-
rect causal structure, real molecular cloud data may have additional
complexities not captured in the synthetic dataset.
Predictions require validation: The four testable predictions re-
quire observational validation. Dedicated observational programs
measuring Jeans masses, magnetic fields, and virial parameters
across large samples of molecular clouds are needed to test these
predictions.
Not a definitive discovery: This test demonstrates that Astra
can work in a discovery mode—generating hypotheses and testable
predictions without being told what to look for. It does not claim
to have resolved the star formation threshold question. Definitive
scientific discovery requires collaboration with domain experts and
observational validation.
9 LIVE SYSTEM VALIDATION
Beyond the controlled test cases above, Astra has been deployed on
live astronomical datasets drawn from public archives, producing re-
sults that independently validate the framework’s capabilities on real-
world data at scale. Across six deployments, the system processed
more than 12 000 individual objects from four independent archives
(NASA Exoplanet Archive, Pantheon+, SDSS, Gaia EDR3). In each
case, Astra operated without prior guidance on what relationships to
seek; the system ingested the data, autonomously identified patterns,
applied causal and physical reasoning, and returned interpretations
that we compare with established results.
9.1 Kepler’s Third Law Recovery
Astra analysed 2 839 confirmed exoplanets from the NASA Ex-
oplanet Archive with measured orbital periods, semi-major axes,
and host-star masses. Operating in discovery mode, the system au-
tonomously identified a power-law relationship between orbital pe-
riod 𝑃and semi-major axis 𝑎, recovering the multivariate fit
log 𝑃= 1.497 log 𝑎−0.474 log 𝑀★,
(3)
with a coefficient of determination 𝑅2 = 0.9982. The semi-major
axis exponent of 1.497 is within 0.2 per cent of the Keplerian value
of 3/2, and the stellar-mass exponent of −0.474 is within 5.2 per cent
of the theoretical −1/2. This multivariate form captures the stellar-
mass dependence predicted by Newton’s generalization of Kepler’s
law (𝑃2 = 4𝜋2𝑎3/(𝐺𝑀★)), recovering a tighter fit than the univariate
𝑃2 ∝𝑎3 relation. The dimensional analysis module independently
validated the result by confirming consistency with Newtonian grav-
ity. This demonstrates Astra’s ability to rediscover fundamental
physical laws directly from observational data, including the identi-
fication of relevant controlling variables.
9.2 Accelerating Expansion (Dark Energy Signature)
From 1 701 Type Ia supernovae in the Pantheon+ compilation (Brout
et al. 2022), Astra fitted a distance modulus–redshift relation
𝜇= 5.33 log10(𝑧) + 24.42,
(4)
with 𝜒2/dof = 0.64, indicating an excellent fit. At redshifts 𝑧> 0.5,
the measured luminosity distances systematically exceed the pre-
dictions of an empty (Milne) universe, recovering the observational
signature of cosmic acceleration first reported by Riess et al. (1998)
and Perlmutter et al. (1999). Astra flagged this deviation as statis-
tically significant and generated the physical interpretation that an
additional energy component (consistent with dark energy or a cos-
mological constant) is required. This test validates the framework’s
ability to identify subtle systematic trends in noisy data and connect
them to fundamental physics.
RASTI 000, 000–000 (2026)
ASTRA: Autonomous Scientific Discovery in Astrophysics
19
9.3 Galaxy Colour Bimodality
Analysis of 2 000 SDSS galaxies revealed a bimodal distribution
in rest-frame 𝑢−𝑔colour, with GMM-fitted peaks at 𝑢−𝑔= 1.44
(blue cloud) and 𝑢−𝑔= 1.92 (red sequence), consistent with the
colour separation reported by Strateva et al. (2001). Astra iden-
tified the bimodality autonomously, correctly interpreting it as re-
flecting two distinct stellar-population histories: ongoing star forma-
tion in blue-cloud galaxies and quenched, passively evolving stellar
populations in the red sequence. The blue fraction declines from
∼50 per cent at low stellar masses (log 𝑀★/𝑀⊙≲10) to ∼10 per cent
at high masses (log 𝑀★/𝑀⊙≳11), reflecting the well-known mass-
dependent quenching of star formation (Peng et al. 2010). This re-
sult validates Astra’s unsupervised pattern recognition on complex,
multi-dimensional datasets.
9.4 Confounder Detection
As part of the galaxy colour analysis, Astra’s causal reasoning
module performed automated confounder detection on the SDSS
galaxy sample. The system identified 𝑢-band apparent magnitude as
the strongest confounder influencing the colour–mass relationship,
with a measured bias of 0.2351. This is physically expected: 𝑢-band
flux is sensitive to both recent star formation (which drives blue
colours) and distance (which affects apparent magnitude at fixed
luminosity), making it a confounding variable in any analysis that
does not explicitly control for survey depth. The automated detection
of this confounder demonstrates Astra’s ability to identify variables
that could bias scientific conclusions if left uncontrolled.
9.5 HR Diagram and the Main Sequence
Using 4 984 stars from Gaia Early Data Release 3, Astra recov-
ered the main-sequence relationship 𝑀𝐺= 3.66 × (𝐺BP −𝐺RP)
with a Pearson correlation 𝑟= 0.90 (𝑝< 10−100). The physics en-
gine provided an interpretation via the Stefan–Boltzmann law: more
luminous stars have higher effective temperatures, producing bluer
colours and brighter absolute magnitudes. By recovering this text-
book relationship from raw photometric data, Astra demonstrates
that its statistical and physical reasoning modules operate correctly
on large stellar samples.
9.6 Causal Direction Discovery
Applying the PC and FCI (Zhang 2008) causal discovery algorithms
to a combined stellar–galaxy dataset, Astra correctly identified red-
shift as a cause of observed colour (cosmological reddening), rather
than the reverse. This is a non-trivial result: in purely correlational
analyses, redshift and colour are symmetric, but causal algorithms
break this symmetry by exploiting conditional independence struc-
ture. Astra’s correct recovery of the causal direction—cosmological
effects driving observed photometric properties, not the reverse—
validates the causal reasoning module on real multi-source data.
9.7 Galaxy Survey Discovery Mode
As an additional deployment, Astra was applied in discovery
mode to a realistic galaxy survey of 3 000 galaxies with proper-
ties drawn from SDSS scaling relations (Elbaz et al. 2007; Mannucci
et al. 2010). Operating without prior hypotheses, Astra recovered:
(i) the star-forming main sequence (log SFR = 0.59 log 𝑀∗−5.45,
𝑟2 = 0.72); (ii) the mass–metallicity relation; and (iii) identified
150 outlier galaxies (5 per cent) warranting follow-up investiga-
tion through multi-dimensional anomaly detection. This demon-
strates Astra’s capacity for automated pattern discovery and triage
in survey-scale datasets. Full scripts and results are available in the
online supplementary material (Example 6).
These six live-data results, obtained without manual tuning or
domain-specific guidance, demonstrate that Astra generalises be-
yond its controlled test cases. The recovered relationships span clas-
sical mechanics (Kepler’s law), cosmology (dark energy), galaxy
evolution (colour bimodality and survey-scale discovery), stellar as-
trophysics (HR diagram), and causal inference (redshift–colour di-
rection), collectively exercising the full breadth of the framework’s
analytical capabilities. (Confounder detection in Section 9.4 is pre-
sented as a sub-analysis of the galaxy colour deployment rather than
as an independent deployment.)
10 CROSS-DOMAIN SCIENTIFIC VALIDATION
A critical test for any general-purpose analytical framework is
whether its capabilities transfer beyond its original domain. To
evaluate this, we deployed Astra on publicly available datasets
from three non-astrophysical domains—economics, climate science,
and epidemiology—and performed a cross-domain synthesis linking
variables across these fields. In each case, Astra operated with-
out domain-specific guidance: the system ingested the data, au-
tonomously identified patterns, applied its causal and statistical rea-
soning modules, and generated hypotheses that we compare with
established results.
All data used in this section are drawn from public archives: the
World Bank Open Data repository (World Bank 2024), NASA God-
dard Institute for Space Studies (GISS) global temperature records
(Hansen et al. 2010), and the NOAA Mauna Loa CO2 time series
(NOAA Global Monitoring Laboratory 2024).
10.1 Economics: World Bank Macroeconomic Indicators
Astra analysed macroeconomic indicators for 217 countries from
the World Bank Open Data repository (World Bank 2024), span-
ning 1960–2023 and covering GDP, unemployment, trade balance,
inflation, government debt, income inequality (Gini coefficient), and
related variables. Operating in discovery mode, the system generated
10 hypotheses and tested each against the data.
Validated hypotheses (9/10):
(i) Okun’s Law: Astra recovers a negative relationship between
GDP growth and unemployment change, consistent with the em-
pirical regularity reported by Okun (1962). The estimated coeffi-
cient (−1.8 per cent unemployment per 1 per cent GDP shortfall) falls
within the range reported in the literature.
(ii) Trade–GDP correlation: Trade openness (exports + imports
as a fraction of GDP) is positively correlated with GDP per capita
(𝑟= 0.41, 𝑝< 10−5), consistent with standard growth models.
(iii) Gini inequality persistence: Income inequality exhibits
strong temporal persistence (𝑟= 0.92 at 5-year lag), consistent with
structural theories of inequality.
(iv) PPP convergence: Purchasing power parity shows con-
vergence over decadal time-scales, consistent with the Balassa–
Samuelson effect.
(v) GDP mean-reversion: GDP growth rates exhibit mean-
reversion on 5–10 year time-scales, consistent with business cycle
theory.
RASTI 000, 000–000 (2026)
20
White
(vi) Reinhart–Rogoff debt threshold: Astra identifies a weakly
negative relationship between government debt-to-GDP ratio and
growth above the ∼90 per cent threshold reported by Reinhart &
Rogoff (2010), though the effect is not statistically robust (𝑝= 0.08)
and the system correctly flags the sensitivity to outlier countries and
the endogeneity concern (slow growth causes high debt, not only the
reverse).
(vii) Export diversification: Economies with more diversified
export baskets show lower GDP volatility (𝑟= −0.38, 𝑝< 0.001).
(viii) Inflation persistence: Inflation rates exhibit strong autocor-
relation (𝑟= 0.78 at 1-year lag), consistent with adaptive expectations
models.
(ix) Finance–growth nexus: Financial sector depth (domestic
credit to private sector as a fraction of GDP) is positively associ-
ated with GDP per capita (𝑟= 0.52, 𝑝< 10−8), though the causal
direction remains ambiguous.
Failed hypothesis (1/10):
(x) Phillips Curve: Astra tested for a negative relationship be-
tween unemployment and inflation, as originally reported by Phillips
(1958). The system found no statistically significant relationship in
the post-1990 cross-country data (𝑟= −0.03, 𝑝= 0.62). This is con-
sistent with the well-documented breakdown of the simple Phillips
Curve in modern macroeconomic data and demonstrates that Astra
correctly identifies non-relationships rather than forcing spurious
patterns.
The Phillips Curve failure is a particularly important result: it
demonstrates that Astra does not simply confirm every hypothesis
it generates. The system’s ability to identify relationships that do not
hold in the data is as scientifically valuable as its ability to identify
those that do.
10.2 Climate Science: NASA GISS and NOAA Data
Astra analysed global mean surface temperature anomalies from
NASA GISS (Hansen et al. 2010) and atmospheric CO2 concen-
trations from the NOAA Mauna Loa Observatory (NOAA Global
Monitoring Laboratory 2024), covering the period 1880–2023 (tem-
perature) and 1958–2023 (CO2).
Validated hypotheses (4/5):
(i) CO2–temperature correlation: Astra identifies a strong
positive correlation between atmospheric CO2 concentration and
global mean temperature anomaly (𝑅2 = 0.936 over the 1958–2023
overlap period). The system correctly notes that correlation does
not establish causation but flags the temporal precedence of CO2
increases as suggestive of a causal relationship.
(ii) Warming acceleration: The rate of warming post-1990
(0.20 ◦C decade−1) is 67 per cent faster than the pre-1990 rate
(0.12 ◦C decade−1), consistent with accelerating radiative forcing
from greenhouse gas accumulation.
(iii) CO2 growth acceleration: The annual rate of CO2 increase
has itself accelerated: the mean annual increment was ∼1.0 ppm yr−1
in the 1960s, rising to ∼2.4 ppm yr−1 in the 2010s, consistent with
increasing anthropogenic emissions.
(iv) Decadal warming trend: Each successive decade since the
1970s has been warmer than the preceding one, a pattern that Astra
identifies as statistically significant at the 𝑝< 0.001 level using a
non-parametric trend test.
Inconclusive hypothesis (1/5): The system tested for an El Niño–
Southern Oscillation (ENSO) modulation signal in the temperature
residuals after removing the long-term trend. While periodic struc-
ture was detected, Astra could not establish a statistically robust
ENSO signal with the available temporal resolution, and correctly
flagged the result as inconclusive.
10.3 Epidemiology: World Bank Health Indicators
Astra analysed health and development indicators for 217 countries
from the World Bank (World Bank 2024), including life expectancy,
infant mortality, GDP per capita, health expenditure, vaccination
coverage, and maternal mortality.
Validated hypotheses (5/5):
(i) Infant mortality vs. GDP: Astra identifies a strong negative
relationship between infant mortality rate and GDP per capita (𝑅2 =
0.587), with a logarithmic functional form providing the best fit—
consistent with diminishing marginal returns of wealth on health
outcomes.
(ii) Preston Curve: Life expectancy increases with GDP per
capita following a concave (logarithmic) relationship (𝑅2 = 0.686),
recovering the classic Preston Curve (Preston 1975). The system cor-
rectly notes the flattening at high GDP, indicating saturation of the
wealth–health relationship.
(iii) Life expectancy vs. health spending: Health expenditure per
capita is positively associated with life expectancy (𝑟= 0.62, 𝑝<
10−12), though Astra’s causal module flags the likely bidirectional
relationship (wealthier countries both spend more on health and have
longer life expectancies, with GDP as a common cause).
(iv) DPT vaccination coverage: DPT3 vaccination coverage is
negatively correlated with infant mortality (𝑟= −0.65, 𝑝< 10−15),
consistent with the established effectiveness of childhood vaccination
programmes.
(v) Maternal mortality: Maternal mortality ratio is strongly neg-
atively associated with GDP per capita (𝑟= −0.58, 𝑝< 10−10) and
with skilled birth attendance (𝑟= −0.71, 𝑝< 10−18), consistent with
the role of healthcare infrastructure in reducing maternal deaths.
10.4 Cross-Domain Synthesis
To test whether Astra can identify meaningful relationships across
domains, we merged the economics, climate, and health datasets at
the country–year level and applied the full analytical pipeline. The
system generated 8 cross-domain hypotheses and applied Benjamini–
Hochberg false discovery rate (FDR) correction (Benjamini &
Hochberg 1995) at 𝑞= 0.05 to account for multiple testing.
Validated after FDR correction (5/8):
(i) GDP–CO2 coupling: National GDP is positively correlated
with per-capita CO2 emissions (𝑟= 0.71, 𝑝adj < 10−10), reflecting
the carbon intensity of economic activity.
(ii) Life expectancy–CO2: Countries with higher CO2 emissions
per capita tend to have higher life expectancies (𝑟= 0.58, 𝑝adj <
10−6). Astra correctly identifies this as a confounded relationship
(GDP drives both) rather than a causal link from emissions to health.
(iii) Wealth–Health Nexus: GDP per capita, health expenditure,
and life expectancy form a strongly coupled triad (𝑅2 = 0.700 for the
three-variable model), which Astra identifies as the strongest cross-
domain relationship. The causal module suggests GDP →health
expenditure →life expectancy as the primary causal pathway, with
direct GDP →life expectancy effects mediated by nutrition, sanita-
tion, and education.
RASTI 000, 000–000 (2026)
ASTRA: Autonomous Scientific Discovery in Astrophysics
21
(iv) Urbanization–CO2: Urbanization rate is positively corre-
lated with per-capita CO2 emissions (𝑟= 0.49, 𝑝adj < 10−4), con-
sistent with higher energy consumption in urban settings.
(v) Renewables–GDP paradox: Renewable energy share is neg-
atively correlated with GDP per capita (𝑟= −0.42, 𝑝adj < 0.001).
Astra correctly interprets this counter-intuitive finding: poorer
countries rely more heavily on traditional biomass (counted as re-
newable), while wealthier countries have historically derived more
energy from fossil fuels. The system flags this as an example where
naïve interpretation of a correlation would be misleading.
Lost after FDR correction (3/8): Three hypotheses (education–
emissions coupling, democracy–health association, and trade
openness–environmental quality) did not survive FDR correction
at 𝑞= 0.05. These marginal relationships may be real but require
larger samples or more careful confound control to establish.
The application of FDR correction is methodologically impor-
tant: without it, the cross-domain analysis would have reported 8/8
validated hypotheses, a misleadingly optimistic result. Astra’s au-
tomatic application of FDR correction demonstrates responsible sta-
tistical practice.
10.5 Negative Results and Epistemic Honesty
The cross-domain validation provides several examples of Astra
correctly identifying non-relationships or qualifying ambiguous find-
ings:
Phillips Curve failure: As discussed in Section 10.1, Astra
found no statistically significant unemployment–inflation trade-off
in post-1990 data (𝑟= −0.03, 𝑝= 0.62), consistent with the well-
documented instability of the Phillips Curve.
FDR attrition: Of 8 cross-domain hypotheses, 3 were lost after
FDR correction. Astra reports these as “not validated” rather than
attempting to salvage them through post-hoc analysis.
Confound identification: In 3 of the 5 validated cross-domain
hypotheses, Astra’s causal module identified confounding variables
(primarily GDP as a common cause) and flagged the correlations as
potentially non-causal.
Reinhart–Rogoff qualification: The debt–growth relationship
was validated only with substantial caveats (𝑝= 0.08, sensitivity to
outliers, endogeneity concerns), demonstrating nuanced rather than
binary hypothesis assessment.
These negative and qualified results are as important as the posi-
tive validations. A system that confirms every hypothesis it generates
would be useless; Astra’s ability to distinguish signal from noise,
and to qualify ambiguous findings, is essential for its role as a scien-
tific tool.
10.6 Summary of Cross-Domain Results
Table 2 provides a comprehensive listing of all hypotheses tested
across the five scientific domains.
∗Reinhart–Rogoff threshold validated with substantial caveats: 𝑝=
0.08, sensitive to outliers, endogeneity concerns flagged.
In total, Astra tested approximately 43 hypotheses across five
scientific domains, validating 38 (including 1 with caveats), fail-
ing 1 (Phillips Curve), finding 1 inconclusive (ENSO), and losing
3 after FDR correction. This 88 per cent validation rate—achieved
without domain-specific tuning and across disciplines as diverse as
astrophysics, macroeconomics, and epidemiology—provides strong
evidence that Astra’s analytical capabilities generalize beyond its
original astrophysical domain.
11 DISCUSSION
11.1 What ASTRA Demonstrates
The six controlled astrophysical test cases, six live deployments,
cross-domain validation, and stigmergic swarm intelligence col-
lectively analyse data drawn from more than a dozen independent
sources spanning five scientific domains, with 397 total discoveries
and 38 validated hypotheses. The astrophysical analyses process more
than 27 430 data points from nine sources, while the cross-domain
validation draws on national-level panel data for 217 countries over
six decades (World Bank), global temperature records spanning 143
years (NASA GISS), and atmospheric CO2 measurements covering
65 years (NOAA Mauna Loa). Rather than repeating individual re-
sults, we reflect here on what these collective demonstrations reveal
about Astra’s strengths and limitations.
The integration advantage is most concretely demonstrated in Test
Case 5 (Bayesian Model Selection), where physical motivation (the
virial theorem predicting a power law) and statistical evidence (Bayes
factors strongly favouring power-law and logarithmic models over
linear alternatives) jointly inform model interpretation within a sin-
gle automated workflow. This joint consideration of statistical evi-
dence and physical constraints—without requiring manual synthesis
of separate analyses—represents the core value of the integrated
approach.
Test Case 6 demonstrates a distinct capability: discovery-mode
operation beyond knowledge retrieval. By operating in “knowledge
isolation mode” on a synthetic dataset with embedded causal struc-
ture, Astra discovered the correct causal drivers, identified column
density as a proxy rather than direct cause, and generated testable
predictions. This addresses a key question: can Astra go beyond
“correct recovery of known results” to demonstrate genuine discov-
ery capability? The results suggest that Astra’s architecture sup-
ports discovery-mode operation, though definitive scientific discov-
ery requires collaboration with domain experts and observational
validation.
Four Modes of Evidence:
(i) Validation mode (Tests 1–5): Astra analyses real data to
recover known astrophysical relationships, validating the integrated
framework.
(ii) Discovery mode (Test 6): Astra analyses data in knowledge
isolation mode to discover patterns without being told what to look
for, generating hypotheses and testable predictions.
(iii) Live deployment (Section 9): Astra operates on archival
data without manual guidance, independently recovering fundamen-
tal physics.
(iv) Cross-domain generalization (Section 10): Astra oper-
ates on non-astrophysical data, recovering established relationships
and correctly identifying non-relationships—demonstrating that the
framework’s capabilities are not domain-specific artefacts.
11.2 What ASTRA Genuinely Contributes
A fair question is whether Astra merely confirms what is already
known. The answer is nuanced.
The live validation results, while impressive for a fully automated
system, recover well-established physics. Their value lies in demon-
strating that Astra’s integrated pipeline produces correct, quan-
titatively precise results on real data without human intervention.
That an automated system can ingest raw archival data and arrive at
𝑅2 = 0.9982 for Kepler’s law or 𝜒2/dof = 0.64 for the Hubble dia-
RASTI 000, 000–000 (2026)
22
White
Table 2. Summary of all hypotheses tested across five scientific domains. “Validated” indicates the hypothesis is supported by the data at the stated significance
level; “Failed” indicates the hypothesis is not supported; “FDR lost” indicates the hypothesis did not survive false discovery rate correction.
Domain
Hypothesis
Key Statistic
Valid?
Data Source
Astrophysics — Controlled Test Cases
Astrophysics
Filament universal width
0.098 ± 0.019 pc
✓
Herschel
Astrophysics
Virial scaling relation
𝑟= 0.988, 𝑝< 10−18
✓
Herschel
Astrophysics
Multi-𝜆cross-match
60/370 secure matches
✓
CDFS
Astrophysics
Mass–metallicity relation
𝑟= 0.68, 𝑝< 10−27
✓
SDSS
Astrophysics
Environmental quenching
ΔSFR ≈−0.3 dex
✓
SDSS
Astrophysics
Causal structure (Gaia)
Correct DAG recovery
✓
Gaia DR2
Astrophysics
Bayesian model selection
BF = 1.2 (PL vs. log)
✓
Herschel
Astrophysics
SF causal drivers (synthetic)
3/3 drivers found
✓
Synthetic
Astrophysics
Column density as proxy
Proxy confirmed
✓
Synthetic
Astrophysics — Live Deployments
Astrophysics
Kepler’s third law
𝑅2 = 0.9982
✓
NASA Exo. Archive
Astrophysics
Dark energy signature
𝜒2/dof = 0.64
✓
Pantheon+
Astrophysics
Galaxy colour bimodality
Peaks: 1.44, 1.92
✓
SDSS
Astrophysics
𝑢-band confounder
Bias = 0.2351
✓
SDSS
Astrophysics
HR main sequence
𝑟= 0.90, 𝑝< 10−100
✓
Gaia EDR3
Astrophysics
Causal direction (𝑧→colour)
Correct orientation
✓
Gaia+SDSS
Economics
Economics
Okun’s Law
−1.8%/1% GDP
✓
World Bank
Economics
Trade–GDP correlation
𝑟= 0.41, 𝑝< 10−5
✓
World Bank
Economics
Gini persistence
𝑟= 0.92 (5-yr lag)
✓
World Bank
Economics
PPP convergence
Decadal convergence
✓
World Bank
Economics
GDP mean-reversion
5–10 yr cycle
✓
World Bank
Economics
Reinhart–Rogoff threshold
𝑝= 0.08 (qualified)
✓∗
World Bank
Economics
Export diversification
𝑟= −0.38, 𝑝< 0.001
✓
World Bank
Economics
Inflation persistence
𝑟= 0.78 (1-yr lag)
✓
World Bank
Economics
Finance–growth nexus
𝑟= 0.52, 𝑝< 10−8
✓
World Bank
Economics
Phillips Curve
𝑟= −0.03, 𝑝= 0.62
×
World Bank
Climate Science
Climate
CO2–temp. correlation
𝑅2 = 0.936
✓
GISS + NOAA
Climate
Warming acceleration
67% faster post-1990
✓
GISS
Climate
CO2 growth acceleration
1.0 →2.4 ppm yr−1
✓
NOAA
Climate
Decadal warming trend
𝑝< 0.001
✓
GISS
Climate
ENSO modulation
Inconclusive
–
GISS
Epidemiology
Epidemiology
Infant mortality vs. GDP
𝑅2 = 0.587
✓
World Bank
Epidemiology
Preston Curve
𝑅2 = 0.686
✓
World Bank
Epidemiology
Life exp. vs. health spending
𝑟= 0.62, 𝑝< 10−12
✓
World Bank
Epidemiology
DPT vaccination effect
𝑟= −0.65, 𝑝< 10−15
✓
World Bank
Epidemiology
Maternal mortality
𝑟= −0.71, 𝑝< 10−18
✓
World Bank
Cross-Domain Synthesis (after FDR correction)
Cross-domain
GDP–CO2 coupling
𝑟= 0.71, 𝑝adj < 10−10
✓
WB + NOAA
Cross-domain
Life exp.–CO2 (confounded)
𝑟= 0.58, 𝑝adj < 10−6
✓
WB + NOAA
Cross-domain
Wealth–Health Nexus
𝑅2 = 0.700
✓
World Bank
Cross-domain
Urbanization–CO2
𝑟= 0.49, 𝑝adj < 10−4
✓
WB + NOAA
Cross-domain
Renewables–GDP paradox
𝑟= −0.42, 𝑝adj < 0.001
✓
World Bank
Cross-domain
Education–emissions
Not significant after FDR
FDR lost
WB + NOAA
Cross-domain
Democracy–health
Not significant after FDR
FDR lost
World Bank
Cross-domain
Trade–environment
Not significant after FDR
FDR lost
World Bank
gram is a non-trivial engineering and methodological achievement,
even though the underlying physics is textbook material.
The cross-domain results extend this argument: recovering Okun’s
Law, the Preston Curve, and CO2–temperature coupling using the
same pipeline that recovers Kepler’s law demonstrates that Astra’s
capabilities are genuinely domain-general. The Phillips Curve failure
and FDR attrition provide further evidence that the system produces
honest, calibrated results rather than indiscriminate confirmations.
Astra’s genuine scientific contribution lies in four areas. First, the
integration itself: by chaining dimensional analysis, causal inference,
and Bayesian model selection into a single workflow, Astra elim-
inates inconsistencies that arise when scientists manually combine
outputs from separate tools—particularly in uncertainty propagation
and physical validation. Second, the causal reasoning capability:
Test Case 6 demonstrates that Astra can distinguish proxy vari-
ables from causal drivers, a distinction that purely correlational or
ML-based approaches cannot make. Third, the knowledge isolation
mode: by disabling access to encoded domain knowledge, Astra
RASTI 000, 000–000 (2026)
ASTRA: Autonomous Scientific Discovery in Astrophysics
23
provides a controlled test of whether patterns in data are discov-
erable from first principles, an approach that could be applied to
domains where the ground truth is genuinely unknown. Fourth, the
cross-domain generalization: the same analytical pipeline that re-
covers astrophysical scaling relations also recovers macroeconomic
regularities, climate trends, and epidemiological relationships, with
appropriate epistemic qualifications.
11.3 Cross-Domain Generalization
The cross-domain validation (Section 10) addresses a fundamen-
tal question: is the framework genuinely general-purpose, or are its
capabilities specific to the astrophysical domain for which it was
developed?
Three aspects of the results support generality. First, the same an-
alytical modules—dimensional analysis, causal inference, Bayesian
model selection, pattern recognition—that recover astrophysical re-
lationships also recover economic, climatic, and epidemiological re-
lationships, without domain-specific modifications. Second, Astra’s
epistemic qualifications transfer across domains: the system correctly
identifies GDP as a confound in the life expectancy–CO2 corre-
lation, flags the Reinhart–Rogoff threshold as sensitive to outliers
and endogeneity, and applies FDR correction to the cross-domain
synthesis. Third, the negative results—the Phillips Curve failure,
the ENSO inconclusive result, and the three FDR-lost cross-domain
hypotheses—demonstrate that Astra does not indiscriminately con-
firm hypotheses.
These results suggest that Astra’s architecture is genuinely
domain-agnostic at the analytical level. The core capabilities—
pattern discovery, causal inference, hypothesis testing with multiple
testing correction, confound identification—are domain-general by
construction.
Caveats: The cross-domain validation uses well-established re-
lationships as benchmarks. Astra has not been tested on genuinely
open questions in non-astrophysical domains. The domain knowledge
systems (MORK ontology, 75 specialized modules) are astrophysics-
specific; extending to production-quality analysis in other domains
would require developing analogous domain knowledge. The cross-
domain results demonstrate that the analytical architecture gener-
alizes, not that Astra is ready for deployment as an economics or
climate science tool.
11.4 Cognitive Architecture and Multi-Agent Reasoning
The cognitive architecture (Section 2.8), multi-agent debate system
(Section 2.9), theory framework (Section 2.10), and autonomous
research agenda (Section 2.11) represent a significant extension of
Astra’s capabilities beyond the core analytical pipeline validated
in the test cases. These components are designed to address limi-
tations of purely pipeline-based scientific analysis: the knowledge
graph maintains persistent context across analyses; neuro-symbolic
integration provides formal verification of statistically discovered
patterns; multi-agent debate reduces confirmation bias through struc-
tured adversarial evaluation; and the theory framework supports the
progression from individual validated hypotheses to broader theoret-
ical understanding.
We emphasize that these components have not been independently
validated through controlled experiments in this paper. The test case
results reported in Sections 3–8 and the live deployments in Sec-
tion 9 exercise the core analytical modules (dimensional analysis,
causal inference, Bayesian model selection) rather than the cogni-
tive architecture or multi-agent debate system in isolation. Rigorous
ablation studies—comparing analytical performance with and with-
out the cognitive architecture, knowledge graph, and multi-agent
debate—are required to quantify their individual contributions and
are planned for future work.
The autonomous research agenda, with its information-theoretic
curiosity metrics and human approval gates, provides a principled
framework for directing computational effort toward scientifically
meaningful questions. However, the effectiveness of curiosity-driven
exploration relative to human-directed analysis remains an open em-
pirical question.
11.5 Positioning Relative to Other Approaches
Astra occupies a distinct position in the computational astronomy
ecosystem by integrating multiple analysis types within a unified
framework.
Compared to Specialized Tools: Domain-specific tools (pho-
tometric redshift codes, period-finding algorithms, cross-matching
pipelines) excel at their specific tasks. Astra does not aim to re-
place them but to provide integrated workflows that combine multi-
ple analysis types with consistent uncertainty handling and physical
validation.
Compared to Manual Pipelines: Astronomers routinely combine
multiple tools manually, creating opportunities for inconsistent un-
certainty treatment and reproducibility challenges. Astra addresses
these by providing automated workflows with integrated validation.
Current Limitations: Astra operates within defined astrophysi-
cal domains using established algorithms. The system assists scien-
tific reasoning rather than replacing domain expertise. The test cases
presented use small samples and should be understood as capability
demonstrations rather than production-scale analyses.
11.6 ASTRA’s Role in Scientific Discovery
A crucial question is: what role can Astra play in genuine scientific
discovery? We would not expect to give Astra one of the big con-
temporary problems—“resolve the nature of the Hubble Tension,”
“tell us what dark matter is,” “prove that we live in a holographic
universe”—and receive definitive answers in a computational Eu-
reka moment. These problems require deep physical insight, creative
hypothesis formation, and careful experimental design—capabilities
that remain fundamentally human.
However, Astra’s discovery architecture, used alongside an ex-
perienced astronomer, provides capabilities that go beyond those of
straightforward AI or machine learning. Test Case 6 demonstrates
that Astra can discover patterns in data without being told what to
look for (knowledge isolation mode), apply causal inference methods
that distinguish correlation from causation, generate competing hy-
potheses with quantitative rankings, and produce testable predictions
to guide future observations.
Astra’s role is to work alongside the experienced astronomer to
analyse data and facilitate genuine discovery. The human scientist
brings deep physical understanding, creative insight, and judgment
about which questions are worth asking. Astra brings automated
pattern discovery, causal reasoning, and systematic hypothesis eval-
uation. Together, they can pursue scientific questions more effectively
than either could alone.
This collaborative model—Astra as discovery assistant working
alongside domain experts—is the appropriate framing for AI-assisted
scientific discovery. The live dashboard (Section 2.6) operationalizes
this model by providing real-time intervention controls and align-
RASTI 000, 000–000 (2026)
24
White
ment monitoring, ensuring that the human operator retains mean-
ingful oversight throughout autonomous discovery cycles. The stig-
mergic swarm intelligence layer (Section 2.7) further enhances this
collaboration by autonomously balancing exploration of novel sci-
entific domains against exploitation of productive directions, guided
by biologically-calibrated parameters (Fig. 3) and validated through
A/B testing against unguided baselines. Claims that AI systems will
autonomously resolve major open questions overlook the essential
role of human physical insight and careful experimental design.
11.7 Limitations and Future Work
Current limitations include:
• Sample sizes: The controlled test cases use 24–1000 objects.
The live deployments reach larger scales (up to 4 984 stars), but
scaling to survey-scale datasets (106–109 objects) requires further
validation.
• Computational cost: Causal discovery scales as O(𝑝2) for 𝑝
variables, limiting applicability to high-dimensional problems.
• Prior dependence: Bayesian evidence computation requires
careful prior specification, and results can be prior-dependent.
• Domain knowledge: Astra’s pattern recognition retrieves en-
coded domain knowledge. Genuine novel discovery requires identi-
fying patterns not already in the knowledge base.
• Selection effects: Multi-wavelength cross-matching assump-
tions (Gaussian errors, uniform priors) may not hold in all regimes.
• Live validation scope: The live deployment results recover
well-established physics and validate the pipeline’s correctness, not
its ability to find genuinely new science.
• Cross-domain depth: The cross-domain validation uses well-
established benchmarks. Production-quality analysis in other do-
mains would require domain-specific knowledge modules analogous
to Astra’s astrophysical MORK ontology.
• Cognitive architecture: The cognitive architecture, multi-
agent debate, theory framework, and autonomous research agenda
(Sections 2.8–2.11) are operational but have not been independently
validated through ablation studies. Their individual contributions to
analytical quality remain to be quantified.
Astra is currently being applied to ongoing research on inter-
stellar medium filaments, where its dimensional analysis and causal
inference capabilities are being used to investigate filament stability
and fragmentation properties.
Future work should focus on: scaling to larger datasets; validation
on more scientifically challenging problems where the answer is not
known in advance; integration with time-domain surveys for real-
time analysis; extension to gravitational wave and neutrino multi-
messenger astronomy; applying knowledge-isolation discovery mode
to real datasets where causal structure is not known a priori; de-
veloping domain knowledge modules for non-astrophysical fields;
and rigorous evaluation of the stigmergic swarm intelligence layer
through controlled experiments comparing pheromone-guided and
unguided discovery on standardized benchmarks with sufficient sta-
tistical power.
12 CONCLUSION
We have presented Astra (Autonomous System for Scientific Dis-
covery in Astrophysics), an integrated framework for physics-aware
scientific analysis that unifies dimensional analysis, causal reason-
ing, Bayesian model selection, multi-wavelength data fusion, and
stigmergic swarm intelligence within a single reproducible pipeline.
Through six controlled astrophysical test cases, six live deployments
on archival data, and cross-domain validation across economics,
climate science, and epidemiology, we have demonstrated Astra’s
technical capabilities across 38 validated hypotheses in five scien-
tific domains, with a stigmergic swarm intelligence layer coordinat-
ing autonomous hypothesis exploration through biologically-inspired
agents (Fig. 3).
The controlled test cases validate Astra’s core analytical modules
on real observational data. The scaling relations analysis (Test 1) re-
covers the ∼0.1 pc filament width and virial scaling (𝑟= 0.988)
from 24 Herschel filaments; the multi-wavelength fusion (Test 2)
achieves Bayesian cross-matching in the CDFS with a <5 per cent
false match rate; and the pattern recognition (Test 3) identifies estab-
lished galaxy relationships including the mass–metallicity relation
and environmental quenching from 600 SDSS galaxies. The causal
inference demonstrator (Test 4) correctly recovers textbook causal
relationships from 1000 Gaia stars, and the Bayesian model selec-
tion (Test 5) demonstrates the automatic Occam’s razor, strongly
preferring power-law and logarithmic models over linear and broken
power-law alternatives.
The discovery-mode test (Test 6) provides the strongest evidence
of Astra’s analytical capabilities. Operating in knowledge isolation
mode on synthetic molecular cloud data, Astra correctly identified
all three causal drivers of star formation (Jeans mass, magnetic field,
virial parameter), distinguished column density as a proxy rather
than direct cause despite its highest univariate feature importance,
and generated four testable predictions validated through intervention
analysis.
Six live deployments on archival data independently recover es-
tablished physics without domain-specific guidance: Kepler’s third
law from 2 839 exoplanets (𝑅2 = 0.9982), the dark energy signa-
ture from 1 701 Type Ia supernovae (𝜒2/dof = 0.64), galaxy colour
bimodality (𝑢−𝑔peaks at 1.44 and 1.92), the HR diagram main se-
quence (𝑟= 0.90 from 4 984 Gaia stars), correct causal direction
for redshift–colour, and automated confounder detection. The cross-
domain validation extends these results beyond astrophysics: Astra
recovers 9/10 economic hypotheses (Okun’s Law, trade–GDP, and
seven others; Phillips Curve correctly identified as non-significant),
4/5 climate hypotheses (CO2–temperature 𝑅2 = 0.936), 5/5 epi-
demiological hypotheses (Preston Curve 𝑅2 = 0.686), and 5/8 cross-
domain syntheses surviving FDR correction.
These results establish four modes of evidence for Astra’s ca-
pabilities: validation of known results on real data, discovery-mode
operation under controlled conditions, live deployment at scale on
archival data, and cross-domain generalization beyond astrophysics.
While individual components use established algorithms, their in-
tegration within a single framework—coordinated by a cognitive
architecture with knowledge graph persistence, neuro-symbolic ver-
ification, and multi-agent hypothesis evaluation—enables analyses
that would otherwise require manual combination of multiple sep-
arate tools and pipelines. Astra is a tool to assist the astronomer,
not a replacement for domain expertise; definitive scientific discov-
ery requires collaboration with domain experts and observational
validation.
The complete source code, documentation, and reproducible anal-
ysis notebooks are available at https://github.com/Tilanthi/
ASTRA (White 2026).
RASTI 000, 000–000 (2026)
ASTRA: Autonomous Scientific Discovery in Astrophysics
25
ACKNOWLEDGEMENTS
This work uses data from Gaia DR2 and EDR3, Herschel Gould Belt
Survey, HST ACS, Chandra Deep Field South, SDSS, the NASA
Exoplanet Archive, and the Pantheon+ supernova compilation. The
cross-domain validation uses data from the World Bank Open Data
repository (https://data.worldbank.org), the NASA Goddard
Institute for Space Studies (GISS) Surface Temperature Analysis, and
the NOAA Global Monitoring Laboratory Mauna Loa CO2 record.
We acknowledge the use of community software tools including
causal-learn, dowhy, NumPy, SciPy, and scikit-learn.
The stigmergic swarm intelligence layer (Section 2.7) builds upon
foundational work on stigmergic intelligence and autonomous navi-
gation by Dey (2025) at OpenHub, Thailand. OpenHub served as a re-
search partner for this work, contributing to the development and test-
ing of ASTRA’s autonomous research capabilities through the Taurus
multi-agent orchestration platform (https://taurus.cloud). The
Taurus platform provided the computational infrastructure for AS-
TRA’s autonomous research cycles, enabling persistent multi-agent
coordination, scheduled discovery runs, and real-time hypothesis
validation.
AUTHOR CONTRIBUTIONS
GJW conceived the ASTRA project, designed the framework archi-
tecture including the V8.0 cognitive architecture and V9.0 multi-
agent system, led the scientific validation, and wrote the manuscript.
The ASTRA codebase was developed with contributions from Open-
Hub (Thailand), who also conducted independent review and testing
of the system—including the cognitive architecture, multi-agent de-
bate, theory framework, and autonomous research agenda—through
the Taurus research platform. Large language model assistance (An-
thropic Claude) was used in manuscript preparation, including initial
drafting, editing, and multiple rounds of simulated peer review. The
scientific content, analysis, and conclusions were designed, executed,
and verified by the author. All errors and omissions are the responsi-
bility of the author. The author declares no conflict of interest.
DATA AVAILABILITY
The complete Astra source code and analysis notebooks are avail-
able at https://github.com/Tilanthi/ASTRA. Six fully repro-
ducible worked examples with data generation scripts, analysis
code, and figure generation are provided in the online repository
(Example1–6/). All data used in this paper are publicly available
from the original survey archives as cited in the text. World Bank
data are available at https://data.worldbank.org; NASA GISS
temperature data at https://data.giss.nasa.gov/gistemp/;
NOAA Mauna Loa CO2 data at https://gml.noaa.gov/ccgg/
trends/.
REFERENCES
Abazajian K. N., Adelman-McCarthy J. K., Agüeros M. A., et al., 2009, ApJS,
182, 543
Alexander D. M., Bauer F. E., Brandt W. N., et al., 2003, AJ, 126, 539
André P., Men’shchikov A., Bontemps S.,Hennemann M., Motte F., Schneider
N., 2010, A&A, 518, L102
Arzoumanian D., André P., Didelon P., et al., 2011, A&A, 529, L6
Arzoumanian D., André P., Men’shchikov A., Könyves V., Schneider N.,
Motte F., 2019, A&A, 621, A114
Bauer F. E., Alexander D. M., Brandt W. N., Hornschemeier A. E., Garmire
G. P., Schneider D. P., 2004, AJ, 128, 2048
Benjamini Y., Hochberg Y., 1995, Journal of the Royal Statistical Society:
Series B, 57, 289
Brinchmann J., Charlot S., White S. D. M., Tremonti C., Kauffmann G.,
Heckman T., Kennicutt R., 2004, MNRAS, 351, 1151
Brout D., et al., 2022, ApJ, 938, 110
Buckingham E., 1914, Physical Review, 4, 345
Dey R., 2025, STAN: Stigmergic A* Navigation – Bringing Collective In-
telligence to Graph Pathfinding through Pheromone-based Optimization,
https://github.com/vbrltech/STAN
Dorigo M., Maniezzo V., Colorni A., 1996, IEEE Transactions on Systems,
Man, and Cybernetics, Part B, 26, 29
Dressler A., 1980, ApJ, 236, 351
Eadie G., Speagle J. S., Cisewski-Kehe J., Foreman-Mackey D., Hup-
penkothen D., 2023, RAS Techniques and Instruments, 2, 78
Elbaz D., et al., 2007, A&A, 468, 33
Gaia Collaboration Brown A. G. A., Vallenari A., Prusti T., de Bruĳne J.
H. J., Babusiaux C., Bailer-Jones C. A. L., 2018, A&A, 616, A1
Giacconi R., Zirm A., Wang J., Rosati P., Gilli R., Nonino M., Czoske O.,
2001, ApJ, 551, 624
Gordon D. M., 2010, Ant Encounters: Interaction Networks and Colony
Behavior. Princeton University Press, Princeton, NJ
Grassé P.-P., 1959, Insectes Sociaux, 6, 41
Hansen J., Ruedy R., Sato M., Lo K., 2010, Reviews of Geophysics, 48,
RG4004
Kocsis L., Szepesvári C., 2006, in Machine Learning: ECML 2006. Springer,
pp 282–293, doi:10.1007/11871842_29
Mannucci F., Cresci G., Poggianti B. M., Gavazzi G., Cucciati O., 2010,
MNRAS, 408, 2115
NOAA Global Monitoring Laboratory 2024, Trends in Atmospheric Carbon
Dioxide: Mauna Loa CO2 annual mean data, https://gml.noaa.gov/
ccgg/trends/
Okun A. M., 1962, Proceedings of the Business and Economic Statistics
Section, American Statistical Association, pp 98–104
Panopoulou G. V., Psarouli I., Taqi N., Andrews J. J., 2022, A&A, 657, L13
Pearl J., 2009, Causality: Models, Reasoning, and Inference, 2nd edn. Cam-
bridge University Press, Cambridge
Peng Y.-j., Lilly S. J., Kovač K., Bosz E., Carollo C. M., McGee S. L., Alonso
M. S., Tassis K., 2010, ApJ, 721, 193
Perlmutter S., Aldering G., Goldhaber G., et al., 1999, ApJ, 517, 565
Phillips A. W., 1958, Economica, 25, 283
Preston S. H., 1975, Population Studies, 29, 231
Reinhart C. M., Rogoff K. S., 2010, American Economic Review, 100, 573
Riess A. G., Filippenko A. V., Challis P., et al., 1998, AJ, 116, 1009
Schwarz G., 1978, Annals of Statistics, 6, 461
Spirtes P., Glymour C., Scheines R., 2000, Causation, Prediction, and Search,
2nd edn. MIT Press, Cambridge, MA
Spurio Mancini A., Docherty M. M., Price M. A., McEwen J. D., 2023, RAS
Techniques and Instruments, 2, 710
Strateva I., Ivezić Ž., Knapp G. R., Heckman T. M., Strauss M. A., Gunn J. E.,
Lupton R. H., 2001, AJ, 122, 1861
Sutherland W., Saunders W., 1992, MNRAS, 259, 413
Tremonti C. A., Heckman T. M., Kauffmann G., et al., 2004, ApJ, 613, 898
White G. J., 2026, ASTRA: Autonomous System for Scientific Discovery in
Astrophysics, https://github.com/Tilanthi/ASTRA
World Bank 2024, World Bank Open Data, https://data.worldbank.org
Zhang J., 2008, Artificial Intelligence, 172, 1873
RASTI 000, 000–000 (2026)
