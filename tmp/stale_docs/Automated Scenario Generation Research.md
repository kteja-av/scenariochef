# **Automated Scenario Generation — Phase 1: State-of-the-Art Literature Review, Architectural Failure Analysis, and Research Gap Map**

## **Part 1 — Executive Summary**

The validation of Autonomous Driving Systems (ADS) via scenario-based testing has transitioned from manual graphical design and parameter sweep scripts to automated, closed-loop synthesis pipelines1. Autonomous driving simulation architectures require precise alignment across natural language requirement parsing, intermediate domain representations, concrete file format compilations, map topological verification, physical simulation execution, safety observation, and closed-loop failure repair1. The Phase-1 capability-oriented framework presented in this review defines an architecture leveraging OpenSCENARIO for dynamic behavior representation, OpenDRIVE for static road network topologies, and esmini for lightweight deterministic simulation1.  
Literature reveals a clear structural division between mature engineering solutions, emerging hybrid frameworks, and genuinely open research problems in scenario generation architectures:

> 1. **Mature Engineering Domains**: XML schema validation against standard XSD definitions, deterministic OpenSCENARIO parsing, OpenDRIVE coordinate transformations, kinematic metric calculations (such as Time-to-Collision \[TTC\] and time headway), artifact storage, and local esmini simulation execution are well-established engineering capabilities1. Direct translation from intermediate formats into OpenSCENARIO XML using programmatic wrapper libraries like scenariogeneration is fully supported and deterministic6.  
> 2. **Emerging Research Capabilities**: Large Language Model (LLM) scenario intent extraction, Retrieval-Augmented Generation (RAG) over engineering standards, programmatic Intermediate Representation (IR) synthesis, rule-based program repair, and search-guided parameter mutation (fuzzing) represent rapidly expanding research domains7.  
> 3. **Open Research Gaps**: Formal static analysis of OpenSCENARIO trigger reachability prior to simulation, topological map-scenario compatibility verification (such as detecting non-existent lane references or broken junction successor links), systematic separation of standard validity from simulator execution capability, and multi-objective closed-loop scenario repair that preserves semantic diversity without introducing latent physical implausibility remain open research challenges1.

## **Part 2 — Research Landscape**

Automated scenario generation bridges software engineering, formal verification, generative artificial intelligence, robotics, and traffic control dynamics1. The taxonomy of scenario generation spans four primary operational stages, detailed in the table below:

| Architectural Stage | Primary Input / Mechanism | Standard Representations | Dominant Technical Approaches |
| :---- | :---- | :---- | :---- |
| **Requirement Ingestion & Understanding** | Unstructured text, crash narratives, regulatory text, telemetry logs2. | Functional scenario text, taxonomy tags (ISO 34504), IntentSpec1. | LLM prompt engineering (CoT/ToT), Slot-filling, Standard RAG7. |
| **Scenario Representation & World Modeling** | Structured intent, road topology, domain knowledge1. | Scene graphs, Domain-Specific Languages (Scenic), Abstract Syntax Trees4. | Strongly-typed intermediate representations (IR), compiler middle-ends1. |
| **Generation & Compilation** | Semantic IR, vehicle catalogs, map geometries1. | ASAM OpenSCENARIO 1.x XML, OpenDRIVE 1.x XML3. | Programmatic AST compilation (scenariogeneration), Guided diffusion, Evolutionary fuzzing6. |
| **Execution, Evaluation & Closed-Loop Repair** | Compiled scenario bundles, map files, runtime configurations1. | Trajectory traces, OSI streams, Evaluation reports, Revised IR1. | Deterministic simulation (esmini), Spatio-temporal logic monitors, Agentic self-repair5. |

The fundamental research paradigm has evolved from unconstrained neural text-to-XML generation toward compiler-style multi-stage synthesis2. Unconstrained generation of complex XML schemas by neural foundation models consistently introduces malformed syntax, hallucinated entity references, unparseable parameter types, and physically impossible spawn placements2. Consequently, modern state-of-the-art architectures enforce a strict boundary: intelligence-heavy components interpret natural language and plan abstract maneuvers, while deterministic compiler pipelines validate schemas, construct Abstract Syntax Trees (ASTs), enforce map topological constraints, and handle serialization1.

## **Part 3 — Component-by-Component Literature Review (C1–C10)**

### **C1 — User Request / Scenario Requirements**

#### **A. Responsibility**

Component C1 ingests user inputs—such as natural language prompts, structured parameters, crash reconstruction narratives, regulatory provisions, or existing scenario files—and normalizes them into a structured RequestSpec containing intent text, target parameters, operational constraints, and evaluation objectives1.

#### **B. Why Literature Is Required**

This component addresses an emerging research problem at the intersection of natural language processing, domain-specific requirements engineering, and formal specification extraction3. Literature is required to evaluate how ambiguity, missing parameters, and contradictory constraints are parsed without introducing unsupported domain assumptions1.

#### **C. Research Themes**

> * Natural-language scenario specification parsing2.  
> * Crash report and accident narrative to formal test case conversion2.  
> * Requirement normalization, parameter extraction, and ambiguity resolution1.  
> * Rule-to-scenario mapping from formal legal and safety standards2.

#### **D. State of the Art**

Current approaches rely on prompt engineering techniques—such as Chain-of-Thought (CoT) and Tree-of-Thoughts (ToT)—coupled with structured output schemas (such as JSON mode or Pydantic validation) to extract explicit entities and relationships from input narratives2. Advanced systems integrate Retrieval-Augmented Generation (RAG) against scenario taxonomy databases (such as ISO 34504\) to ground free-form text into formal taxonomy nodes15.

#### **E. Representative Papers**

> * **Title**: Txt2Sce: Generating Test Scenarios in OpenSCENARIO Format Based on Textual Accident Reports8  
  * **Authors / Year / Venue**: Deng et al., 2025, arXiv preprint8.  
  * **Problem Addressed**: Generating standardized OpenSCENARIO files directly from unstructured textual crash reports8.  
  * **Method**: Employs LLM parsing to convert accident text into structured scenario templates, followed by scenario block mutation and tree derivation8.  
  * **Main Result**: Successfully generated 33 scenario file trees containing 4,373 test scenarios for the Autoware stack8.  
  * **Limitation**: Primarily addresses textual accident summaries; struggles with missing initial velocity or exact spatial trajectory coordinates unless inferred2.  
  * **Relevance to Phase 1**: Directly validates the C1 requirement of converting unstructured natural language narratives into formal scenario requirements1.

#### **F. Recent Research**

Recent work demonstrates that direct LLM parsing of natural language into executable simulation code often suffers from hallucinations and missing spatial parameters2. Systems like ScenicNL and TARGET mitigate this by enforcing intermediate template slot filling and probabilistic constraints2.

#### **G. Ongoing Research / Active Frontier**

Active research focuses on multimodal requirement ingestion, where text prompts are jointly parsed alongside 2D sketch diagrams or dashcam video clips to resolve spatial ambiguity2.

#### **H. Current Limitations**

Current approaches cannot automatically determine whether an omitted parameter (such as vehicle deceleration rate) should be filled via standard default distributions, requested from the user, or marked as a variable parameter sweep1.

#### **I. Research Gap**

Existing methods perform requirement parsing, but they do not provide a formal ambiguity quantification boundary that explicitly isolates user-specified intent from LLM-inferred default parameters prior to IR generation1.

#### **J. Relevance to Phase 1**

**Must research deeply**. Establishing a clear contract between raw natural language requests and normalized requirement specifications is essential to avoid error propagation into downstream components1.

### **C2 — Scenario Understanding**

#### **A. Responsibility**

Component C2 converts the normalized RequestSpec and knowledge query results into a structured semantic IntentSpec, identifying actors, initial spatial positions, maneuver actions, trigger conditions, temporal-spatial relationships, and safety objectives1.

#### **B. Why Literature Is Required**

Scenario understanding is an established research problem in semantic reasoning, scene graph extraction, and spatial-temporal knowledge representation1.

#### **C. Research Themes**

> * Actor identification and semantic role labeling1.  
> * Spatial, temporal, and causal interaction reasoning1.  
> * Scene graph and dynamic ontology representations3.  
> * LLM-driven intent parsing into intermediate semantic structures2.

#### **D. State of the Art**

State-of-the-art approaches extract symbolic representations or scene graphs from natural language2. Systems convert text into JSON structures defining actor roles (Ego, Target NPC, Pedestrian), relative spatial orientations (lead car, adjacent lane cut-in), and triggered maneuver sequences1.

#### **E. Representative Papers**

> * **Title**: Chat2Scenario: Natural Language Interaction for Extracting and Generating Driving Scenarios9  
  * **Authors / Year / Venue**: Wang et al., 2024, arXiv preprint9.  
  * **Problem Addressed**: Interpreting user intent from naturalistic driving narratives and extracting structured concrete scenarios9.  
  * **Method**: Integrates LLMs with scenario classification models to identify vehicle behaviors, position conditions, and criticality thresholds9.  
  * **Main Result**: Enables automated extraction of concrete ASAM OpenSCENARIO 1.0 scenarios from naturalistic dataset text descriptions9.  
  * **Limitation**: Bound to predefined scenario classification frameworks; limited dynamic temporal reasoning for complex multi-stage triggers1.  
  * **Relevance to Phase 1**: Supports the C2 capability of extracting explicit actor roles, maneuvers, and trigger conditions from intent text1.

#### **F. Recent Research**

Research emphasizes converting intent into intermediate domain-specific structures or scene graphs rather than code, ensuring that spatial-temporal relationships are verified before compilation2.

#### **G. Ongoing Research / Active Frontier**

Frontier research explores multi-agent reasoning models and graph-attention neural networks (such as PreGSU) for generalized traffic scene understanding and interaction classification22.

#### **H. Current Limitations**

Semantic understanding models frequently fail when handling multi-stage conditional trigger chains where the output of one vehicle's maneuver dynamically conditions the spatial trigger of another1.

#### **I. Research Gap**

Current frameworks do not provide deterministic sanity checks to verify whether an extracted spatial-temporal intent graph is topologically compatible with the target road geometry prior to world model construction1.

#### **J. Relevance to Phase 1**

**Must research deeply**. Converting vague human intent into machine-understandable semantics without introducing unsupported assumptions is a core intelligence capability of Phase 11.

### **C3 — Scenario Knowledge**

#### **A. Responsibility**

Component C3 acts as a deterministic knowledge and retrieval layer. It provides engineering standard schemas (ASAM OpenSCENARIO/OpenDRIVE), catalog definitions, domain physical constraints, and simulator feature capability matrices (esmini support profiles) to downstream components1.

#### **B. Why Literature Is Required**

Scenario knowledge representation is an engineering and domain-modeling task, expanding into emerging research on standard-aware RAG systems for domain code compilation1.

#### **C. Research Themes**

> * Automotive knowledge graphs and ontologies (ISO 34501, ASAM standards)10.  
> * RAG architectures for engineering documentation and API libraries7.  
> * Simulator feature support matrices and execution capability modeling1.  
> * Vehicle dynamics catalogs and physical constraint bounds1.

#### **D. State of the Art**

Current implementations use vector databases (such as Chroma or FAISS) containing chunked standard documentation, OpenSCENARIO XSD schemas, and API documentation for Python libraries like scenariogeneration7. Systems like HASCO use RAG to retrieve exact API syntax to prevent LLM code generation errors7.

#### **E. Representative Papers**

> * **Title**: HASCO: Hybrid AI Simulation Compiler for Driving Scene Synthesis7  
  * **Authors / Year / Venue**: OASIcs, 20267.  
  * **Problem Addressed**: Hallucination of invalid physics, illegal XML attributes, and non-existent API calls in direct LLM scenario generation7.  
  * **Method**: Combines RAG over esmini documentation, XSD schemas, and the scenariogeneration Python repository with a compiler pipeline7.  
  * **Main Result**: Eliminates schema errors and achieves significantly higher executable compilation rates compared to end-to-end LLM prompting7.  
  * **Limitation**: Relies on static documentation retrieval; does not dynamically test runtime API support across different esmini build versions1.  
  * **Relevance to Phase 1**: Directly informs the C3 knowledge base design by proving that RAG over standard documentation and generation APIs prevents downstream XML compilation failures1.

#### **F. Recent Research**

Recent work underscores the distinction between *standards-compliant capability* and *simulator-supported execution capability*1. A scenario may be fully valid under ASAM OpenSCENARIO 1.2 XSD rules but fail in esmini due to unimplemented action types or partial controller support1.

#### **G. Ongoing Research / Active Frontier**

Active research targets unified hierarchical taxonomies (integrating OpenDRIVE, OpenSCENARIO, and ISO 34504\) combined with learnable taxonomy anchors for law-scenario and standard-scenario matching15.

#### **H. Current Limitations**

Knowledge bases are predominantly static and do not track version-specific simulator execution limits or runtime edge-case bugs1.

#### **I. Research Gap**

Existing architectures treat knowledge bases as passive documentation repositories rather than active capability matrices that maintain strict explicit mapping between standard XML features and simulator engine execution support1.

#### **J. Relevance to Phase 1**

**Research moderately**. RAG integration is well-understood, but building an explicit esmini execution compatibility matrix is critical for Phase 11.

### **C4 — Scenario Representation / Intermediate Representation (IR)**

#### **A. Responsibility**

Component C4 constructs a canonical, simulator-independent ScenarioIR (World Model) that explicitly captures actors, road topologies, initial physical states, maneuvers, triggers, parameters, and evaluation criteria independent of target file format serialization1.

#### **B. Why Literature Is Required**

Scenario representation is a fundamental, high-priority research problem in computer science and simulation engineering, centered on intermediate abstractions, domain-specific languages (DSLs), and compiler middle-ends2.

#### **C. Research Themes**

> * Simulator-independent scenario intermediate representations1.  
> * Domain-Specific Languages (DSLs) and Abstract Syntax Trees (ASTs) for scenario modeling2.  
> * Formal ontologies versus probabilistic program representations13.  
> * Separation of scenario semantics from OpenSCENARIO XML syntax1.

#### **D. State of the Art**

State-of-the-art systems utilize domain-specific languages like Scenic or structured object models (Pydantic/JSON schemas) that represent scenarios as probabilistic programs or symbolic graphs2. The representation defines spatial relationships using relative geometric constraints (e.g., position ahead of ego by 20m on lane 2\) rather than absolute cartesian coordinate points (![][image1]), allowing scenarios to adapt to varied road networks1.

#### **E. Representative Papers**

> * **Title**: Scenic: A Language for Scenario Specification and Data Generation13  
  * **Authors / Year / Venue**: Fremont et al., 2022, Machine Learning (Springer) / UC Berkeley13.  
  * **Problem Addressed**: Defining complex spatial-temporal distributions over physical scenes and agent behaviors without low-level scripting13.  
  * **Method**: Introduces a probabilistic programming language combining readable geometric spatial constructs, declarative constraints, and dynamic behavioral models13.  
  * **Main Result**: Enables sampling of thousands of diverse concrete scenario traces from abstract probabilistic specifications for testing autonomous systems13.  
  * **Limitation**: Native compiler outputs target simulators like CARLA or LGSVL; direct compilation to ASAM OpenSCENARIO XML requires additional mapping layers2.  
  * **Relevance to Phase 1**: Demonstrates the essential value of separating high-level spatial-temporal scenario semantics from concrete execution engines1.

#### **F. Recent Research**

Research focuses on compiler-style scenario generation where an LLM or planner outputs a structured AST or IR, which a deterministic backend then serializes into target formats like OpenSCENARIO 1.x XML or OpenSCENARIO 2.x DSL3.

#### **G. Ongoing Research / Active Frontier**

Active work includes the development of graph-based scenario representations that combine OpenDRIVE vector topology with dynamic agent interaction trees for structured scenario management and deep learning integration4.

#### **H. Current Limitations**

Most intermediate representations either focus purely on static spatial placement (scene graphs) or dynamic trajectory traces, failing to cleanly integrate trigger conditional logic alongside formal safety evaluation criteria within a single unified IR schema1.

#### **I. Research Gap**

Literature lacks a unified, strongly-typed Intermediate Representation that simultaneously captures declarative OpenSCENARIO trigger-action conditional chains, OpenDRIVE road-relative spatial constraints, and formal evaluation criteria while remaining completely independent of OpenSCENARIO XML syntax1.

#### **J. Relevance to Phase 1**

**Must research deeply**. The IR is the central architectural anchor of Phase 1, isolating cognitive understanding from deterministic code compilation1.

### **C5 — Scenario Generation**

#### **A. Responsibility**

Component C5 takes the validated ScenarioIR alongside selected catalogs and parameter variation profiles, and generates concrete scenario instances (ScenarioBundle), producing executable .xosc XML files and referenced .xodr map files1.

#### **B. Why Literature Is Required**

Scenario generation is an extensively researched, highly active domain encompassing classical rule-based systems, search-based fuzzing, probabilistic sampling, generative neural models, and hybrid LLM compilers3.

#### **C. Research Themes**

> * Template-based and rule-based programmatic generation6.  
> * Search-based testing, genetic algorithms, and fuzzing (DriveFuzz, TM-fuzzer)10.  
> * Controllable generative trajectory models and diffusion frameworks (CTG)18.  
> * Hybrid LLM \+ deterministic compiler pipelines (scenariogeneration integration)3.

#### **D. State of the Art**

The landscape is categorized into five distinct technical paradigms, detailed in the comparison matrix below:

| Generation Approach | Core Mechanism | Key Strengths | Major Limitations | Representative Systems |
| :---- | :---- | :---- | :---- | :---- |
| **Rule-Based / Template** | Predefined parameter scripts and static XML slots | 100% syntactically valid; highly predictable | Low diversity; manual engineering effort | Standard scenariogeneration scripts6 |
| **Search-Based / Fuzzing** | Genetic algorithms mutating parent scenarios based on fitness functions | Highly effective at finding safety violations and bugs | High computational cost; prone to unfeasible physics | DriveFuzz, TM-fuzzer, Doppel10 |
| **Generative / Diffusion** | Denoising diffusion models guided by temporal logic constraints | High trajectory realism; smooth motion profiles | Generates trajectory vectors, not logical OpenSCENARIO XML | CTG, TRACE, SceneStreamer18 |
| **End-to-End LLM** | Direct text-to-code prompting (LLM outputs raw XML/Scenic) | Highly flexible; natural language interface | High syntax error rates; hallucinations; unparseable XML | Early ScenicNL / direct GPT-4 prompting2 |
| **Hybrid Compiler (Proposed Phase-1)** | LLM generates IR/Python code ![][image2] Deterministic API builds AST ![][image2] Serializer emits XML | Combines natural language flexibility with 100% schema correctness | Requires robust IR design and compiler error handling | HASCO, Txt2Sce, Phase-1 Design3 |

#### **E. Representative Papers**

> * **Title**: DriveFuzz: Discovering Autonomous Driving Bugs through Driving Quality-Guided Fuzzing17  
  * **Authors / Year / Venue**: Kim et al., 2022, ACM CCS17.  
  * **Problem Addressed**: Uncovering safety-critical autonomous driving bugs efficiently in simulation without generating unrealistically erratic scenarios17.  
  * **Method**: Introduces physical driving quality metrics to guide evolutionary scenario mutation (fuzzing) across vehicle maneuvers, weather, and road defects10.  
  * **Main Result**: Discovered critical safety bugs in Autoware and Apollo stacks significantly faster than random search17.  
  * **Limitation**: Direct low-level parameter mutation can yield invalid road states or unrealistic traffic interactions27.  
  * **Relevance to Phase 1**: Demonstrates how closed-loop fitness feedback drives scenario mutation, serving as a core paradigm for component C91.

#### **F. Recent Research**

State-of-the-art research overwhelmingly favors hybrid architectures where neural models handle high-level task planning and parameter exploration, while deterministic libraries (such as the scenariogeneration Python package featuring xosc and xodr submodules) handle XML element instantiation6.

#### **G. Ongoing Research / Active Frontier**

Active frontiers explore multi-agent LLM systems that collaboratively negotiate traffic maneuvers and output executable OpenSCENARIO derivation trees8.

#### **H. Current Limitations**

Current search-based generators struggle to balance rare-event criticality search with scenario physical plausibility and OpenDRIVE road network geometric constraints2.

#### **I. Research Gap**

Literature lacks a unified generation framework that combines LLM semantic intent interpretation, programmatic compiler-based OpenSCENARIO construction, and rule-guided multi-agent interaction generation within a single deterministic execution wrapper1.

#### **J. Relevance to Phase 1**

**Must research deeply**. Scenario generation represents the central synthesis engine of the system1.

### **C6 — Scenario Validation**

#### **A. Responsibility**

Component C6 executes multi-stage pre-simulation validation on generated scenario bundles, producing a structured ValidationReport that classifies diagnostics into XML structural, OpenSCENARIO semantic, OpenDRIVE map topological, physical plausibility, temporal reachability, and esmini execution compatibility checks1.

#### **B. Why Literature Is Required**

Scenario validation is an essential research domain spanning formal methods, static analysis, map topology verification, and software testing1.

#### **C. Research Themes**

> * Multi-stage verification funnels (structural ![][image2] semantic ![][image2] physical ![][image2] runtime)1.  
> * Formal topological graph analysis of OpenDRIVE road networks4.  
> * Static reachability analysis of OpenSCENARIO trigger conditions1.  
> * Physical plausibility checks (initialization overlap, maximum acceleration bounds)1.  
> * Standards compliance versus simulator engine execution compatibility1.

#### **D. State of the Art**

Current validation pipelines perform XML schema validation using standard XSD tools, supplemented by semantic checkers (such as the ASAM OpenSCENARIO checker)1. Advanced static analysis frameworks represent OpenDRIVE maps as directed graphs to verify lane connectivity prior to simulation4. The verification pipeline operates across five sequential stages:

> 1. **Stage 1 — Structural Validation**: Rejects malformed XML strings and schema violations1.  
> 2. **Stage 2 — Semantic & Reference Check**: Verifies missing entity references or catalog definitions1.  
> 3. **Stage 3 — OpenDRIVE Map Topological Check**: Detects disconnected lane geometries or invalid junction links4.  
> 4. **Stage 4 — Physical Plausibility & Reachability**: Rejects spawn overlaps and logically unreachable trigger bounds1.  
> 5. **Stage 5 — esmini Engine Preflight Dry-Run**: Identifies unimplemented action types or runtime configuration failures3.

#### **E. Representative Papers**

> * **Title**: Topological Consistency Verification of OpenDRIVE Road Networks for Autonomous Driving Simulation4  
  * **Authors / Year / Venue**: ISPRS Archives, 20264.  
  * **Problem Addressed**: Undetected topological inconsistencies in OpenDRIVE maps (such as disconnected lane segments and broken junction links) that invalidate simulation runs4.  
  * **Method**: Models road networks as hierarchical directed graphs (road, lane, junction levels) and applies adjacency matrix reachability algorithms to verify topological consistency predicates4.  
  * **Main Result**: Identified widespread topological defects across production maps (error-to-road ratios up to 3.94), proving that geometric accuracy does not guarantee topological connectivity4.  
  * **Limitation**: Focuses strictly on static OpenDRIVE map topology; does not evaluate dynamic OpenSCENARIO trajectory entity interactions on the map1.  
  * **Relevance to Phase 1**: Provides the theoretical and algorithmic basis for component C6 map compatibility validation, proving that formal static graph analysis prevents runtime simulation failures1.

#### **F. Recent Research**

Recent literature highlights that formal verification of scenario reachability is necessary to detect deadlocks and logically unreachable triggers (e.g., a trigger requiring Ego velocity ![][image3] when the motor profile caps at ![][image4]) before initiating computationally expensive simulation runs1.

#### **G. Ongoing Research / Active Frontier**

Active research focuses on low-cost static verification engines capable of analyzing combined OpenSCENARIO conditional state machines and OpenDRIVE spatial graph constraints simultaneously4.

#### **H. Current Limitations**

Existing validation tools operate in isolation: XML checkers ignore map topology, map verifiers ignore dynamic trigger conditions, and neither accounts for simulator-specific implementation subsets1.

#### **I. Research Gap**

There is no unified pre-execution validation engine that performs static joint analysis over OpenSCENARIO state-machine reachability, OpenDRIVE topological lane connectivity, physical vehicle kinematic bounds, and simulator-specific feature support matrices prior to runtime execution1.

#### **J. Relevance to Phase 1**

**Must research deeply**. Multi-layer validation is the crucial bridge that guarantees generated scenarios are both standard-compliant and executably valid in esmini1.

### **C7 — esmini Simulation**

#### **A. Responsibility**

Component C7 serves as the deterministic execution engine. It loads the validated ScenarioBundle, initializes esmini's ScenarioEngine and RoadManager, steps through the simulation clock, executes controllers, and records ground-truth state trajectories alongside Open Simulation Interface (OSI) trace streams1.

#### **B. Why Literature Is Required**

This component represents an established engineering domain centered on lightweight simulation execution engines, deterministic timing semantics, and OSI ground-truth streaming1. Literature is required to establish execution semantics, determinism constraints, and feature coverage limitations1.

#### **C. Research Themes**

> * OpenSCENARIO execution engine mechanics and runtime semantics3.  
> * Deterministic time-stepping, random seed handling, and reproducibility1.  
> * Open Simulation Interface (OSI) ground-truth extraction and packaging3.  
> * Feature coverage matrices (standards-compliant versus engine-supported)1.

#### **D. State of the Art**

esmini is an open-source C++ implementation designed specifically to parse and execute ASAM OpenSCENARIO 1.x files with OpenDRIVE road networks5. It provides a C API, a Python wrapper, an internal ScenarioEngine for state machine trigger handling, and a RoadManager for coordinate alignment and lane-following kinematics3.

#### **E. Representative Papers / Technical Documentation**

> * **Title**: esmini — OpenSCENARIO Player and Library Documentation5  
  * **Authors / Year / Source**: Emilsson et al., 2026 (Ongoing Maintainers), Official Documentation & GitHub Repository5.  
  * **Problem Addressed**: Lightweight, high-throughput execution of OpenSCENARIO dynamic traffic descriptions without heavy 3D rendering overhead3.  
  * **Method**: Implements a modular C++ architecture featuring ScenarioEngine for state-machine trigger/action evaluation and RoadManager for OpenDRIVE map navigation3.  
  * **Main Result**: Provides high-performance, deterministic execution of OpenSCENARIO XML (versions 1.0–1.2) with OSI ground-truth output streaming3.  
  * **Limitation**: Implements a subset of the full OpenSCENARIO standard; advanced actions or complex custom controller features may be unsupported or behave differently than specified in standard documentation1.  
  * **Relevance to Phase 1**: Defines the exact execution target and capabilities for component C7 in Phase 11.

#### **F. Recent Research**

Recent work utilizes esmini as a fast, headless screening engine in multi-stage validation pipelines, filtering thousands of scenarios before passing edge cases to photorealistic simulators like CARLA3.

#### **G. Ongoing Research / Active Frontier**

Active development in esmini focuses on improving OpenSCENARIO 1.2 feature coverage, enhancing OSI sensor data generation, and supporting modular external controller couplings via ROS 2/FMI3.

#### **H. Current Limitations**

esmini does not support all OpenSCENARIO actions and trigger combinations. Scenarios using unsupported elements may load without warnings but exhibit unhandled kinematic behavior or early termination during runtime1.

#### **I. Research Gap**

Literature lacks an open empirical profiling benchmark detailing the precise boundary between ASAM OpenSCENARIO standard specification rules and actual executable behavior within specific esmini release builds1.

#### **J. Relevance to Phase 1**

**Primarily engineering**. esmini is a provided execution capability; research should focus strictly on compatibility boundaries and deterministic logging interfaces1.

### **C8 — Observation & Evaluation**

#### **A. Responsibility**

Component C8 transforms raw simulation execution logs and OSI trace streams (RunRecord) into normalized quantitative safety metrics, behavioral completion indicators, objective pass/fail decisions, and criticality scores (EvaluationReport)1.

#### **B. Why Literature Is Required**

Scenario observation and safety evaluation is a mature, highly developed research field spanning surrogate safety measures, functional metric design, and scenario criticality ranking1.

#### **C. Research Themes**

> * Kinematic safety metrics (Time-to-Collision \[TTC\], Post-Encroachment Time \[PET\], Time Headway)1.  
> * Behavioral maneuver completion and traffic rule compliance checking1.  
> * Scenario criticality scoring and risk ranking1.  
> * Distinction between measurement, evaluation, interpretation, and ranking1.

#### **D. State of the Art**

Current approaches evaluate simulation traces using programmatic rulebooks or spatio-temporal logic monitors2. Systems separate metric calculation (e.g., minimum TTC \= ![][image5]) from semantic evaluation (e.g., safety rule violation \= True) and interpretative reasoning (e.g., late braking caused near-miss)1. The evaluation processing hierarchy consists of four distinct operational layers:

> 1. **Measurement Layer**: Extracts basic kinematic states (positions, velocities, accelerations) from raw OSI logs1.  
> 2. **Metric Calculation Layer**: Computes mathematical surrogate safety metrics including TTC, PET, time headway, and jerk1.  
> 3. **Objective Evaluation Layer**: Evaluates metrics against formal pass/fail thresholds and traffic rule compliance rulebooks2.  
> 4. **Semantic Interpretation & Criticality Layer**: Performs root-cause analysis and assigns qualitative risk scores1.

#### **E. Representative Papers**

> * **Title**: Parallel and Multi-Objective Falsification with Scenic and VerifAI19  
  * **Authors / Year / Venue**: Viswanadha et al., 2021, RV (International Conference on Runtime Verification)19.  
  * **Problem Addressed**: Efficient evaluation and falsification of autonomous driving system behavior against complex, multi-objective temporal specifications19.  
  * **Method**: Integrates Scenic scenario sampling with VerifAI, using formal rulebooks (DAG-structured metric priorities) to evaluate simulation trajectories19.  
  * **Main Result**: Demonstrated parallelized falsification that rapidly discovers trajectory edge cases violating prioritized safety metrics19.  
  * **Limitation**: Requires manual specification of formal metric rulebooks for each scenario domain19.  
  * **Relevance to Phase 1**: Establishes the formal methodology for multi-metric evaluation and falsification scoring in component C81.

#### **F. Recent Research**

Recent studies emphasize multi-objective reinforcement learning (MORL) metrics and sequence-level behavioral diversity scores to evaluate both scenario criticality and regional coverage12.

#### **G. Ongoing Research / Active Frontier**

Active research explores Vision-Language Models (VLMs) and LLMs for semantic interpretation of simulation logs, generating qualitative behavioral explanations for why a scenario failed or proved critical3.

#### **H. Current Limitations**

Standard kinematic metrics (such as TTC) produce false positives in dense urban traffic or low-speed intersection maneuvers where low physical distance does not correspond to actual collision risk1.

#### **I. Research Gap**

Current frameworks lack a standardized evaluation schema that cleanly separates deterministic numerical trajectory measurement from high-level reasoning-based behavioral intent classification1.

#### **J. Relevance to Phase 1**

**Research moderately**. Metric calculation algorithms are standard engineering, but structuring multi-level evaluation contracts is essential for closed-loop repair1.

### **C9 — Feedback & Improvement**

#### **A. Responsibility**

Component C9 ingests diagnostic validation failures (ValidationReport) or simulation outcome evaluations (EvaluationReport), diagnoses root causes, and generates revised intermediate representations (RevisedIR) or parameter variation plans1.

#### **B. Why Literature Is Required**

Feedback-driven scenario improvement is a high-priority, cutting-edge research domain encompassing automated program repair, simulation-guided search, evolutionary mutation, and agentic reflection loops1.

#### **C. Research Themes**

> * Error-driven programmatic repair vs. search-driven parameter optimization1.  
> * LLM-based reflection, code repair, and self-evolving scenario adaptation3.  
> * Evolutionary scenario mutation and fuzz testing10.  
> * Adversarial scenario exploration and active learning loops10.

#### **D. State of the Art**

State-of-the-art closed-loop frameworks fall into two distinct functional categories:

> 1. **Automated Repair**: Diagnoses invalid scenarios (e.g., target lane does not exist) and applies structural mutations to produce valid executable files1.  
> 2. **Exploration & Optimization**: Mutates valid scenarios to maximize safety criticality (e.g., minimizing TTC) using genetic algorithms, Bayesian optimization, or agentic parameter sweep planning10.

#### **E. Representative Papers**

> * **Title**: SERA: Self-Evolving Scenario Repair and Recommendation for Autonomous Driving Systems11  
  * **Authors / Year / Venue**: arXiv preprint, 202511.  
  * **Problem Addressed**: Closed-loop repair of scenario failure cases and automated recommendation of targeted test variations11.  
  * **Method**: Employs an LLM reflection mechanism that analyzes performance logs, performs failure-aware scenario recommendations, and applies self-evolving repair to scenario scripts11.  
  * **Main Result**: Significantly improves failure discovery rates and scenario repair success compared to unguided baseline generation11.  
  * **Limitation**: High LLM token cost during iterative repair loops; risk of repair loops converging to trivial or repetitive scenario variations1.  
  * **Relevance to Phase 1**: Provides direct literature justification for the C9 feedback and repair loop using LLM reflection over simulation logs1.

#### **F. Recent Research**

Research demonstrates that coupling LLM self-repair agents with deterministic compiler checkers (as in HASCO and SERA) achieves higher repair convergence rates than unconstrained re-prompting7.

#### **G. Ongoing Research / Active Frontier**

Active research explores closed-loop adversarial scenario generation using Collision Knowledge Graphs (KG-ASG) and safety-informed embedding spaces to discover edge cases systematically38.

#### **H. Current Limitations**

Feedback loops often suffer from *diversity collapse*, where iterative repair or optimization continually modifies parameters toward a narrow cluster of extreme scenarios (such as instant maximum deceleration) while failing to explore the broader operational design domain1.

#### **I. Research Gap**

Literature lacks a unified feedback orchestrator that cleanly decouples deterministic error-driven repair (fixing schema/map invalidity) from intelligence-driven parameter optimization and diversity-preserving scenario exploration1.

#### **J. Relevance to Phase 1**

**Must research deeply**. Closed-loop feedback and repair represents a core technical innovation in Phase 11.

### **C10 — Scenario Management**

#### **A. Responsibility**

Component C10 provides persistent storage, indexing, versioning, data lineage tracking, deduplication, and metadata management across all system envelopes, artifacts, execution logs, and evaluation reports (ScenarioLineage)1.

#### **B. Why Literature Is Required**

Scenario management is primarily an infrastructure engineering task, intersecting with research on simulation experiment reproducibility, data lineage graphs, and scenario set diversity1.

#### **C. Research Themes**

> * Scenario repository databases and artifact version control1.  
> * Provenance tracking from requirement text to execution metrics1.  
> * Reproducibility contract enforcement (seeds, configurations, versions)1.  
> * Deduplication, scenario clustering, and similarity metrics27.

#### **D. State of the Art**

Modern platforms like ScenarioNet provide unified simulation data management, ingesting heterogeneous dataset formats and indexing scenarios by road topology, actor density, and interaction types40. Artifact management systems store explicit hashes linking input requests, intermediate representations, generated XML files, map versions, esmini build hashes, and output trajectories1.

#### **E. Representative Papers**

> * **Title**: ScenarioNet: Open-Source Platform for Large-Scale Traffic Scenario Simulation and Modeling40  
  * **Authors / Year / Venue**: Li et al., 2024, NeurIPS (Advances in Neural Information Processing Systems)40.  
  * **Problem Addressed**: Fragmentation of driving scenario datasets and lack of unified data pipeline tools for large-scale scenario modeling40.  
  * **Method**: Constructs a standardized database format and simulation platform capable of ingesting synthetic and real-world datasets (Waymo, nuScenes, CARLA)40.  
  * **Main Result**: Enables seamless scenario retrieval, cross-dataset training, and high-throughput evaluation across millions of frames40.  
  * **Limitation**: Designed primarily for trajectory data vectors rather than structured ASAM OpenSCENARIO state-machine XML artifacts1.  
  * **Relevance to Phase 1**: Informs component C10 regarding structured scenario indexing, database abstraction, and retrieval strategies1.

#### **F. Recent Research**

Recent work focuses on graph-based scenario management systems where individual scenario versions and their repair lineages are represented as directed acyclic provenance graphs4.

#### **G. Ongoing Research / Active Frontier**

Active research focuses on automated scenario deduplication using trajectory embedding spaces and graph similarity metrics to prevent redundant testing27.

#### **H. Current Limitations**

Existing scenario repositories focus either on raw file storage (Git/S3) or numerical trajectory indexing, lacking native support for tracking the evolutionary lineage of automated repair iterations1.

#### **I. Research Gap**

Literature lacks a dedicated provenance management schema designed specifically to track the multi-stage derivation lineage connecting user requirement specifications, intermediate representations, compiled OpenSCENARIO XML files, esmini build configurations, and feedback repair steps1.

#### **J. Relevance to Phase 1**

**Primarily engineering**. While foundational for system traceability, artifact storage and versioning rely on established software engineering practices1.

## **Part 4 — Cross-Cutting Research Capabilities**

### **A. Scenario Provenance**

Scenario provenance defines the end-to-end audit trail tracking how an initial user requirement evolves through interpretation, knowledge retrieval, IR generation, XML compilation, preflight validation, simulation execution, observation calculation, and feedback repair1. Research in data lineage demonstrates that establishing cryptographically hashed provenance graphs (linking RequestSpec ![][image2] IntentSpec ![][image2] ScenarioIR ![][image2] ScenarioBundle ![][image2] ValidationReport ![][image2] RunRecord ![][image2] EvaluationReport ![][image2] RevisedIR) is critical for diagnosing systemic failure propagation and ensuring regulatory compliance under ISO 26262 / ISO 21448 standards1.

### **B. Reproducibility**

Simulation reproducibility requires strict deterministic controls across six operational axes:

> 1. Scenario XML content hash1.  
> 2. OpenDRIVE map file geometry and topology hash1.  
> 3. Exact simulator engine build version and library dependencies (esmini release tag)1.  
> 4. Simulation fixed time-step size (![][image6]) and integration solver configuration1.  
> 5. Random seed initialization for traffic controllers and stochastic behaviors1.  
> 6. Operating environment and hardware architecture parameters1.

Failing to pin fixed time-step parameters or library build versions causes identical OpenSCENARIO files to exhibit diverging trigger activation timelines across execution runs1.

### **C. Scenario Diversity**

Generating thousands of scenarios provides minimal testing value if scenarios represent minor variations of identical interactions1. State-of-the-art diversity assessment utilizes mathematical distance metrics over state sequences12:

> * **Unique Behavior Sequences (\#UB)**: Counts unique discrete action sequences across traffic actors12.  
> * **Unique Behavior Distance (UBD) & Within-Behavior Distance (WBD)**: Measures trajectory dynamic variations within identical behavioral classes12.  
> * **Sequence-Based Coverage Metric (SCD)**: Quantifies dynamic interaction differences across multi-actor spatial trajectories12.  
> * **Map-Aware Diversity Metric (MASD)**: Evaluates average spatial displacement between distinct trajectory samples on drivable road areas46.

### **D. Scenario Coverage**

Scenario coverage quantifies how thoroughly a generated test suite explores the operational space35. Literature distinguishes six hierarchy levels:

> 1. **Parameter Coverage**: Sampling density across individual continuous variables (e.g., speed, initial headway)13.  
> 2. **Road Topology Coverage**: Diversity of OpenDRIVE geometries tested (straight, curved, junction, roundabout)4.  
> 3. **Behavioral / Interaction Coverage**: Percentage of functional maneuvers (cut-in, merging, braking) represented12.  
> 4. **State-Space Coverage**: Extent to which multi-agent physical configurations fill the reachable state space35.  
> 5. **Requirement / Rule Coverage**: Proportion of formal safety rules or regulatory provisions exercised2.  
> 6. **Criticality Coverage**: Proportion of scenarios operating near or beyond safety failure thresholds9.

### **E. Failure Taxonomy**

The Phase-1 failure analysis establishes a 9-tier structural failure taxonomy, categorized below alongside literature definitions:

| Failure Tier | Primary Cause & Literature Manifestation | Diagnostic Stage |
| :---- | :---- | :---- |
| **Generation Failure** | Malformed XML syntax, unclosed tags, illegal attribute data types1. | Pre-simulation (C5/C6) |
| **Validation Failure** | XSD schema non-compliance, missing entity or catalog references1. | Pre-simulation (C6) |
| **Map Compatibility Failure** | Entity assigned to non-existent road/lane ID; broken junction topology1. | Pre-simulation (C6) |
| **Load Failure** | esmini scenario parser or RoadManager fails during file initialization1. | Preflight (C6/C7) |
| **Runtime Execution Failure** | Simulation engine crash, infinite loop, memory segmentation fault1. | Execution (C7) |
| **Trigger Failure** | Trigger condition logically unreachable; state machine deadlocks1. | Execution (C7) |
| **Behavioral Failure** | Entity teleports, off-road pathing, physically impossible acceleration1. | Execution (C7/C8) |
| **Evaluation Failure** | Ground-truth metrics calculation error; missing state telemetry1. | Post-simulation (C8) |
| **Infrastructure Failure** | Operating system process failure, disk I/O timeout, corrupted trace log1. | System-level |

## **Part 5 — Dedicated LLM and Agentic Systems Research (2024–2026)**

The application of Large Language Models and autonomous agent architectures to autonomous driving testing has accelerated rapidly from 2024 to 20262. However, critical analysis reveals significant variance between theoretical agentic claims and verified engineering implementations.  
The table below details key representative agentic driving systems from recent literature, breaking down the specific role of the LLM, the exact tool integrations used, the nature of simulator feedback, and the quantitative validation demonstrated:

| Framework & Year | Specific LLM Role | Integrated Tools & APIs | Simulator Feedback & Iteration | Output Validation & Determinism | Quantitative Evaluation Results |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **HASCO (2026)** \[cite: 7\] | Parses NL intent; generates scenariogeneration Python code using RAG7. | RAG vector DB, scenariogeneration API, esmini validator7. | Compiler error feedback; re-prompts code generation upon failure7. | Fully deterministic downstream AST compilation7. | Near 100% executable compilation success vs ![][image7] direct LLM output7. |
| **Txt2Sce (2025)** \[cite: 8\] | Converts crash text into OpenSCENARIO blocks and derivation trees8. | OpenSCENARIO block tree, Autoware execution engine8. | Iterative block mutation based on execution outcomes8. | Validates XML against Autoware simulation interfaces8. | Generated 33 derivation trees yielding 4,373 valid test scenarios8. |
| **ScenicNL (2026)** \[cite: 2\] | Translates crash narratives into probabilistic Scenic DSL programs2. | Scenic AST parser, CARLA simulator, traffic rule monitors2. | Compiler syntax feedback incorporated into LLM prompt chain2. | Deterministic sampling using fixed random seeds2. | Tested against 11 traffic regulations in CARLA2. |
| **SERA (2025)** \[cite: 11\] | Analyzes failure logs, recommends scenario variations, and repairs code11. | Performance log analyzer, scenario bank, reflection repair engine11. | Closed-loop self-evolving reflection loop using simulator logs11. | Relies on simulator feedback for outcome verification11. | Superior failure discovery and repair convergence vs static baselines11. |

## **Part 6 — Diffusion and Generative Model Research**

Generative deep learning models—specifically denoising diffusion probabilistic models—have emerged as powerful tools for continuous motion synthesis in autonomous driving18. However, their applicability must be positioned precisely within the Phase-1 system abstraction.  
In the proposed architecture, diffusion models do not replace the top-level understanding or world-modeling components. Instead, they operate strictly within **Component C5 (Scenario Generation)** as specialized trajectory synthesis tools. While compiler-based pipelines (xosc) generate discrete conditional state-machine triggers, diffusion frameworks synthesize dense, multi-agent continuous trajectory matrices (![][image8] coordinates). These continuous trajectory arrays are then imported into the generated OpenSCENARIO XML files via \<Trajectory\> or \<Polyline\> elements.  
Key generative diffusion frameworks include:

> 1. **CTG (Controllable Traffic Generation / Guided Conditional Diffusion, 2023–2025)**:  
   * *Method*: Leverages conditional diffusion guided by Signal Temporal Logic (STL) formulas to generate multi-agent trajectories satisfying formal rules (e.g., speed limits, distance bounds)18.  
   * *System Placement*: Fits strictly within **Component C5 (Scenario Generation)** as a continuous trajectory synthesis engine for complex multi-agent interactions1.  
   * *Relevance to Phase 1*: Highly relevant if Phase 1 requires generating dense, realistic actor trajectories imported into OpenSCENARIO via \<Trajectory\> or \<Polyline\> tags; irrelevant for generating discrete OpenSCENARIO conditional state-machine triggers1.  
> 2. **TRACE (Trajectory Diffusion Model for Controllable Pedestrians, 2023\)**:  
   * *Method*: Uses classifier-free diffusion over spatial grid map features to synthesize pedestrian paths28.  
   * *System Placement*: Fits within **Component C5 (Scenario Generation)** specifically for non-vehicle pedestrian trajectory synthesis1.  
> 3. **SceneStreamer (Autoregressive Scene Transformer, 2025\)**:  
   * *Method*: Generates continuous traffic scenes token-by-token using autoregressive sequence modeling29.  
   * *System Placement*: Competes with C4/C5 world modeling, but operates on raw token sequences rather than structured OpenSCENARIO XML1.

## **Part 7 — E01–E10 Research Mapping**

The ten Phase-1 experiments (E01–E10) defined in trajectories.md function as a capability-discovery test suite1. The table below maps each experiment to tested capabilities, failure modes, established literature methods, limitations, status, and recommended follow-up experiments:

| Exp ID | Scenario & Capability Tested | Failure Mode Tested | Established Literature Approach | Current Literature Limitations | Problem Status | Recommended Follow-up Experiment |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| **E01** | Constant-Speed Following (C1-C5, C7, C8)1 | Baseline happy path; initialization state errors1. | Parametric XML script generation (scenariogeneration)6. | None for basic straight-line car following1. | **Solved** | E01b: Curve-following on non-zero elevation OpenDRIVE road1. |
| **E02** | Sudden Lead Braking (C5, C7, C8, C9)1 | Longitudinal action timing; delayed trigger execution1. | Parametric speed action triggers in OpenSCENARIO3. | Fixed deceleration rates lack dynamic vehicle weight/friction bounds1. | **Solved** | E02b: Braking with friction coefficient change (![][image9] drop)1. |
| **E03** | Ego Acceleration to Speed (C5, C7, C8)1 | Speed action bounds; target speed overshoot1. | Absolute/relative speed action profiles3. | Simple linear rate acceleration ignores engine torque curves1. | **Solved** | E03b: Acceleration ramp coupled with lane merge1. |
| **E04** | Planned Lane Change (C4-C7)1 | OpenDRIVE road-relative spatial positioning1. | LaneChangeAction with relative lane offset3. | Fails if target lane offset is topologically invalid1. | **Partially Solved** | E04b: Multi-lane change across junction boundaries1. |
| **E05** | Target Vehicle Cut-In (C2, C4-C9)1 | Multi-actor spatial interaction & distance trigger1. | Fuzzing & distance-triggered lateral maneuvers17. | High sensitivity to initial gap distance sampling27. | **Partially Solved** | E05b: Blind-spot cut-in during Ego acceleration1. |
| **E06** | Pedestrian Crossing (C2, C5-C8)1 | Heterogeneous actor dynamics & collision metric1. | Pedestrian trajectory actions & TTC monitoring19. | Pedestrian movement lacks realistic reactive dodging28. | **Partially Solved** | E06b: Pedestrian emerging from behind parked vehicle1. |
| **E07** | Multi-Stage Trigger Chain (C2, C4, C7, C8)1 | Temporal causality & condition state-machine deadlock1. | OpenSCENARIO Storyboard event dependency chains3. | High risk of unreachable downstream triggers1. | **Open Research** | E07b: Circular conditional trigger dependencies1. |
| **E08** | Invalid Lane Request (C4, C6, C9)1 | Map compatibility failure; target lane non-existent1. | Static OpenDRIVE graph verification4. | Standard XML validators miss map graph disconnects1. | **Partially Solved** | E08b: Lane reduction merge at highway taper1. |
| **E09** | Unreachable Trigger (C4, C6, C7, C9)1 | Semantic & reachability failure; condition impossible1. | Formal reachability analysis / SMT solvers14. | SMT verification scales poorly to complex scenarios14. | **Open Research** | E09b: Trigger conditioned on impossible speed (![][image3])1. |
| **E10** | Runtime Compatibility Failure (C3, C6, C7, C9)1 | Simulator feature support gap vs XML standard1. | Simulator-in-the-loop dry-run screening3. | No static tool maps standard XML to esmini features1. | **Open Research** | E10b: Unimplemented OpenSCENARIO 1.2 action execution1. |

## **Part 8 — Failure-Mode Research Mapping**

The Phase-1 ![][image10] failure-mode matrix categorizes system risk across four quadrants1. The table below maps these failure modes to relevant literature, solution status, testing experiments, and research gaps:

| Failure Mode Quadrant | Specific Failure Description | Related Component | Existing Literature Coverage | Solved Status | Relevant Exp ID | Specific Research Gap Identified |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| **Known Knowns** (Expected / Explicit)1 | Malformed XML, XSD schema error, missing fields1. | C1, C5, C6 | XML Schema (XSD) checkers, standard compilers3. | **Solved** | E081 | Standard engineering; no research gap1. |
| **Known Knowns** (Expected / Explicit)1 | Missing file links, esmini scenario load crash1. | C3, C6, C7 | esmini loader dry-runs, file path checkers3. | **Solved** | E101 | Engineering implementation; no research gap1. |
| **Known Unknowns** (Unresolved Contracts)1 | Natural language requirement ambiguity & missing bounds1. | C1, C2 | Prompt slot-filling, ScenicNL, Txt2Sce2. | **Partially Solved** | E01-E071 | Lack of formal boundary separating explicit user intent from LLM defaults1. |
| **Known Unknowns** (Unresolved Contracts)1 | Standards-compliant XML vs esmini execution support gap1. | C3, C6, C7 | HASCO RAG retrieval over documentation7. | **Partially Solved** | E101 | Absence of static feature support compatibility matrices for esmini1. |
| **Known Unknowns** (Unresolved Contracts)1 | Multi-stage trigger reachability & deadlock detection1. | C4, C6 | SMT reachability, formal verification14. | **Open** | E091 | Static analysis engines cannot verify runtime trigger reachability efficiently1. |
| **Unknown Knowns** (Implicit Domain Assumptions)1 | Entity assigned to invalid/disconnected OpenDRIVE lane1. | C4, C5, C6 | Graph connectivity analysis over OpenDRIVE4. | **Partially Solved** | E04, E081 | XSD validators ignore map topology; graph checks not built into OSC tools1. |
| **Unknown Knowns** (Implicit Domain Assumptions)1 | Initial physical placement collision / impossible speed1. | C4, C5, C6 | Kinematic bounding, physical plausibility funnels3. | **Partially Solved** | E051 | Spatial placement tools lack road-relative kinematic overlap validation1. |
| **Unknown Unknowns** (Experiment Discovered)1 | Repair loop amplifies defects or causes diversity collapse1. | C9 | SERA, TM-fuzzer, MORL diversity analysis11. | **Open** | E01-E07 Probes1 | Closed-loop repair loops lack diversity-preserving loss constraints1. |
| **Unknown Unknowns** (Experiment Discovered)1 | Simulator version drift changes trajectory interpolation1. | C7, C10 | Provenance tracking, containerization1. | **Partially Solved** | E101 | Lack of fine-grained execution trace lineage matching across build tags1. |

## **Part 9 — State-of-the-Art Comparison Matrix**

The table below provides a systematic comparison across the five primary architectural approaches present in published literature and the proposed Phase-1 system:

| Evaluation Dimension | Classical / Template-Based | Search / Fuzzing (DriveFuzz) | Probabilistic DSLs (Scenic) | End-to-End LLM Prompting | Proposed Phase-1 Compiler Architecture |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **Input Modality** | Manual Python / XML scripts6. | Seed scenarios & parameter ranges10. | Probabilistic code domain specifications13. | Natural language / crash text2. | Natural language, requirements, or parameters1. |
| **Representation Abstraction** | Direct OpenSCENARIO XML6. | Low-level parameter vectors17. | Scenic DSL / AST13. | Unstructured text ![][image2] raw XML2. | Strongly-typed Semantic IR (World Model)1. |
| **Schema & Syntax Correctness** | 100% compliant6. | High compliance (mutates valid seeds)10. | High (handled by DSL parser)13. | Very Low (![][image7] executable)2. | 100% compliant (guaranteed by AST compiler)3. |
| **Map Topological Safety** | Manual verification4. | Ignored (causes off-road spawns)27. | High (requires map declaration)13. | None (frequent invalid lane IDs)2. | High (static OpenDRIVE graph verification)1. |
| **Criticality / Bug Discovery** | Low (tests nominal paths)7. | Very High (guided fuzzing search)17. | High (via falsification samplers)19. | Moderate (uncontrolled edge cases)2. | High (closed-loop repair & exploration)1. |
| **Execution Target** | OpenSCENARIO engines5. | CARLA / LGSVL / Autoware17. | CARLA / LGSVL / Custom13. | CARLA / ScenarioRunner2. | Target-agnostic IR ![][image2] esmini (Phase 1\)1. |
| **Closed-Loop Repair Mechanism** | None6. | Genetic mutation based on fitness10. | Resampling from distribution13. | Unconstrained re-prompting2. | Multi-stage diagnosis ![][image2] IR mutation ![][image2] Re-compilation1. |

## **Part 10 — Research Gap Analysis and Gap Map**

Based on evidence synthesized across literature and experimental failure analysis, research problems are classified into five explicit maturity categories:

> 1. **Well-Established (Engineering Solutions Mature)**: XML Schema (XSD) validation and syntax parsing3; esmini lightweight execution and OSI trace logging3; kinematic metric computation (TTC, PET, distance)1.  
> 2. **Partially Solved (Solutions Exist but Have Notable Boundaries)**: LLM intent parsing into structured JSON schemas2; OpenDRIVE directed graph topological verification4; evolutionary parameter mutation and fuzzing search10.  
> 3. **Emerging Research (Active Frontier; No Consolidated Standard)**: RAG-guided scenario code compilation (HASCO)7; LLM reflection-driven self-evolving scenario repair (SERA)11; guided trajectory diffusion models with STL constraints (CTG)18.  
> 4. **Open Research Gaps (Substantial Unresolved Challenges)**: Static pre-execution analysis of OpenSCENARIO trigger reachability1; explicit capability mapping between standard compliance and simulator execution1; diversity-preserving closed-loop multi-objective repair loops1.  
> 5. **Pure Engineering Problems (Implementation Tasks; Not Research Gaps)**: Database persistence of execution artifacts (S3/PostgreSQL)1; process orchestration for batch simulation scheduling1.

### **Precise Evidence-Based Research Gap Formulations**

#### **Research Gap 1: Pre-Execution Analysis of OpenSCENARIO Trigger Reachability**

> * **Existing Solution**: Current systems rely on runtime execution in simulators to determine whether triggers fire1.  
> * **Unsolved Limitation**: Syntactically valid OpenSCENARIO files frequently contain state-machine conditions that are logically unreachable under physical kinematics (e.g., E09)1.  
> * **Supporting Sources**: Identified in formal verification literature14 and esmini runtime documentation5.  
> * **Impact on Phase 1**: Results in wasted simulation compute cycles executing deadlocked scenarios1.  
> * **Demonstrating Experiment**: Experiment E09 (Unreachable Trigger)1.  
> * **Defensible Contribution**: Developing a lightweight static analyzer that evaluates OpenSCENARIO trigger condition state machines against vehicle acceleration bounds prior to execution1.

#### **Research Gap 2: Formal Mapping Between Standard Schema Validity and Simulator Execution Capability**

> * **Existing Solution**: Systems assume that passing ASAM XSD validation guarantees simulator execution1.  
> * **Unsolved Limitation**: OpenSCENARIO validation tools evaluate standard XML compliance, but simulator engines (esmini) implement selective subsets of standard features, leading to silent runtime misbehavior or load crashes (e.g., E10)1.  
> * **Supporting Sources**: Demonstrated in HASCO7 and esmini feature notes5.  
> * **Impact on Phase 1**: Valid scenarios fail unexpectedly during execution without clear diagnostic feedback1.  
> * **Demonstrating Experiment**: Experiment E10 (Runtime Feature Compatibility Failure)1.  
> * **Defensible Contribution**: Formulating an explicit, machine-readable simulator capability matrix that intercepts and transforms unsupported standard XML elements during compilation1.

#### **Research Gap 3: Diversity-Preserving Closed-Loop Scenario Repair**

> * **Existing Solution**: LLM and fuzzing repair loops modify failing scenarios based on immediate pass/fail feedback11.  
> * **Unsolved Limitation**: Iterative feedback loops trigger *diversity collapse*, continually modifying parameters toward trivial extreme values (e.g., instantaneous max braking) while failing to preserve scenario intent or regional state-space coverage1.  
> * **Supporting Sources**: Documented in multi-objective RL and fuzzing studies12.  
> * **Impact on Phase 1**: Automatic repair loops generate repetitive, non-diverse scenarios1.  
> * **Demonstrating Experiment**: Iterative repair across Probe Experiments E01–E071.  
> * **Defensible Contribution**: Constructing a closed-loop repair manager that combines LLM reflection with explicit sequence diversity metrics (SCD/UBD) to enforce parameter spread during repair1.

## **Part 11 — Recommended Phase-1 Research Scope**

To maximize scientific validity and implementation efficiency, the Phase-1 research scope is divided into four execution tiers:

> 1. **Must Research Deeply (Core Novelty & System Contracts)**:  
   * Strongly-Typed Semantic Intermediate Representation (Component C4)1.  
   * Multi-Stage Validation Funnel & OpenDRIVE Graph Verification (Component C6)1.  
   * Closed-Loop Repair with Diversity-Preserving Loss Constraints (Component C9)1.  
> 2. **Useful Research (Integrate Existing State-of-the-Art Methods)**:  
   * Standard-Aware RAG for Requirement Intent Parsing (Components C1-C3)7.  
   * Kinematic Metric Extraction & Objective Prioritization (Component C8)9.  
> 3. **Engineering Only (Implement Standard Software Patterns)**:  
   * AST Serialization to OpenSCENARIO via scenariogeneration (Component C5)6.  
   * Local esmini Process Execution & OSI Log Parsing (Component C7)3.  
   * Database Persistence & Cryptographic Provenance Graph (Component C10)1.  
> 4. **Defer to Phase 2 (Future Scope Expansion)**:  
   * Photorealistic CARLA Rendering & Sensor Simulation2.  
   * Generative Trajectory Diffusion Models (CTG/TRACE)18.  
   * Multi-Vehicle Physical Crash Reconstruction from Video2.

## **Part 12 — Recommended Literature Set**

The following curated list represents the foundational standards, landmark papers, and state-of-the-art frameworks driving this analysis:

> * **ASAM e.V.**, "ASAM OpenSCENARIO User Guide," Specification Document, 2021\. *Official standard defining entity dynamic XML structures*1.  
> * **Fremont, D. J., et al.**, "Scenic: A Language for Scenario Specification and Data Generation," *Machine Learning*, 112(4), pp. 1–45, Springer, 2022\. DOI: 10.1007/s10994-021-06120-5. *Landmark probabilistic DSL paper*13.  
> * **Kim, S., et al.**, "DriveFuzz: Discovering Autonomous Driving Bugs through Driving Quality-Guided Fuzzing," *Proc. ACM CCS*, 2022\. DOI: 10.1145/3548606.3560558. *State-of-the-art fuzzing framework*17.  
> * **ISPRS Archives**, "Topological Consistency Verification of OpenDRIVE Road Networks for Autonomous Driving Simulation," *ISPRS Archives*, XLIX-B4-2026, pp. 417–424, 2026\. *Definitive OpenDRIVE topological graph analysis*4.  
> * **HASCO Contributors**, "HASCO: Hybrid AI Simulation Compiler for Driving Scene Synthesis," *OASIcs*, Vol. 143, 2026\. *State-of-the-art hybrid LLM-compiler paper*7.  
> * **Deng, Y., et al.**, "Txt2Sce: Generating Test Scenarios in OpenSCENARIO Format Based on Textual Accident Reports," *arXiv preprint arXiv:2509.02150*, 2025\. *Direct natural-language-to-OpenSCENARIO baseline*8.  
> * **Viswanadha, K., et al.**, "Parallel and Multi-Objective Falsification with Scenic and VerifAI," *International Conference on Runtime Verification (RV)*, 2021\. *Formal evaluation rulebooks*19.  
> * **SERA Authors**, "SERA: Self-Evolving Scenario Repair and Recommendation for Autonomous Driving Systems," *arXiv preprint arXiv:2505.22067*, 2025\. *Closed-loop LLM scenario repair*11.  
> * **Li, M., et al.**, "ScenarioNet: Open-Source Platform for Large-Scale Traffic Scenario Simulation and Modeling," *Advances in Neural Information Processing Systems (NeurIPS)*, 36, 2024\. *State-of-the-art scenario database platform*40.  
> * **Zhong, Z., et al.**, "Guided Conditional Diffusion for Controllable Traffic Generation (CTG)," *IEEE ICRA*, 2023 / arXiv:2210.17366. *State-of-the-art trajectory diffusion model*18.

## **Architectural Challenge, Unknown Unknowns, and Direct Synthesis**

### **Critical Challenge to the Phase-1 Architecture**

An exhaustive review of literature challenges several abstraction boundaries in the Phase-1 design:

> 1. **Unjustified Separation of Component C1 (User Request) and Component C2 (Scenario Understanding)**: Literature demonstrates that requirement ingestion and semantic intent extraction operate as a tightly coupled cognitive loop2. Merging C1 and C2 into a unified *Scenario Intent & Ingestion Capability* eliminates redundant data conversions and prevents contract mismatches1.  
> 2. **Component C3 (Scenario Knowledge) as a Static Knowledge Base vs Dynamic Execution Capability**: Literature (such as HASCO) indicates that knowledge retrieval cannot remain a passive document store7. C3 should be split into a static *Standard Schema Base* and an active *Simulator Execution Compatibility Matrix*1.  
> 3. **Deterministic Boundary Encroachment in Component C6 (Scenario Validation)**: While schema checks are strictly deterministic, physical plausibility verification and reachability analysis require reasoning over kinematics and map topologies4. Treating C6 as purely deterministic understates the need for algorithmic reachability solvers1.  
> 4. **Cross-Cutting Concerns Deserving Top-Level Architectural Status**: Provenance tracking and execution orchestration are currently treated as cross-cutting concerns1. Literature shows that without an explicit, first-class *Provenance Engine*, closed-loop feedback in Component C9 cannot trace failure root causes back to original requirement interpretations1.

### **Identification of "Unknown Unknown" Research Opportunities**

Experiments across simulation literature reveal critical points where formal correctness fails to guarantee behavioral success:

> * **Simulator Implementation Drift**: Identical OpenSCENARIO XML files executed across different build versions of esmini or CARLA produce diverging vehicle trajectories due to unstandardized internal step interpolation algorithms1.  
> * **Silent Trigger Mismatches**: Triggers evaluating relative distance between entities exhibit floating-point threshold skips when simulation step sizes (![][image6]) are set too large, causing collision actions to fail silently1.  
> * **Repair Loop Amplification**: Automated LLM repair prompts attempting to fix off-road vehicle spawns often introduce secondary physical implausibilities, such as instantaneous ![][image11] acceleration spikes1.  
> * **Metric Contradictions**: High-level semantic evaluation metrics (e.g., scenario criticality score) frequently disagree with low-level kinematic metrics (e.g., TTC), marking safe, routine merging maneuvers as high-risk edge cases1.

### **Direct Answers to Key Final Questions**

#### **What Part Is Already Well-Established Engineering?**

Converting structured parameters into OpenSCENARIO XML using libraries like scenariogeneration, parsing XML schemas against ASAM XSD files, invoking local esmini binary processes, calculating kinematic metrics (TTC, headway) from OSI trajectory logs, and storing artifacts in versioned databases are fully mature engineering tasks1.

#### **What Part Reproduces Existing Research?**

Using an LLM to parse natural language text into JSON slots reproduces recent work like Chat2Scenario and Txt2Sce8. Utilizing RAG over standard documentation to improve code output reproduces HASCO7. Applying evolutionary mutation based on TTC metrics reproduces DriveFuzz17.

#### **What Part Combines Existing Ideas in a New Way?**

The primary architectural synthesis—combining an LLM intent parser, a strongly-typed simulator-independent semantic IR, an OpenDRIVE topological graph verifier, a deterministic Python AST compiler, and an esmini preflight dry-run validator into a unified closed-loop feedback pipeline—combines isolated research concepts into a robust compiler-style testing framework1.

#### **What Part Could Plausibly Constitute a Genuine Research Contribution?**

Three explicit capabilities represent genuine research contributions:

> 1. **Static Pre-Execution Trigger Reachability**: Formulating a static analysis engine that evaluates OpenSCENARIO conditional state machines against vehicle kinematic envelopes to detect deadlocks prior to simulation1.  
> 2. **Explicit Standard-to-Simulator Execution Mapping**: Establishing a machine-readable capability matrix that translates standard-compliant OpenSCENARIO features into esmini-executable subsets during compilation1.  
> 3. **Diversity-Preserving Closed-Loop Scenario Repair**: Designing a multi-objective repair loop that couples LLM reflection with sequence-level diversity metrics (SCD/UBD) to prevent diversity collapse during failure repair1.

#### **What NOT to Spend Research Time On**

> * Do not write a custom OpenSCENARIO XML string serializer from scratch; utilize the established scenariogeneration Python package (xosc/xodr)6.  
> * Do not develop custom 3D rendering engines or integrate CARLA during Phase 1; focus strictly on headless esmini execution1.  
> * Do not train unconstrained text-to-XML neural networks; compiler-style intermediate generation completely outperforms end-to-end neural generation in schema compliance2.

#### **Which 3–5 Research Areas to Investigate Deepest Before Implementing Phase 1**

> 1. **Intermediate Representation (IR) Schema Design (Component C4)**: Define a strongly-typed schema (using Pydantic or JSON Schema) that captures spatial relationships, dynamic maneuvers, state-machine triggers, and safety criteria independently of OpenSCENARIO XML syntax1.  
> 2. **OpenDRIVE Topological Graph Validation (Component C6)**: Implement a directed graph reachability verifier using network adjacency matrices to check lane connectivity and junction links before running simulation files1.  
> 3. **Closed-Loop Repair Contracts (Component C9)**: Formulate the feedback payload schema connecting C8 evaluation diagnostics to C9 repair prompts, incorporating explicit diversity loss terms to ensure repaired scenarios remain distinct and non-trivial1.

#### **Works cited**

> 1. trajectories.md  
> 2. An LLM-driven Scenario Generation Pipeline Using an Extended Scenic DSL for Autonomous Driving Safety Validation \- arXiv, [https://arxiv.org/html/2602.20644v1](https://arxiv.org/html/2602.20644v1)  
> 3. Components\_break\_down\_automated\_scenario development.md  
> 4. Topological Analysis of OpenDRIVE Models for Advanced Autonomous Vehicle Simulations, [https://isprs-archives.copernicus.org/articles/XLIX-B4-2026/417/2026/isprs-archives-XLIX-B4-2026-417-2026.html](https://isprs-archives.copernicus.org/articles/XLIX-B4-2026/417/2026/isprs-archives-XLIX-B4-2026-417-2026.html)  
> 5. esmini user guide, [https://esmini.github.io/](https://esmini.github.io/)  
> 6. ML-SceGen: A Multi-level Scenario Generation Framework \- arXiv, [https://arxiv.org/html/2501.10782v1](https://arxiv.org/html/2501.10782v1)  
> 7. HASCO: A Hybrid AI Simulation Compiler for Semantic Accident Reconstruction \- DROPS, [https://drops.dagstuhl.de/storage/01oasics/oasics-vol143-aeic2026/OASIcs.AEiC.2026.4/OASIcs.AEiC.2026.4.pdf](https://drops.dagstuhl.de/storage/01oasics/oasics-vol143-aeic2026/OASIcs.AEiC.2026.4/OASIcs.AEiC.2026.4.pdf)  
> 8. \[2509.02150\] Txt2Sce: Scenario Generation for Autonomous Driving System Testing Based on Textual Reports \- arXiv, [https://arxiv.org/abs/2509.02150](https://arxiv.org/abs/2509.02150)  
> 9. Chat2Scenario: Scenario Extraction From Dataset Through Utilization of Large Language Model This work was supported by the National Key R\&D Program of China under Grant Nr. 2022YFE0117100, and by the FFG in the research project PECOP (FFG Projektnummer 893988), as part of the “Bilateral Cooperation Austria \- People's Republic of China / MOST 2nd Call” program. Corresponding author \- arXiv, [https://arxiv.org/html/2404.16147v2](https://arxiv.org/html/2404.16147v2)  
> 10. Risk Scenario Generation for Autonomous Driving Systems based on Causal Bayesian Networks \- arXiv, [https://arxiv.org/html/2405.16063v1](https://arxiv.org/html/2405.16063v1)  
> 11. From Failures to Fixes: LLM-Driven Scenario Repair for Self-Evolving Autonomous Driving, [https://arxiv.org/html/2505.22067v1](https://arxiv.org/html/2505.22067v1)  
> 12. Reinforcement Learning for Testing Interdependent Requirements in Autonomous Vehicles: An Empirical Study \- arXiv, [https://arxiv.org/pdf/2502.15792](https://arxiv.org/pdf/2502.15792)  
> 13. Scenic: a language for scenario specification and data generation \- ResearchGate, [https://www.researchgate.net/publication/358283053\_Scenic\_a\_language\_for\_scenario\_specification\_and\_data\_generation](https://www.researchgate.net/publication/358283053_Scenic_a_language_for_scenario_specification_and_data_generation)  
> 14. Trajectory and Planner Repair for Automated Vehicles to Comply With Traffic Rules \- mediaTUM, [https://mediatum.ub.tum.de/doc/1771312/1771312.pdf](https://mediatum.ub.tum.de/doc/1771312/1771312.pdf)  
> 15. Deriving Scenario-Aware Driving Requirements from Traffic Laws and Regulations \- arXiv, [https://arxiv.org/html/2604.24562v1](https://arxiv.org/html/2604.24562v1)  
> 16. Automated Generation of Test Scenarios for Autonomous Driving Using LLMs \- MDPI, [https://www.mdpi.com/2079-9292/14/16/3177](https://www.mdpi.com/2079-9292/14/16/3177)  
> 17. SimADFuzz: Simulation-Feedback Fuzz Testing for Autonomous Driving Systems \- arXiv, [https://arxiv.org/html/2412.13802v1](https://arxiv.org/html/2412.13802v1)  
> 18. \[2210.17366\] Guided Conditional Diffusion for Controllable Traffic Simulation \- arXiv, [https://arxiv.org/abs/2210.17366](https://arxiv.org/abs/2210.17366)  
> 19. arXiv:2107.04164v1 \[cs.AI\] 9 Jul 2021, [https://arxiv.org/pdf/2107.04164](https://arxiv.org/pdf/2107.04164)  
> 20. Txt2Sce: Scenario Generation for Autonomous Driving System Testing Based on Textual Reports \- arXiv, [https://arxiv.org/html/2509.02150v1](https://arxiv.org/html/2509.02150v1)  
> 21. A Survey on the Application of Large Language Models in Scenario-Based Testing of Automated Driving Systems \- arXiv, [https://arxiv.org/html/2505.16587](https://arxiv.org/html/2505.16587)  
> 22. From Virtual Environments to Real-World Trials: Emerging Trends in Autonomous Driving, [https://arxiv.org/html/2603.17714v1](https://arxiv.org/html/2603.17714v1)  
> 23. Trustworthy Autonomous System Development \- Weizmann Institute of Science, [https://www.weizmann.ac.il/math/harel/sites/math.harel/files/users/user56/trustworthy%20autonomous%20systems.pdf](https://www.weizmann.ac.il/math/harel/sites/math.harel/files/users/user56/trustworthy%20autonomous%20systems.pdf)  
> 24. Survey on Scenario-Based Safety Assessment of Automated Vehicles \- OPUS, [https://opus4.kobv.de/opus4-hs-kempten/files/703/Survey\_on\_Scenario-based\_Safety\_Assessment.pdf](https://opus4.kobv.de/opus4-hs-kempten/files/703/Survey_on_Scenario-based_Safety_Assessment.pdf)  
> 25. EPTCS 395 Formal Methods for Autonomous Systems \- CSE CGI Server, [https://cgi.cse.unsw.edu.au/\~eptcs/Published/FMAS2023/Proceedings.pdf](https://cgi.cse.unsw.edu.au/~eptcs/Published/FMAS2023/Proceedings.pdf)  
> 26. Bridging Simulation and Usability: A User-Friendly Framework for Scenario Generation in CARLA \- arXiv, [https://arxiv.org/html/2507.19883v1](https://arxiv.org/html/2507.19883v1)  
> 27. TM-fuzzer: fuzzing autonomous driving systems through traffic management \- ResearchGate, [https://www.researchgate.net/publication/382623296\_TM-fuzzer\_fuzzing\_autonomous\_driving\_systems\_through\_traffic\_management](https://www.researchgate.net/publication/382623296_TM-fuzzer_fuzzing_autonomous_driving_systems_through_traffic_management)  
> 28. Trace and Pace: Controllable Pedestrian Animation via Guided Trajectory Diffusion \- CVPR, [https://cvpr.thecvf.com/virtual/2023/poster/22261](https://cvpr.thecvf.com/virtual/2023/poster/22261)  
> 29. SceneStreamer: Continuous Scenario Generation as Next Token Group Prediction \- arXiv, [https://arxiv.org/html/2506.23316v2](https://arxiv.org/html/2506.23316v2)  
> 30. Semantic-guided fuzzing for virtual testing of autonomous driving systems \- OUCI, [https://ouci.dntb.gov.ua/en/works/7AKdEp1l/](https://ouci.dntb.gov.ua/en/works/7AKdEp1l/)  
> 31. SimADFuzz: Simulation-Feedback Fuzz Testing for Autonomous Driving Systems, [https://www.researchgate.net/publication/387184732\_SimADFuzz\_Simulation-Feedback\_Fuzz\_Testing\_for\_Autonomous\_Driving\_Systems](https://www.researchgate.net/publication/387184732_SimADFuzz_Simulation-Feedback_Fuzz_Testing_for_Autonomous_Driving_Systems)  
> 32. Field Testing of ADAS Technologies in Naturalistic Driving Conditions \- MDPI, [https://www.mdpi.com/2624-8921/7/4/135](https://www.mdpi.com/2624-8921/7/4/135)  
> 33. Survey of Model-Based Security Testing Approaches in ... \- SciSpace, [https://scispace.com/pdf/survey-of-model-based-security-testing-approaches-in-the-2z3vzo83.pdf](https://scispace.com/pdf/survey-of-model-based-security-testing-approaches-in-the-2z3vzo83.pdf)  
> 34. esmini/release\_notes.md at master \- GitHub, [https://github.com/esmini/esmini/blob/master/release\_notes.md?plain=1](https://github.com/esmini/esmini/blob/master/release_notes.md?plain=1)  
> 35. Scenario Metrics for the Safety Assurance Framework of Automated Vehicles: A Review of Its Application \- MDPI, [https://www.mdpi.com/2624-8921/7/3/100](https://www.mdpi.com/2624-8921/7/3/100)  
> 36. Simulation-Based Testing, Validation, and Training with Probabilistic Programming \- EECS at Berkeley, [https://www2.eecs.berkeley.edu/Pubs/TechRpts/2023/Archive/EECS-2023-214.pdf](https://www2.eecs.berkeley.edu/Pubs/TechRpts/2023/Archive/EECS-2023-214.pdf)  
> 37. Reinforcement Learning for Testing Interdependent Requirements in Autonomous Vehicles: An Empirical Study \- arXiv, [https://arxiv.org/html/2502.15792v2](https://arxiv.org/html/2502.15792v2)  
> 38. Safety-Critical Scenario Generation Via Reinforcement Learning Based Editing | Request PDF \- ResearchGate, [https://www.researchgate.net/publication/382986182\_Safety-Critical\_Scenario\_Generation\_Via\_Reinforcement\_Learning\_Based\_Editing](https://www.researchgate.net/publication/382986182_Safety-Critical_Scenario_Generation_Via_Reinforcement_Learning_Based_Editing)  
> 39. RCG: Safety-Critical Scenario Generation for Robust Autonomous Driving via Real-World Crash Grounding \- arXiv, [https://arxiv.org/html/2507.10749](https://arxiv.org/html/2507.10749)  
> 40. Traffic Scene Generation from Natural Language Description for Autonomous Vehicles with Large Language Model \- arXiv, [https://arxiv.org/html/2409.09575v2](https://arxiv.org/html/2409.09575v2)  
> 41. CaDRE: Controllable and Diverse Generation of Safety-Critical Driving Scenarios using Real-World Trajectories \- arXiv, [https://arxiv.org/html/2403.13208v1](https://arxiv.org/html/2403.13208v1)  
> 42. Generating Critical Scenarios for Testing Automated Driving Systems \- arXiv, [https://arxiv.org/pdf/2412.02574](https://arxiv.org/pdf/2412.02574)  
> 43. Text2Scenario: Text-Driven Scenario Generation for Autonomous Driving Test \- arXiv, [https://arxiv.org/html/2503.02911v1](https://arxiv.org/html/2503.02911v1)  
> 44. ScenarioNet: Open-Source Platform for Large-Scale Traffic Scenario Simulation and Modeling | OpenReview, [https://openreview.net/forum?id=uHlKNCDAJb](https://openreview.net/forum?id=uHlKNCDAJb)  
> 45. SimGen: Simulator-conditioned Driving Scene Generation \- arXiv, [https://arxiv.org/html/2406.09386v2](https://arxiv.org/html/2406.09386v2)  
> 46. \[2101.06557\] TrafficSim: Learning to Simulate Realistic Multi-Agent Behaviors \- ar5iv \- arXiv, [https://ar5iv.labs.arxiv.org/html/2101.06557](https://ar5iv.labs.arxiv.org/html/2101.06557)  
> 47. Tree-Based Scenario Classification: A Formal Framework for Coverage Analysis on Test Drives of Autonomous Vehicles | Request PDF \- ResearchGate, [https://www.researchgate.net/publication/372285995\_Tree-Based\_Scenario\_Classification\_A\_Formal\_Framework\_for\_Coverage\_Analysis\_on\_Test\_Drives\_of\_Autonomous\_Vehicles](https://www.researchgate.net/publication/372285995_Tree-Based_Scenario_Classification_A_Formal_Framework_for_Coverage_Analysis_on_Test_Drives_of_Autonomous_Vehicles)  
> 48. Scenario Metrics for the Safety Assurance Framework of Automated Vehicles: A Review of Its Application \- ResearchGate, [https://www.researchgate.net/publication/395608848\_Scenario\_Metrics\_for\_the\_Safety\_Assurance\_Framework\_of\_Automated\_Vehicles\_A\_Review\_of\_Its\_Application](https://www.researchgate.net/publication/395608848_Scenario_Metrics_for_the_Safety_Assurance_Framework_of_Automated_Vehicles_A_Review_of_Its_Application)  
> 49. Prof. Dr.-Ing. Matthias Althoff \- Professur für Cyber-Physical Systems \- Department of Computer Engineering, [https://www.ce.cit.tum.de/cps/members/prof-dr-ing-matthias-althoff/](https://www.ce.cit.tum.de/cps/members/prof-dr-ing-matthias-althoff/)  
> 50. Multi-modal Traffic Scenario Generation for Autonomous Driving System Testing \- NSF PAR, [https://par.nsf.gov/servlets/purl/10618376](https://par.nsf.gov/servlets/purl/10618376)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAaCAYAAADWm14/AAABrElEQVR4Xu2UyytFURSHlzxjIImJEeURkoEYCAMDSgaYiAkpoUz8AWYU5dE1USbeeeaRiYlkIqZGRqSQ8kjMFH7rrvNYZ7tcN3dgcL766uzf2neffdbZ5xL5+Pj4/DNKYS1MtMYZsMIt/5o0WAVjjTwOJhlZkHi4BudgAJ7BQTgDt+C4OzUs1XAD7sEVo3YCx4wsyAhsta4T4Ac8gunwDR5YtXDwE+/DZJKb36laHsm6XSpzmFDXReROjIEDMF/Vf6IEdpC0+h7Oq1oPybph1+ojmZhtFiKgnmSNBpWtwls1/pZNeGWGETINX0nOlg2/Dt7EF7hdw7CZ5B0+wkVVb7FqNnxGctU4FMfkPTeFJB3pVZlDDUmRW99oXfOhZFJJvgLepM0sfIftKjPZgadqzB3hdQtU5pAJd+EknIJN8JLkR9uw2Jkp9MMHuGDkGr7RBVwi+bz5QF57ZoRAHzr+s8hSYxPe9LIZKrhzDK/Jf0pPJA8XNdpgpxlacGdeyH1tQ/CZZNNRgZ/uEKYYuc05yU2ZbngD69zy3ymD5WaoqCQ5U+twFOZ4yz4+Xj4BKRtJe7THAFIAAAAASUVORK5CYII=>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABIAAAAWCAYAAADNX8xBAAAAaklEQVR4XmNgGAWjYOBAIboAuWAhEKuiC5IDrIF4G7oguSAbiNPQBYWAWIoMvBSI10LZYNAJxMvJwCeB+B8Q1zNQAFSAeC8DJLzIBhxAfAWIZdAlSAUpQFyMLkgO2A/ELOiC5ABJdIFhDACathTb12UQNgAAAABJRU5ErkJggg==>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAFIAAAAWCAYAAABT5cvhAAAAp0lEQVR4Xu3VIQ9BURjG8VeSJEESFLOxmcCuQDKib6SqikhRBHODmc1sPoAv5W8nedM5p97nt/3Leeo955qJiIiIVFKD6v5Q0g3pRRtquk0S1WhNb9pR+3+WHAt60JF6bpMME7rShcZukwx9OtGd5m6TRL83s6SP6Q+fpUsHetLSbRJhRGcLX+HUbRJhRjcLb+LAbRJhZeH67qnjNolU0JZafhARqbAvJ44SAq45YocAAAAASUVORK5CYII=>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAD0AAAAZCAYAAACCXybJAAADTklEQVR4Xu2XWahNURjHP0PmcM1zlyKEJAkPHHMiGbs8iOTBVGYhMjyQmVJkvMqQSDIUEiVDXhApSl1KHgwpQ0Lh/7/fWvd8Z529j3uSk3udX/0e1v+us/dea6/17XVF8uTJ849SPwwqOwPghjDMlipwNNwIp8C2qX8uowOcJ3rDUcHfcslB2DMMs6EVvApXic7gPvhFdPCWQfAFnA8Hw2vwZEqP3FAb3g7DbNkJ38K+rl0DfofvRW9AqsGXcIlrk0bwI5xmslzAl7E8DLNlC/wJp7p2LfgNfoJ1XDbG9enl2p6boqskl1yE7cIwW6rCjqbdX3SAJ0zG1cCsvcnIOfgVVg9yT3eYEK0XpCEcBnuI1hHSAA4X7fs7Wkj0JPNaA+Fc0ecfCWum9MgAB38f3oWFJj8mOuiWJiOnXN48yAkngiuBk8Ltw21wHi4VrQ387QjRQSyDt+AD0a0Ux0I4I8i4zR6JXn8I3C/6TE1spzj2wMfwtaTP+mWJHhwLGfMuQW45AH/AvSabI/q7e5J843z7zIp8pwhYwMLvMwvrWdPm9UqknIP2DBUtUKtNdkn0gbi8LH7QnYLc4rdGZ5NNctlMk3EVMVtjMks3if5a8Dk5qbwPvyosxLxXphUTCWeUD9DVtY+6duuyHsppl3OJxbFdtE89k01wGfeyh6uI2VqTWTZJsjZYCuAN0d9SvjBug4xwefDAYTkiegEeVghvyHa4jK/Az5JcolFsE/2t//yRcS5jUfM0ddk6k3lYbLkVogom3yz/3geugA9Fr5MwfVIolOQM8ZDiue6y2a6dcG0WHssTeCbIQnZI+qDHu8wOupnL1pvMw2W7KwwdPJ2xgHk4MSUSPXmlsKyzkh43WV34zumXM/cHKyT3jYf7mCc31oBM8ITHwfBNeia7bKzJ2rhsq8k8h2HvMHQUwwuib5tw1T2DE32HKPjwfGO74WJ4Bz6V9LMtDwTP4SG4SPTC4VHVwmXHCeUe+yA6iQtEV8Ybl1HWi5XwlWuzP6/t4QrhJzSOYtHawonhVuL5YrNk3nKlsAM/UxwE/6mIg0unn2j1Db/ZfwuuCk5KHPYzGhbaCgtPfX987KxINBY9GP1XzILTw7Cyw0HbQ02ePOXkF4Q9q9/tL/smAAAAAElFTkSuQmCC>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACIAAAAZCAYAAABU+vysAAACOElEQVR4Xu2VT0hWQRTFr2mh2R8xAxPKTypEiwgT1AhdVMuWWUIJQYnQIgSxTS0iWrSN0MwIktIUFxLUqoUg1iYKImgRYUoGraJF9M/Ic7z3fcy7vsyvXfAO/ODNmfvm3Zm5M08kVar/UKvAEXAFdIEt8e6/qgAcBpdAi+h4OWsNGAMPQTPoAXOgKQxaRlVgGlwQff8R6I5FrFCd4CNYG3hcmTeiM11OG8ArcNLaq8F38CIbkYOegwfOOwR+gwPO9xoC7yWeMFfjaNBekUpEP3jH+XXmX3S+1ycwbs8VEl/VUJvBadAKqkW3MKadoh/sd/4u8/ucH2q7aMw9MAwGwCy4DfKDONYcV+4gOAPegutB/6JYkEkfrDF/xPmhODvGfAW15hWJFnqvtVkzrL+91qZOSUIijaKD3XB+lAhn8iedFY157Pz74BsoBcXgM3gJOsA2UAh2ZKNNNDgYlzXUbvOvOT8UC5IxN51/y/yoYE+Irho9MgUqrS+rdWBelm7BftGXzjs/VL0kJ8tJ0T9ubd5TZaBNNMkfYML6YpoAT53HQTjYnsBj5YdLmgc+gLuBR7FwuTXchq1gMt69eHp+ScIddQx8ET1+kQZladbT4CfIBB5vUyaz0doc/B24au2M6IRYi5HaRS/BRF0Gr8E50Rk+Eb01Q7FwOQC3MxL/KaPgmeh/hkeTd9J668+AGdEjzS1kPbGYG6w/UeWiR5JHmscuF3ELueT7nM/7ZJM9Mzk/uVSpUv2TFgCrJG7dnhB+fwAAAABJRU5ErkJggg==>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABkAAAAaCAYAAABCfffNAAABbElEQVR4Xu2UvytFYRjHvwhXJBkog0EpsxRlM2AzKcXEIKVEMdgsfkyKDDIZWKzKzyxyUyZKfmQwGPAPCIXv43nvPec8556T4RrofOpT932+73ufe85z7gES/hr9tNUW80kDfaeXtNBkeWONvtBP2muyKMbppC1GUU+v6CC0yTktCOwIU05f6ZwNolihQ7SI3kEb9QR2hOmC7uu2QS7q6DUtdmtpJofPsjuC1NJGukw/aDN0nrEs0mHfWprdI/pXrtJ96Pye6B7dCOww1NAbWmLqI9AmJ6aeQebxRmdtkIt5OmqLpJQ+QBt1mEzohGYyl1iq6S1N2cAxBv2iIxtAr0D+UxU2sMzQCVv0UQa959Ko3WRpempqISqhVyH3No4paJMdXy0zjwW3rqJLXuwxTR/pIT2APi3ylOwaj6FNxJbvk0CTWw+49Tptc5+zyFCf4R3+qVtyGPom2KYXdJP2ufqvIK8ieUMkJPw3vgD3QVFmffjvFwAAAABJRU5ErkJggg==>

[image7]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADQAAAAWCAYAAACPHL/WAAAAqklEQVR4Xu3VIQsCQRCG4RFFTYJgEUyCTfCqSbALZovNYtdmMVqMBtvZrHaToD/E/+F7bJqpplnmhafclzbcrkgURVGUeT37wWsTlLijZTZXzfDADWOzuamGBZ64YKhnP9Wxwgsn9PXspyY2eOOArp79NcUXO7TN5rbqIFt8sEdHz35rYC3pPzpKRu9OddMtJd10Zwz07Lu5pLfoipHZXFdIepeyuTii6M9+9uwSC4XlSdwAAAAASUVORK5CYII=>

[image8]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAAAaCAYAAAAHfFpPAAADTklEQVR4Xu2XWahNYRTHl3kmY2aZhzwpkoQioojIlEgyJ4kyhgfTg8KDMfMcL8iD4UXKnAeFEroPJCEyZMzw/7f2Zp119t5nn3tL59T51a9z91r7nv2d71vfsEVKlCgRQUNYyweLiFY+kA8t4W3YwCeKiENwog+moQa8Caf7RJHRAr6B/X0iF5vhHVjJJwqYIfCwD4KlsAxW84k46sMPsJ9PFDjX4A0fBNXhYzjHJ+JYCO/7YIFTF/6Am3wiYDW854NxXIZnfNDQGo6EjYJrrheDRHs6X/qKzlMPf1AaWK2d4BT4G86GnSW73CfDX7Cpi0fyRHQNiGI5vBR8voSL4Fm4Ed4196WB83UV/Al7mPgo+F30x+ViHrwIX4hWAP+mfvvrI9pBY1w8iyqiD4+aL8PhLnPNOccVNtwuP8OaJp/EWLgYdhNt2FyTOw6fmes0sC3XfdDAauVz5vuEp53ojYN9AqyUzBJ6BY8Ef08QXYXTsl70gMUK4vM6mhwr64S5zkUd0UFjFSbxFq7xQU8v0QbxMwmWLO+r6DmBZw1utyHdRb83qgLjGCr6P8N8wvEUrvNBT3vRLxvnE44Fovd18Ik8aC76HStMjHOaMXZEWjaIzv+khTOc2jN9wlNPtAHLfAJME91OyDn43OQ4dXwJsnOS1gSOGJ81wMROiU4BC+cvOysOzv1b5no/rGquCdvCZ6Wapvxhe12MW9xX0QY2g1/k30Mri5652wbXhJXEbeeRiXnC6TYiuO4K38OTf+9QyuBH2MXFQ9hhYXtnwSUmFxJOk1QVexBecTHCHWAPPAoHim6XvD4vuqpbuIU9hJ8kc4HzbIUP4E7RkWQj+SMsXBDZATNcPITV+g7uFl1co+DUYuf6yoiE8/+1RJcvSzF8PebIc6ST2CHxI8fpxu/gJ6uK04tV5vdwMl6yO8bC3SlpDdgHt/lgHGwUR4/bXkXgi9QFHwzoKXpu4IsKaSw6QnFHWY5urs6OgzvWN4kfiEh41GXZRY1GWrjH2wOOZZLoIYoV1QZehadhbXtTQG94zAfzgCfX7T6YBh5Tw4NOeeCPj3ud5ll9i+hucgBOzUxnwEMWK6Q8jBbtXP9ukJq1sIkPFhE8IxRz+0uU+F/8AYfnmYEVi8t2AAAAAElFTkSuQmCC>

[image9]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAsAAAAXCAYAAADduLXGAAAAzklEQVR4XmNgGAWDHvADsTa6IBDwoguAwBkgXo0mVgPE19HEGMSA+D8Ql6KJ3wDiFWhiDGEMEMVmSGJSULFsJDEwmA7En4CYBUkshgGiWA9JDAxA1u1AE5sDxO+BmAlZUJIBYkIHsiAQ3AXiLVD2fJhgJANE8WIonxGI+6FibQwQZ0yByjHMBOIfQPwIiOcC8WYGSKjMAOKXQLwRiGVgim8C8TYGiIkqQMwFk2CAhAjc0zD3lsGl8QBY+JqgS2ADFQwQZ6AEDz7AjC6ADQAAqOMkz9JY7ScAAAAASUVORK5CYII=>

[image10]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAC4AAAAZCAYAAABOxhwiAAAB+klEQVR4Xu2Vu0sdURCHx0SMEtRYKCiS0s5CCwuFiOCDWIUgaqEI4gMRbQUDIRIQQlqxUUGMD0gghSAWvq5v0EbQwn/AXhNtxNdvMq7Mzl3XvULE4nzwwd2ZPffM7s45h8jhcDx7MmEX/A57Ya4//SS8gA3wG+yDRf50PAVwB/bADngAT+EHfdN/JhUuwa+wGc7CKziob7LEYIu6zoYX8Oz291PwBY7Alyq2B69hrYrdwZ/nnOTp8lR8mWRQm4oFkQNf26AiCb61wQAWSeZrVLHPt7FJFfMxDOdgsonxoFYVC6IELsAMmyB5KeOwycSD4Hm2SdrWo56khgkVe5BdknaJ0iqVJO32RsW4aJ6wU8UShTcKLvyjTdxHFcmAUZsIgceskRTPRf8g2aUeC7+wY7gP00wukHR4CH/DFJN7iGqS4qdgt8klyjRJHfk2EQT3+DwcI//qjgqP50XNE2aZXCJ8ImnVKG36Dy6YN3+PQlihrsPgon+StEc5XCV/z0eFt2XeYfjLM9wmfLbcywDJaaXph3UmFoQu2oOLXyE5kaNSA3/BVypWCofUtQ9+or8kE/GnjsEteELy1sPglpqB7TYB3pH8X5Tii+EfuEFygsbgOjwiOdHj4E/B2x7vItZLkqM4jPfkP3UtZRRtoW5S/PyevOgdDofDEc8NUaZfQEN7g30AAAAASUVORK5CYII=>

[image11]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAFAAAAAZCAYAAACmRqkJAAAEGUlEQVR4Xu2Ya6gVZRSGl1pqlqVWdjVPYUk3CYNuRFmJaVG/ysoiMdQKijCiflRURFFQEZF2MYIipVAkjLQiRMwSfyhdKcrMQA2hoCtd6PY+rJnOmnX27LOLfY7Q2S88sOedb2bPXt/3rbVmm3UUdYi4VVwp9k3nOupFh4tFYoJ4WGwVwyojOmqqO8S7xefh4kdxY/fpgauR2ajRUWJ6OP5azAnHA1arxT7Z7EUXi21idPJbUpeYnc0gZuoGcb+4MJ0rNVhcJO4TC8yT8+7QeLEim73oILFeHJlPNNOx4gGxSfwpXq2e/kfniC/FTeJcsUa8VBlhNlQsN7/HWeZVbYc4PQ7qJ90uLslmE+0tlpgHfpA4rXq6XqeIa8TJ4ldrHMAhYru4JXhjxA9WXbHXiV1iRPBYiZ+JPYLXH9poXhBaEc/2nJgmJovLxLWVES2qLoDkhb/Mbx7Fcn8zHG8WK8Mxmmp+7ZnJ70udKp7JZhPdZf6MkSlxQKuqC+Cj5jfNuYFgcQ0zOMp8DDMZRdDx70x+qQPMf/AF5n0Y2+c486rIPUudKGZYa5X1cXF2NqUDxVwxU0w0TzNtVV0AyQ0EIReEZYVP8j26+PxUZYTZ8YX/RPJL0S6QWxlzj3hZ3Gs+Eb+IM4rPT4u7xU9iFhfWaE/zfM5ERJGPl4rzxDzxuXmg26q6AL5u3YGKoojgU4goFI0CxTn8XHCieBNgDAE7ovCo5l+J38SlhYeorB+H4yzSDV1CFEElN58UPCauTwK4KpvSa+Y/8ODklwE8xrxq8fnJyojuADL7dSq3/4vJ/8h8dRLMUqxwxtaJXcF3RlFhvxPvi/nmk0SBIWW0VQSQ5jPrBfOHPiz5tCz4VGQehs+LKyPMTij8x5Ifxcs7Yx5K/gfineSxwusCyERQ2BrpKvGz+bXwtnnL0lbVBfBB8y/NM/uGeU4i39Dx/249tyo5jGtvS34UhYExfE/Ue9YzIAvNx+Ych1hd9KmNRI9KwbrCvEKTGtbGAe0QAWS7Zk0xf+jzk/+JVbv9tWJDOEaXm187KflR+1njALLlWClR/GvC2LitS9Hcj82mNE68lTyq8R/Wxv6URMusrLOeN6WRZjvRzpQi77El6PNK0YCyIg8N3vPW+0wznqCwuqKYICpqDBarh7H5HbdLvJK8Ul3m18S3i6vFh+H4P4v+izeFneL7AirWp+YroxSJd5t4VtwstphvhyxaEKokW4ncSQ5r9gclbzffmH8vbzYUDV4Vvyg84Nnw+M5vC49/TK63bvGXFBPYSF3m9+XZycW0RBQs+s9+FSuTdoW2IveEUVRrmlXGsrL7QxvFXtksxA7av/hMvm02oQNSvMf/m1e3jpIesT54LRsoosBQqRu1NR21IP4gmJ3Njjr6/+tvxCjbxu/1byYAAAAASUVORK5CYII=>