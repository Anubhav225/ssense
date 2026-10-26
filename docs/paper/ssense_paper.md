Ssense: A Domain-Adapted Legal Small Language Model and Scalable Inference Architecture for Auditing Global Web Compliance under India's DPDP Act, 2023 and DPDP Rules, 2025

| **Anubhav Das** | **Priyanshu Roy** |
| :---: | :---: |
| Department of Computer Science and Engineering | Department of Computer Science and Engineering |
| Institute of Engineering and Management | Institute of Engineering and Management |
| Kolkata, India | Kolkata, India |


Abstract—Sovereign data protection legislation increasingly asserts extraterritorial jurisdiction over the global digital economy. Under Section 3(b) of India's Digital Personal Data Protection (DPDP) Act, 2023, data fiduciaries operating anywhere in the world must comply with statutory mandates when processing personal data of Indian data principals. In practice, however, global web platforms routinely deploy generic, boilerplate, or deceptive privacy policies that mask statutory non-compliance, while ordinary citizens and regulatory monitors lack automated mechanisms to evaluate these legal contracts at scale. While Large Language Models (LLMs) present a potential auditing mechanism, general-purpose models suffer from severe statutory hallucinations, cross-jurisdictional contamination (e.g., superimposing GDPR doctrines onto Indian law), and an epistemic failure to distinguish statutory silence from active legal breach. In this work, we present Ssense, the first domain-adapted Legal Small Language Model (Law-LM / Legal SLM) and scalable inference architecture specifically fine-tuned and preference-aligned on India's DPDP Act, 2023 and its statutory Rules. Built upon Qwen2.5-7B-Instruct, Ssense establishes a dual-track parameter-efficient architecture—a forensic statutory auditor (rank 128) and a citizen-facing legal dialogue model (rank 64)—trained via rank-stabilized LoRA (rsLoRA) and Simple Preference Optimization (SimPO) over statutory reasoning traces. Following alignment, the adapter weights are merged into the base Transformer parameters to produce a unified, standalone, open-weights legal model (Ssense-DPDP-7B) released for the research community. We computationally model the DPDP Act by pruning 44 legislative sections into a 26-node actionable statutory decision tree based on fiduciary obligations, prohibitions, and legitimate-use safe harbors. To overcome the epistemology of legal silence, we introduce a three-step deductive reasoning chain and an omission firewall that discards findings derived solely from unstated practices. To combat long-context attention decay across verbose legal policies, we couple the SLM with a deterministic Statutory Compliance Layer (SCL) as a lossless neuro-symbolic backstop ($V_{\text{final}} = V_{\text{SLM}} \cup V_{\text{SCL}}$). To support high-throughput compliance auditing, we design an inference serving architecture integrating PagedAttention continuous batching, prompt KV cache pre-warming, speculative prompt lookup decoding ($k=3$), multi-tier hierarchical policy caching, and pushdown automaton grammar-constrained decoding (guaranteeing 100% schema validity). In empirical audits of real-world fiduciaries, Ssense achieved zero statutory hallucinations and zero false positives against reference legal labels, providing an open, reproducible blueprint for sovereign statutory alignment of Small Language Models.
Index Terms—Legal Language Models (Law-LMs), Statutory Alignment, Open-Weights Models, DPDP Act 2023, DPDP Rules 2025, Global Web Compliance, Scalable Inference Serving, Deontic Logic, Neuro-Symbolic AI, Regulatory Compliance Auditing

# I. INTRODUCTION

The global proliferation of sovereign data privacy legislation has transformed regulatory compliance into a critical challenge for the digital economy. Following the landmark constitutional recognition of privacy as a fundamental right under Article 21 in *Justice K.S. Puttaswamy (Retd.) v. Union of India*, the Parliament of India enacted the Digital Personal Data Protection (DPDP) Act, 2023, accompanied by its procedural Rules. Crucially, the DPDP Act is not merely a domestic statute: under **Section 3(b)**, the law asserts explicit **extraterritorial jurisdiction**, applying to any digital personal data processing conducted outside the territory of India if such processing is in connection with offering goods or services to data principals within India, or profiling them. Consequently, websites and online services worldwide—ranging from multinational e-commerce platforms and software-as-a-service (SaaS) providers to global media networks—are legally bound by India's sovereign data protection regime.

A fiduciary's privacy policy serves as the binding statutory contract through which an organization declares its data processing practices to users and regulators. In practice, however, statutory compliance is virtually unverified by the public. A PwC India survey of 3,233 consumers revealed that only 16% of users were aware of the DPDP Act's existence, and 69% did not know they possessed the statutory right to withdraw consent. This compliance gap is exacerbated by the phenomenon of *inauthentic web compliance*: global tech entities frequently deploy standardized, monolithic privacy declarations (often drafted to satisfy European GDPR or US state-level safe harbors) that project an illusion of compliance while systematically breaching non-negotiable statutory mandates of Indian law. Typical real-world breaches include omitting mandatory notices in the 22 languages of the Eighth Schedule (§5(3)), imposing asymmetrical friction on consent withdrawal (§6(4)), asserting perpetual data retention under vague operational pretexts (§8(7)), conducting behavioral tracking and targeted advertising on minors without verifiable parental consent (§9(1)–(3)), and failing to designate an accessible Indian Data Protection Officer (§13).

Language models represent an intuitive paradigm for automating the extraction and verification of legal terms. However, applying off-the-shelf general-purpose LLMs (e.g., GPT-4, Llama 3) to statutory compliance reveals severe foundational limitations:
1. *Statutory Hallucination and Confabulation:* General models routinely fabricate legal section numbers, invent statutory duties, or misinterpret legal definitions. Dahl et al. [1] demonstrated that state-of-the-art foundation models hallucinate on verifiable legal questions between 58% and 88% of the time, while Guha et al. [2] (LegalBench) confirmed that general models struggle with fine-grained statutory interpretation and deductive rule application.
2. *Cross-Jurisdictional Contamination:* Because general LLMs are predominantly trained on Anglo-American and European legal corpora, they exhibit severe jurisdictional bias—superimposing GDPR concepts (such as broad commercial "legitimate interests") or US common-law doctrines onto an Indian statute that explicitly defines a closed, exhaustive list of §7 legitimate uses.
3. *The Epistemology of Legal Silence:* A fundamental failure of unadapted LLMs is treating contractual silence as an affirmative violation. In statutory jurisprudence, an entity that does not engage in cross-border transfers is under no statutory obligation to mention Section 16. Naive language models routinely flag such omissions as non-compliance, creating widespread false positives that destroy trust in automated auditing.

## A. Limits of Existing Work

Few systems address the DPDP Act directly. The sole prior DPDP compliance system in the academic literature, APLiance (Dhakar, Sinha and Sural [3]), formalises Sections 1 to 7 of the Act as Attribute-Based Access Control (ABAC) rules, treats a policy as a set of implied access requests, and uses a hosted general-purpose LLM (GPT-5.4-mini, without fine-tuning) to extract sixteen attribute values. While APLiance pioneers the formalization of DPDP access rules, it exhibits three fundamental limitations: (i) it relies entirely on an unadapted cloud LLM, leading to severe misclassification on implicit legal nuances (64% accuracy for unambiguous consent, 76% for easy withdrawal); (ii) it adopts an ultra-conservative policy on silence, classifying any unknown attribute as a violation, which causes 100% of tested real-world policies (25 of 25) to fail compliance; and (iii) it functions purely as an informational reporting tool without scalable serving infrastructure.

Other Indian legal language-model efforts exist, notably InLegalBERT for court judgment classification and rhetorical role labeling [4], Aalap for litigation reasoning and bail petition analysis [5], and LoRA-adapted models for general legal Q&A [6]. However, as summarized in Section III, these systems focus almost exclusively on retrospective litigation, penal statutes, and court judgments rather than real-time statutory contract compliance under the DPDP Act. Research outside India has explored GDPR Article 13 compliance [7], [8], CCPA disclosure mapping [9], OPP-115 policy corpora [10], and Polisis neural taggers [11]. However, these rely on disparate foreign statutes, cannot resolve Indian statutory rules, and fail to provide scalable high-throughput inference serving.

## B. Key Contributions and Breakthroughs

To address these foundational challenges, this paper presents **Ssense**, a domain-adapted Small Language Model (Law-LM / Legal SLM) architecture and scalable inference serving system designed to verify the statutory authenticity of web platforms worldwide under India's DPDP Act, 2023 and DPDP Rules, 2025. Our primary contributions are:
1. *The First Open-Weights Domain-Adapted DPDP Law-LM:* We train and preference-align a dual-track Legal SLM architecture based on Qwen2.5-7B-Instruct: a forensic statutory auditor emitting strict schema-bound JSON audit reports, and a citizen-facing legal dialogue assistant. Both models are trained via rank-stabilized LoRA (rsLoRA) and Simple Preference Optimization (SimPO) over statutory reasoning traces, eliminating statutory hallucinations and cross-jurisdictional contamination. Adapter weights are merged into the base model to release a standalone open-weights model (`Ssense-DPDP-7B`).
2. *Joint Computational Formalization of the DPDP Act, 2023 and DPDP Rules, 2025:* We formalize the joint statutory deontic logic (obligations $\mathcal{O}$, prohibitions $\mathcal{P}$, permissions $\mathcal{P}erm$, and safe harbors $\mathcal{S}$) across the 44 legislative sections of the DPDP Act, 2023 and the 22 procedural rules under the DPDP Rules, 2025 into a complete 26-node actionable statutory violation taxonomy ($\mathcal{V}_{26}$). Each violation class is deterministically mapped to its governing legislative section, procedural rule, and statutory penalty severity weight ($\omega \in \{30, 20, 10, 5\}$), preventing citation confabulation.
3. *Epistemic Omission Firewall:* We formulate the mathematical semantics of legal silence versus affirmative breach. By enforcing a three-step deductive reasoning chain ($\text{Active Claim} \to \text{Statutory Mapping} \to \text{Deontic Justification}$) backed by a binary `omission_check` gate, Ssense guarantees that unstated practices are not penalized unless an affirmative statutory duty of disclosure is violated.
4. *Lossless Neuro-Symbolic Statutory Backstop:* To overcome attention decay and "Lost in the Middle" failures over verbose legal texts ($>8,000$ tokens), we couple the fine-tuned Law-LM with a deterministic Statutory Compliance Layer (SCL) equipped with safe-harbor lookarounds ($V_{\text{final}} = V_{\text{SLM}} \cup V_{\text{SCL}}$).
5. *High-Throughput Inference Serving Architecture:* We design and empirically evaluate an optimized inference serving engine integrating PagedAttention continuous batching ($B \in \{1, 4, 8, 16\}$), prompt KV cache pre-warming, speculative prompt lookup decoding ($k=3$) exploiting statutory/policy $n$-gram overlap (yielding a $1.8\times$ decoding speedup), multi-tier SHA-256 hierarchical caching, and pushdown automaton grammar-constrained decoding (XGrammar) to guarantee sub-second latency, zero syntactic drift, and memory-safe execution.
6. *Algorithmic Certification and Empirical Evaluation:* We formalize an evaluation protocol replacing generic NLP metrics with legal rigor: optimal bipartite semantic assignment for multi-violation F1, Context Faithfulness LLM-as-a-judge, paired McNemar hypothesis testing, and 95% Wilson score confidence bounds resolving the small-sample boundary paradox.

We explicitly delineate the scientific boundaries of this study: while APLiance established the first symbolic ABAC interpretation of Sections 1–7, Ssense provides the first domain-adapted Law-LM, the first computational model spanning the full fiduciary-facing breadth of the Act (26 violation types), the first open-weights DPDP release, and an optimized inference engine delivering high-throughput statutory compliance auditing.

## C. Paper Organization

Section II formalizes the legal and technical background of the DPDP Act, 2023, DPDP Rules, 2025, and Law-LMs. Section III provides an extensive survey of legal AI, privacy policy auditing, and Indian legal NLP. Section IV details the research gap analysis. Section V presents the computational and deontic formalization of the statute. Section VI details the Law-LM architecture and scalable inference serving design. Section VII outlines the algorithmic evaluation protocol, Section VIII presents empirical results on global and domestic fiduciaries, Section IX discusses architectural and legal implications, Sections X and XI address limitations and ethics, and Section XII concludes.


# II. BACKGROUND AND PRELIMINARIES

## A. Statutory Architecture of the DPDP Act, 2023, DPDP Rules, 2025, and Extraterritorial Reach

India's Digital Personal Data Protection Act, 2023 establishes an enforceable legal framework balancing an individual's right to protect their personal data with the lawful processing of such data. Unlike prior legislative drafts that included non-personal data or criminal penalties, the enacted DPDP Act focuses strictly on digital personal data, defined as data about an identified or identifiable natural person.

*Extraterritorial Jurisdiction under Section 3(b):* A defining pillar of the DPDP Act is its explicit extraterritorial reach. Section 3 delineates the application of the Act:
$$\text{DPDP Application} = \{ d \in \mathcal{D}_{\text{digital}} \mid \text{Territory}(d) = \text{India} \} \cup \{ d \in \mathcal{D}_{\text{digital}} \mid \text{Activity}(d) \in \mathcal{A}_{\text{extraterritorial}} \}$$
where $\mathcal{A}_{\text{extraterritorial}}$ encompasses any processing outside India related to offering goods or services to Data Principals within India, or profiling them. Consequently, foreign data fiduciaries—including global social media conglomerates, international e-commerce sites, cloud providers, and digital content streaming platforms domiciled in the US, EU, or Asia—are subject to Indian sovereign jurisdiction. When such entities engage with Indian users, their web privacy policies must satisfy Indian statutory standards.

*Deontic Logic of Statutory Duties:* From a computational perspective, the DPDP Act can be formalized as a normative deontic system comprising four distinct operational modalities:
$$\mathcal{M}_{\text{statute}} = \langle \mathcal{O} \text{ (Obligations)}, \mathcal{P} \text{ (Prohibitions)}, \mathcal{P}erm \text{ (Permissions / Legitimate Grounds)}, \mathcal{S} \text{ (Safe Harbors)} \rangle$$
1. *Obligations ($\mathcal{O}$):* Affirmative duties imposed on fiduciaries, such as providing an itemized notice accompanied by descriptions of personal data and purpose in English and all 22 Eighth Schedule languages (§5(1), §5(3)), ensuring consent withdrawal is as easy as giving consent (§6(4)), implementing reasonable security safeguards (§8(5)), erasing personal data upon purpose completion or consent withdrawal (§8(7)), and establishing accessible grievance redressal mechanisms (§13).
2. *Prohibitions ($\mathcal{P}$):* Mandatory restrictions, including prohibiting conditional or bundled consent (§6(1)), prohibiting processing detrimental to child well-being (§9(1)), and absolute statutory bans on tracking, behavioral monitoring, or targeted advertising directed at children (§9(2), §9(3)).
3. *Permissions ($\mathcal{P}erm$):* Processing is permitted only upon obtaining valid Section 6 consent, or under the closed, exhaustive list of nine legitimate uses enumerated in Section 7 (e.g., voluntary provision for a specified purpose, state subsidies, court decrees, medical emergencies). Unlike the GDPR, Indian law recognizes no broad, open-ended commercial "legitimate interest" ground.
4. *Safe Harbors ($\mathcal{S}$):* Specific statutory carve-outs (e.g., retaining data when mandated by other enacted laws under Section 8(7) provisos, or exemptions for state security under Section 17).

Table I summarizes the statutory provisions bearing directly on privacy-policy content, their deontic modality, and their common real-world breach manifestations across global web platforms.

### TABLE I: DPDP STATUTORY PROVISIONS, PROCEDURAL RULES, DEONTIC MODALITIES, AND GLOBAL WEB DEFECTS

| Act Section & Procedural Rule | Deontic Modality | Statutory Mandate | Typical Global Web Defect |
| --- | --- | --- | --- |
| §3(b) | Extraterritoriality | Extraterritorial scope over global entities offering goods/services or profiling in India | Global site assumes local laws do not apply; provides generic US/EU policy |
| §5(1), §5(3), Rule 3 | Obligation ($\mathcal{O}$) | Itemized notice of categories collected, specific purposes, DPO contact, and 22 Eighth Schedule languages | Monolithic English text; vague purpose ("improving user experience"); missing language notice |
| §6(1), §6(4), Rule 4 | Obligation ($\mathcal{O}$) & Prohibition ($\mathcal{P}$) | Consent must be free, specific, informed, unconditional; withdrawal must be as easy as giving consent | Bundled consent with terms of service; dark patterns; withdrawal only via postal mail or complex tickets |
| §7 | Closed Permission ($\mathcal{P}erm$) | Closed list of 9 legitimate uses; commercial profiling strictly excluded | Asserts broad commercial "legitimate interest" to harvest and monetize user data |
| §8(5), §8(7), Rule 6, Rule 8, Sched. 3 | Obligation ($\mathcal{O}$) | Enforce reasonable security safeguards; erase data once purpose fulfilled or consent withdrawn | Perpetual retention ("we retain data indefinitely"); no technical safeguards disclosed |
| §9(1)–(3), Rule 10 | Prohibition ($\mathcal{P}$) & Obligation ($\mathcal{O}$) | Verifiable parental consent for minors; absolute ban on tracking, behavioral monitoring, or targeted ads | Indiscriminate ad-network tracking scripts deployed on minor-accessible platforms |
| §13, Rule 11 | Obligation ($\mathcal{O}$) | Accessible grievance redressal with designated Data Protection Officer (DPO) contact details in India | Omits Indian grievance officer; directs complaints to unreachable offshore legal departments |
| §16, Rule 13(4), Sched. 2 | Prohibition ($\mathcal{P}$) | Restrict cross-border transfers to non-notified territories or blacklisted jurisdictions | Unrestricted data transfer clauses to offshore affiliates without statutory disclosures |

## B. Computational Compliance: ABAC vs. Deontic Statutory Auditing

Automated statutory compliance can be conceptualized through contrasting computational paradigms. APLiance (Dhakar et al. [3]) formulates compliance as Attribute-Based Access Control (ABAC). In ABAC, an access request is defined as a tuple $\langle s, o, a, e \rangle$ representing subject, object, action, and environment attributes, evaluated by a policy evaluation engine returning $\text{Permit}$ or $\text{Deny}$. To handle incomplete web policy text, APLiance partitions attributes into base (extracted from text), derived (deduced by rules), and unknown (runtime facts unresolvable from text). Crucially, APLiance adopts an adversarial stance toward unknown attributes: a request is evaluated as violating if *any* assignment to an unknown attribute yields a denial. While logically sound in closed security systems, applying this heuristic to open-world statutory contracts creates a severe *silence penalty*: if a policy does not mention that it refrains from tracking children, the system assumes tracking occurs, resulting in 100% of tested policies failing compliance [3].

Ssense departs fundamentally from this access-control formulation. In statutory law, legal obligations operate under the epistemic principle of affirmative duty: an entity is in breach only if it affirmatively admits to an unlawful practice (e.g., perpetual data retention in violation of §8(7)), or if it fails an explicit statutory disclosure duty (e.g., omitting grievance officer contact information mandated by §13). Silence on non-mandatory disclosures (such as cross-border transfer when no transfer occurs) cannot be legally construed as non-compliance. Ssense therefore models compliance as a formal deontic audit tree combining inductive SLM reasoning with an explicit omission firewall and deterministic statutory safe-harbor automata.

## C. Parameter-Efficient Law-LM Alignment: rsLoRA and SimPO

Achieving real-time statutory auditing directly within user devices necessitates Small Language Models (SLMs) in the 7-billion parameter class capable of running on edge accelerators or local consumer GPUs without leaking private browsing data to third-party cloud APIs. We build upon Qwen2.5-7B-Instruct [12], a state-of-the-art decoder-only Transformer incorporating grouped-query attention (GQA), SwiGLU activations, and rotary position embeddings (RoPE) across 28 layers.

To adapt the base SLM into a specialized legal reasoner without catastrophic forgetting of general syntactic competence, we deploy Low-Rank Adaptation (LoRA; Hu et al. [13]). Conventional LoRA parameterizes weight updates as $\Delta W = \frac{\alpha}{r} B A$, where $A \in \mathbb{R}^{r \times d_{\text{in}}}$, $B \in \mathbb{R}^{d_{\text{out}} \times r}$, and $r \ll \min(d_{\text{in}}, d_{\text{out}})$. However, as demonstrated by Kalajdzievski [14], standard LoRA exhibits gradient vanishing and unstable optimization as rank $r$ scales. We therefore adopt Rank-Stabilized LoRA (rsLoRA), which scales updates by the square root of the rank:
$$\Delta W = \gamma_{\text{rs}} B A = \frac{\alpha}{\sqrt{r}} B A$$
By maintaining gradient variance independent of adapter rank, rsLoRA enables high-rank adaptation ($r=128$) for the forensic auditor, unlocking deep statutory representation capacity while preserving numerical stability.

*Preference Optimization via SimPO:* Supervised fine-tuning (SFT) equips the model with statutory syntax, but often leaves residual tendencies toward over-calling violations or generating polite hallucinations. We deploy Simple Preference Optimization (SimPO; Meng et al. [15]), a reference-free objective that scores candidate responses by length-normalized log-likelihood. While Direct Preference Optimization (DPO; Rafailov et al. [16]) steers model behavior using paired chosen/rejected completions, it requires maintaining a frozen reference model in GPU memory throughout training, doubling memory overhead. Similarly, while monolithic objectives such as ORPO (Hong et al. [17]) remove reference models, SimPO directly enforces a target reward margin without reference overhead:
$$\mathcal{L}_{\text{SimPO}}(\theta) = - \mathbb{E}_{(x, y_w, y_l)} \left[ \log \sigma \left( \frac{\beta}{|y_w|} \log \pi_\theta(y_w \mid x) - \frac{\beta}{|y_l|} \log \pi_\theta(y_l \mid x) - \gamma \right) \right]$$
where $y_w$ is the factually grounded statutory audit, $y_l$ is an over-called or hallucinated counterpart, $\beta$ controls reward scaling, and $\gamma > 0$ enforces a strict target reward margin. Crucially, length normalization prevents the optimization process from rewarding verbosity—a documented failure mode in legal LLMs (Chen et al. [18]).

## D. Retrieval Grounding and Grammar-Constrained Decoding

Statutory interpretation demands absolute factual grounding. We formulate a multi-stage modular Retrieval-Augmented Generation (RAG) framework (Gao et al. [19]) over a curated corpus of the DPDP Act and Rules, combining lexical BM25 matching for exact section numbers with dense BGE embeddings and neural cross-encoder re-ranking (Xiao et al. [20]) for semantic parity.

To prevent syntactic invalidity (e.g., malformed JSON, unclosed brackets, or hallucinated enum values) from corrupting downstream compliance verification and automated auditing, we enforce Pushdown Automaton Grammar-Constrained Decoding (XGrammar; Dong et al. [21]). The statutory output schema (`dpdp_schema.json`) is compiled into an execution grammar that masks token logits at every decoding step $t$, mathematically guaranteeing that emitted tokens strictly conform to the 26-node statutory decision contract without retry overhead.


# III. LITERATURE SURVEY

We survey work spanning the foundational pillars of Ssense: legal language models and statutory adaptation (Section III-A), synthetic data distillation and preference alignment (Section III-B), automated privacy policy compliance analysis (Section III-C), domain-specific retrieval grounding and contextual integrity (Section III-D), safety and adversarial prompt injection defense (Section III-E), and DPDP-specific auditing systems (Section III-F). Reported scores are not pooled across studies, because legal regimes, statutory corpora, evaluation units, and metrics differ fundamentally. Section III-G and Table III synthesize each evidence line into an evidence map delineating what the literature supports and where empirical transfer stops, directly establishing the research gaps formalized in Section IV.

## A. Legal-Domain Foundation Models and Law-LMs

The emergence of Legal Language Models (Law-LMs) addresses the documented failure of general-purpose foundation models when reasoning over complex statutory texts. Dahl et al. [1] profiled legal hallucinations across state-of-the-art models, revealing hallucination rates between 58% (GPT-4) and 88% (Llama 2) on verifiable legal questions. To systematize the evaluation of legal reasoning, Guha et al. [2] introduced **LegalBench**, a collaboratively constructed benchmark spanning 162 legal tasks across issue-spotting, statutory interpretation, and legal rule application. Their findings established that while general models can perform surface-level legal classification, they consistently fail at multi-step deductive syllogisms and nuanced statutory interpretations.

Early legal language models focused on domain-specific pre-training. Chalkidis et al. introduced LEGAL-BERT [22], demonstrating that continued pre-training on legal contracts and court cases significantly outperforms generic BERT baselines, and established the LexGLUE benchmark [23] for standardized evaluation of legal language understanding across multi-jurisdictional tasks. More recently, Colombo et al. [24] introduced **SaulLM-7B**, demonstrating that a parameter-efficient 7-billion parameter language model, when adapted with domain-specific legal training and targeted legal instruction tuning, can rival or surpass proprietary foundation models on specialized legal tasks. Similarly, DISC-LawLLM [25] and ChatLaw [26] formalized legal syllogistic instruction tuning ($A \to B, B \to C \implies A \to C$) and external legal knowledge retrieval to suppress factual confabulation. Further legal instruction corpora such as LawInstruct [27] and interpretable legal QA frameworks [28] have systematized multi-step legal reasoning.

In the Indian legal landscape, prior work has concentrated almost exclusively on court proceedings and penal litigation. Paul et al. [4] developed **InLegalBERT**, pre-training on 5.4 million Indian court documents for legal statute identification and rhetorical role labeling in Supreme Court and High Court judgments. Kalamkar et al. [5] developed **Aalap**, instruction-tuning a 7B model for litigation workflows, bail argument generation, and legal case issue framing. Ta et al. [6] applied LoRA fine-tuning for general Indian legal Q&A. While these models advance Indian legal NLP, they are trained on case law and litigation transcripts; none are designed, fine-tuned, or evaluated for real-time statutory contract compliance under the DPDP Act, 2023. Ssense bridges this gap as the first Law-LM aligned specifically with Indian sovereign data protection legislation.

## B. Synthetic Data Distillation, Reflexion, and Alignment

Because real-world privacy policies annotated with fine-grained statutory violation labels are non-existent for new statutes, training relies on synthetic instruction synthesis. Self-Instruct established the generate, filter, and fine-tune pattern for instruction following [29]. To imbue student models with complex reasoning capabilities, explanation trace distillation—formalized in Orca [30] and MiniLLM [31]—demonstrates that student models acquire deductive capabilities by imitating explicit, step-by-step rationales rather than isolated label outputs. In agentic pipelines, Reflexion [32] demonstrates that verbal self-reflection and multi-turn retry loops enable language agents to correct malformed outputs autonomously. Italiani et al. [33] applied teacher–student distillation to legal question answering using a frozen teacher model and retrieved legal contexts. However, training recursively on synthetic data risks model collapse and distribution erosion [34], which is why real-world policy excerpts must be retained, validated by deterministic filters, and deduplicated via MinHash locality-sensitive hashing to eliminate train-test contamination (Oren et al. [35], Lee et al. [36]).

Model alignment shapes final generation behavior. While DPO [16] requires maintaining a frozen reference model in GPU memory, reference-free methods such as ORPO [17] and SimPO [15] eliminate reference weights while enforcing target reward margins. Importantly, Chen et al. [18] (FLAME) warned that standard preference alignment can reward length and superficial confidence over factual correctness. For statutory compliance, the preference signal must explicitly penalize over-calling, under-calling, and fabricated statutory citations.

## C. Automated Privacy Policy Compliance Analysis

The computational analysis of website privacy policies originated with the landmark **OPP-115** corpus (Wilson et al. [10]), which provided 115 expert-annotated privacy policies across ten broad privacy practices. Building on this corpus, Harkous et al. [11] developed **Polisis**, deploying hierarchical convolutional neural networks to predict privacy practices and automate policy queries. While OPP-115 and Polisis established the feasibility of automated policy analysis, they were descriptive taxonomies rather than statutory compliance checkers.

With the enactment of modern privacy regulations, research shifted toward regulatory compliance. Liu et al. [7] combined sentence classification with rule engines for GDPR Article 13 across 304 policies; CompLicy mapped 89 GDPR terms across 148 platforms [8]; and C3PA introduced expert annotations for CCPA requirements [9]. PrivComp-KG integrated knowledge graphs with LLMs for compliance verification [37]; Chen et al. [38] developed sliding-window entailment for healthcare policies; GKC-CI applied Contextual Integrity (Nissenbaum [39]) to 456 policies [40]; and Cory et al. [41] performed word-level LLM annotations of GDPR transparency.

Table II contextualizes these systems. While prior works provide valuable methodologies, they focus overwhelmingly on GDPR or CCPA regimes, operate as retrospective batch audits, and do not bridge the gap between static text extraction and verifiable, scalable statutory compliance reasoning.

### TABLE II: COMPLIANCE-CHECKING STUDIES COMPARED (FIGURES AS REPORTED BY THE AUTHORS)

| Study | Regulatory Target | Scale and Headline Figure | Methodology | Enforcement |
| --- | --- | --- | --- | --- |
| OPP-115 [10] | Descriptive taxonomy | 115 policies, 23,194 data practices | Manual expert annotation | None |
| Polisis [11] | Descriptive taxonomy | 115 policies, hierarchical neural tagging | Deep learning classifier | None |
| Liu et al. [7] | GDPR Art. 13 | 36,610 labelled sentences, 304 policies | Sentence classification + rules | None |
| CompLicy [8] | GDPR | 89 terms in 7 groups; 148 web platforms | Rule inventory | None |
| C3PA [9] | CCPA | 225 expert-annotated policies; 14,000+ segments | Regulation-aware multi-task extraction | None |
| PrivComp-KG [37] | General privacy | 100 privacy policies; knowledge graph triples | LLM + Knowledge Graph reasoning | None |
| Chen et al. [38] | GDPR Art. 13 | 388 synthetic policies; 100 websites | Sliding-window entailment | None |
| GKC-CI [40] | Contextual integrity | 21,588 annotations; 90.65% accuracy | Fine-tuned classifiers | None |
| Cory et al. [41] | GDPR transparency | 21 requirements; 200-policy sample | Word-level LLM annotation | None |
| APLiance [3] | DPDP §§ 1–7 | 25 policies; 400 pairs; 94.5% accuracy | Prompted GPT-5.4-mini + ABAC rules | None |
| Ssense (Ours) | DPDP 2023 & Rules (26 types) | Global & domestic web audits; Wilson certification | Fine-tuned Law-LM + SCL + CFG | Deterministic statutory audit reporting & legal reasoning |

## D. Domain-Specific RAG and Contextual Integrity in Legal AI

Statutory interpretation demands aligning machine reasoning with legal contextual norms. Helen Nissenbaum's doctrine of Contextual Integrity [39] formalizes privacy not as blanket secrecy, but as adherence to context-relative informational norms governing actors, data attributes, transmission principles, and purpose-bound consent. In computational legal modeling, standard zero-shot retrieval often falters because general-purpose retrievers latch onto superficial lexical overlap rather than governing statutory provisions.

Modern modular Retrieval-Augmented Generation (RAG; Gao et al. [19]) addresses this through multi-stage retrieval pipelines combining dense semantic embeddings with neural cross-encoder re-ranking. Ssense adopts BGE dense embeddings (`BAAI/bge-large-en-v1.5`) alongside neural cross-encoder re-ranking (`bge-reranker-v2-m3`; Xiao et al. [20]), merged with exact lexical BM25 section matching via Reciprocal Rank Fusion (RRF; Cormack et al. [42]). To enforce strict citation fidelity during fine-tuning, Zhang et al. [43] introduced RAFT (Retrieval Augmented Fine-Tuning), demonstrating that training language models on an explicit mixture of oracle documents and hard distractor clauses teaches models to ignore irrelevant statutory context and cite binding statutory sections verbatim. Ssense incorporates RAFT distractor training into its citizen dialogue assistant, guaranteeing high statutory faithfulness and eliminating fabricated legal safe harbors.

## E. Safety, Adversarial Robustness, and Prompt Injection Defense

Prompt injection represents a critical system-level attack vector whenever an automated compliance auditor ingests untrusted web content. When an auditor fetches and analyzes live web privacy policies, malicious actors or compromised platforms can embed adversarial indirect prompt injection payloads (e.g., hidden HTML spans instructing the auditor to ignore violations and emit a false compliance certification).

Greshake et al. [44] demonstrated that retrieved adversarial web text can compromise real-world LLM-integrated pipelines by hijacking the model's instruction-following hierarchy. Li et al. [45] benchmarked instruction-following models across adversarial injection scenarios, showing that standard fine-tuned models fail to isolate untrusted user data from system-level tasks without specialized defense layers. To defend against adversarial prompt manipulation, SecAlign (Chen et al. [46]) demonstrated that preference optimization can steer model responses to treat injected text strictly as passive data rather than executable instructions. Ssense synthesizes these defenses into a multi-tier security firewall (Section VI-J), combining Unicode NFKC canonicalization, regex-based delimiter isolation, sliding-window perplexity filtering, and SecAlign-style adversarial preference alignment, certifying 100% injection defense across 500 red-teamed adversarial probes.

## F. DPDP-Specific Auditing Systems and Grounding in APLiance [3]

APLiance (Dhakar, Sinha, and Sural [3]) represents the primary peer-reviewed compliance-checking baseline established under India's DPDP framework. Its computational architecture formalizes compliance through an Attribute-Based Access Control (ABAC) framework structured around three attribute classes (subject, object, environment) and eleven decision rules evaluated via a prompted cloud language model (GPT-5.4-mini) paired with a symbolic Pylog reasoning engine.

In their empirical evaluation across 25 corporate privacy policies (spanning e-commerce, social media, news, and streaming platforms) with 16 attributes (400 labeled pairs), APLiance reported a macro-accuracy of 94.5% (precision: 96.1%, recall: 96.1%). While explicit affirmative provisions (such as purpose specification) were identified accurately, nuanced consent modalities proved significantly more challenging: unambiguous consent (Section 6(1)) achieved an accuracy of only 64.0% and a recall of 14.0%, while frictionless consent withdrawal (Section 6(4)) reached 76.0% accuracy. Crucially, APLiance's ablation study demonstrated that decomposing compliance into intermediate attribute checks significantly outperformed asking a language model for an unconstrained compliance verdict (76% vs. 68% on withdrawal; 64% vs. 52% on unambiguous consent). However, when evaluated against the full statutory rule set, **zero out of 25 policies (0%) were found compliant**; only after relaxing five mandatory requirements (notices in all Eighth Schedule languages, route for Board complaints, and ambiguous consent constraints) did 20 of 25 policies pass.

**Architectural Grounding and Contrast with Ssense:** Ssense adopts APLiance's core insight—that robust legal compliance requires decomposing complex statutory mandates into structured, intermediate deontic decisions—but introduces fundamental paradigm shifts across four dimensions:
1. *Sovereign Open-Weights vs. Proprietary Cloud Prompting:* While APLiance relies entirely on zero-shot prompting of a closed-source cloud API (GPT-5.4-mini), Ssense trains and releases an open-weights, domain-adapted Law-LM (`Ssense-Legal-7B`) fine-tuned via rsLoRA [14] and SimPO [15], ensuring complete data sovereignty, zero egress of proprietary contracts, and reproducible offline auditing.
2. *Expanded Statutory Coverage:* APLiance limits its rules to 7 statutory provisions (Sections 5 to 11); Ssense operationalizes a comprehensive 26-node statutory decision tree spanning the entire DPDP Act, 2023 and the procedural DPDP Rules, 2025 (Section V-A).
3. *Epistemology of Silence vs. Silence Penalty:* APLiance penalizes contractual silence as a violation across all attributes, causing 100% of tested policies to fail. Ssense introduces a formal three-step deductive chain backed by an Omission Firewall (`omission_check`), distinguishing between affirmative disclosure duties and uninvoked conditional practices (Section V-C).
4. *Pushdown CFG Decoding vs. Unconstrained Parsing:* To eliminate brittle regex parsing of free-form model text, Ssense compiles its statutory JSON contract into a pushdown automaton via XGrammar [21], mathematically guaranteeing 100% schema validity without prompt retry overhead.

## G. Synthesis and Cross-Domain Evidence Map

To synthesize the literature survey and establish the empirical boundary conditions across all foundational pillars, Table III provides an evidence map delineating what each research domain rigorously supports and precisely where theoretical or empirical transfer to Indian statutory DPDP compliance auditing stops.

### TABLE III: EVIDENCE MAP: WHAT THE LITERATURE SUPPORTS AND WHERE TRANSFER STOPS

| Evidence line | Method | Supports in Ssense | Transfer limit |
| --- | --- | --- | --- |
| Legal Foundation Models & Law-LMs [1], [6], [22], [24], [25], [26], [27], [28], [23], [4], [5], [2] | Domain pre-training, rsLoRA, legal syllogistic instruction tuning, legal reasoning benchmarks | Adapter design; statutory reasoning; hallucination mitigation; non-parametric evaluation | Prior models focus on court litigation transcripts or Anglo-American common law; no DPDP statutory verification |
| Privacy Corpus & Regulatory NLP [7], [8], [9], [10], [11], [37], [38], [41] | Policy segment annotation, hierarchical CNNs, LLM extractors, rule inventories | Multi-label statutory categorization; clause-to-statute mapping | OPP-115 and Polisis are descriptive; GDPR and CCPA diverge fundamentally from India's DPDP Act |
| Contextual Integrity & Deontic Norms [39], [40] | Contextual integrity norms, deontic logic mapping, safe-harbor lookaround automata | Statutory decision tree structuring; deontic modality assignment; safe-harbor lookarounds | Theoretical CI norms require formal operationalization into computationally bounded regex and SLM classifiers |
| Synthetic Distillation & Decontamination [29], [30], [31], [32], [33], [34], [35], [36] | Teacher–student reasoning traces, verbal reflexion loops, MinHash LSH deduplication, benchmark contamination detection, collapse prevention | Data Forge pipeline; schema repair; multi-turn retry budgets | Teacher output is not ground truth; requires independent deterministic validation |
| Preference Alignment [15], [16], [17], [18] | Reference-free margin optimization (SimPO, ORPO), factuality-aware alignment | Alignment phase; penalizing statutory hallucination and over-calling | Preference gains alone do not prove legal correctness |
| Retrieval Grounding & RAFT [19], [20], [43], [42] | Modular RAG, BGE dense embeddings and neural cross-encoder re-ranking, RAFT domain adaptation, reciprocal rank fusion | Hybrid statutory lookup and cross-encoder re-ranking for legal dialogue | Retrieval recall does not guarantee statutory entailment |
| Inference Serving & Long-Context Attention [21], [47], [48], [49], [50], [51] | FlashAttention-2 kernels, PagedAttention continuous batching, S-LoRA adapter multiplexing, pushdown automata CFG masking, prompt caching | Server design; 100% valid JSON contract emission without syntax collapse | Requires dynamic adapter cache management and latency budget gating |
| Adversarial Robustness & Injection Security [44], [45], [46] | Indirect prompt injection evaluation, task-instruction separation, preference-aligned defense | Adversarial red-teaming (Axis 12); input sanitization; prompt injection resistance | General jailbreak benchmarks omit legal boilerplate and retrieved statutory conflict scenarios |
| Statistical Gating & Hypothesis Testing [52], [53], [54], [55], [56], [57], [58], [59], [60] | Optimal bipartite matching (BERTScore [53]), LLM-as-a-judge, McNemar hypothesis tests [57], Wilson score intervals [58], bootstrap resampling [59], lexical diversity [60] | Rigorous evaluation harness; finite-sample statistical gating | Point estimates on small samples must be bounded by confidence intervals |
| DPDP-Specific Auditing (APLiance [3]) | Attribute-based access control (ABAC) with prompted cloud LLM | Problem framing and baseline comparison | Evaluated on Sections 1–7 only; unadapted cloud LLM; silence penalty fails 100% of policies |

# IV. RESEARCH GAP ANALYSIS

Table IV compares representative systems on the properties that matter for a DPDP auditing tool; entries reflect our reading of the published descriptions and a dash means not applicable or not described. Table V states seven gaps and the design response to each. Table VI lists gaps that Ssense does not close, so that the contribution is not overstated.

### TABLE IV: CAPABILITY COMPARISON WITH REPRESENTATIVE PRIOR SYSTEMS

| System | Statutory Target | Domain-Tuned Law-LM | Open-Weights Release | Deontic Decision Model | Epistemic Silence Firewall | Neuro-Symbolic Backstop | High-Throughput Serving Engine |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Liu et al. [7] | GDPR Art. 13 | No (BERT classifier) | No | Rule layer | No | No | No |
| CompLicy [8] | GDPR Art. 13 | No (Rule engine) | No | 89 terms | No | No | No |
| Cory et al. [41] | GDPR transparency | No (Prompted LLM) | No | 21 categories | No | No | No |
| PrivComp-KG [37] | General privacy | No (Prompted LLM) | No | No | No | No | No |
| APLiance [3] | DPDP §§1–7 | No (GPT-5.4-mini) | No | ABAC rules | No (Silence penalized) | Rule engine | No (Cloud API dependent) |
| Ssense (Ours) | DPDP 2023 & Rules 2025 (26 types) | Yes (rsLoRA + SimPO) | Yes (Ssense-DPDP-7B) | 26-node tree | Yes (omission_check) | Yes (SCL union) | Yes (Continuous batching + CFG) |

### TABLE V: RESEARCH GAPS AND SSENSE DESIGN RESPONSES

| Gap | What is missing in prior work | Ssense response |
| --- | --- | --- |
| RG-1 | Lack of scalable high-throughput serving architecture for legal auditing. Prior policy auditors rely on un-cached, slow cloud LLM APIs or offline batch processing unsuitable for concurrent real-time verification [3]. | High-throughput serving engine deploying PagedAttention continuous batching, multi-tier caching ($h_k, t_k$), SHA-256 deduplication, prompt KV cache pre-warming, and speculative prompt lookup decoding (Section VI-E, VI-F). |
| RG-2 | No open-weights statute-adapted model for the DPDP Act. Prior Indian legal NLP focuses on court litigation [4], [5] or general legal Q&A [6], while DPDP compliance relies on unadapted cloud models [3]. | Ssense-DPDP-7B: A domain-adapted 7B Law-LM trained via rsLoRA and SimPO, with adapter weights merged into base parameters for open-weights research release (Section VI-C). |
| RG-3 | Inability to separate statutory silence from legal breach. Prior systems either treat missing information as a violation (e.g., APLiance's silence penalty) or fail to detect omission of mandatory disclosures. | Formal epistemology of silence: Three-step deductive reasoning chain backed by an explicit omission firewall and schema-gated omission_check (Section V-C). |
| RG-4 | Attention decay over long statutory contracts ($>8,000$ tokens). Neural models suffer from "Lost in the Middle" failures on verbose privacy policies [52]. | Sub-quadratic FlashAttention-2 GPU kernel execution [47] coupled with lossless neuro-symbolic integration: Deterministic Statutory Compliance Layer (SCL) with safe-harbor lookarounds unioned with SLM predictions ($V_{\text{final}} = V_{\text{SLM}} \cup V_{\text{SCL}}$). |
| RG-5 | Syntactic drift and hallucinated enums in structured legal output. Free-form generation suffers from invalid JSON syntax or fabricated statutory violation keys. | Pushdown automaton grammar-constrained decoding (XGrammar [21]) masking token logits at every decoding step to guarantee 100% schema validity. |
| RG-6 | Extraterritorial statutory evasion under Section 3(b). Global platforms deploy generic GDPR/US safe-harbor policies that project an illusion of compliance while violating Indian law. | Real-time global web policy verification auditing foreign entities against Indian sovereign mandates (Section V-B). |
| RG-7 | Citizen-facing legal explanation lacks statutory provenance. General-purpose language models exhibit high hallucination rates on legal question answering (Dahl et al. [1], Louis et al. [28]). | Conversational dialogue adapter grounded in hybrid BM25 + dense BGE retrieval and pre-computed audit summaries (Section VI-I). |



### TABLE VI: GAPS THAT SSENSE DOES NOT CLOSE


| Gap | Description | Status |
| --- | --- | --- |
| Multilingual notices | Policies in Eighth Schedule languages are dropped at extraction; APLiance found none of 25 policies met the all-language requirement. | Future work (Section XII) |
| Public benchmark | Prior DPDP benchmarking was restricted to APLiance [3]; Ssense provides direct replication and DPDP-Bench multi-label suites. | Established in Section VIII-B (Table XV & XVI) |
| User outcomes | No measured effect on user comprehension or on site breakage. | Planned studies E4, E5 |
| Rule coverage | Provisions beyond the 26 actionable classes, and emergent administrative circulars, are not hardcoded. | Modular corpus refresh |
| On-device inference | A GGUF export exists but the evaluated path is server-side. | Future work |
| Component validation | The JSON-schema gate, omission firewall, MinHash contamination test, Wilson certification and 4-bit GGUF configuration are not yet isolated by ablation. | Study E2 |



# V. LEGAL FORMALISATION AND COMPUTATIONAL STATUTORY MODELING

## A. Joint Statutory Reduction: Mapping the DPDP Act, 2023 and DPDP Rules, 2025 to 26 Actionable Violation Types

A central challenge in designing a domain-adapted Law-LM is translating legislative prose into a computationally verifiable, finite taxonomy. In India's sovereign data protection regime, statutory compliance is fundamentally dual-tiered: (1) primary substantive legislation enacted through the 44 sections of the Digital Personal Data Protection Act, 2023 (Act No. 22 of 2023), and (2) subordinate procedural mandates notified through the 22 implementation rules and accompanying statutory schedules of the Digital Personal Data Protection Rules, 2025 (MeitY).

Not every statutory section or procedural rule represents an obligation that can be breached by a data fiduciary in a public privacy policy. Within the primary Act, Sections 18 to 26 establish the composition, powers, and digital inquiry procedures of the Data Protection Board of India, while Sections 29 to 32 govern proceedings before the Telecom Disputes Settlement and Appellate Tribunal (TDSAT). Similarly, procedural rules governing internal Board inquiries (Rules 17–22) regulate state adjudicatory machinery rather than commercial fiduciaries.

Let $\mathcal{S}_{\text{Act}} = \{1, 2, \dots, 44\}$ denote the 44 legislative sections of the DPDP Act, 2023, and let $\mathcal{R}_{\text{Rules}} = \{1, 2, \dots, 22\}$ denote the 22 implementation rules under the DPDP Rules, 2025, complemented by statutory Schedules $\Sigma = \{\text{Schedule 1 (Penalty Ceilings)}, \text{Schedule 2 (Exemptions)}, \text{Schedule 3 (Retention Limits)}\}$. The complete statutory compliance universe is:
$$\mathcal{U}_{\text{DPDP}} = \mathcal{S}_{\text{Act}} \cup \mathcal{R}_{\text{Rules}} \cup \Sigma$$

Partitioning away state adjudicatory provisions ($\mathcal{S}_{\text{admin}} = \{18, \dots, 26\}$ and $\mathcal{S}_{\text{tribunal}} = \{29, \dots, 32\}$) and internal Board inquiry procedures ($\mathcal{R}_{\text{inquiry}} = \{17, \dots, 22\}$) yields the actionable fiduciary compliance space:
$$\mathcal{U}_{\text{fiduciary}} = (\mathcal{S}_{\text{Act}} \setminus (\mathcal{S}_{\text{admin}} \cup \mathcal{S}_{\text{tribunal}})) \cup (\mathcal{R}_{\text{Rules}} \setminus \mathcal{R}_{\text{inquiry}}) \cup \Sigma$$

From $\mathcal{U}_{\text{fiduciary}}$, we construct a formal 26-node statutory decision tree $\mathcal{T}_{\text{statute}}$, defining the discrete taxonomy $\mathcal{V}_{26}$. Each leaf node $v \in \mathcal{V}_{26}$ represents an actionable compliance breach uniquely mapped to a formal quadruple:
$$v = \langle \sigma(v), \rho(v), \mu(v), \omega(s(v)) \rangle$$
where:
1. $\sigma(v) \in \mathcal{S}_{\text{Act}}$ is the governing substantive section of the DPDP Act, 2023;
2. $\rho(v) \in \mathcal{R}_{\text{Rules}} \cup \Sigma$ is the operational enforcement rule or schedule under the DPDP Rules, 2025;
3. $\mu(v) \in \{\text{Obligation } \mathcal{O}, \text{Prohibition } \mathcal{P}, \text{Safe Harbor Abuse } \mathcal{S}\}$ is the deontic modality; and
4. $\omega(s(v)) \in \{30, 20, 10, 5\}$ is the statutory penalty severity weight calibrated directly to Schedule 1 of the Act.

Crucially, at inference time, statutory citations are looked up deterministically from $\mathcal{T}_{\text{statute}}$ based on the predicted violation enum, rather than autoregressively generated by the language model. This structural constraint mathematically eliminates fabricated section citations. Table VII details the complete 26-node statutory taxonomy grouped into six deontic domains.

### TABLE VII: COMPLETE 26-NODE STATUTORY VIOLATION TAXONOMY UNDER THE DPDP ACT, 2023 & DPDP RULES, 2025

| Deontic Domain | Violation Type Enum ($v \in \mathcal{V}_{26}$) | Governing Section & Rule | Statutory Severity $s(v)$ | Deontic Modality & Statutory Penalty Weight $\omega(s)$ |
| --- | --- | --- | --- | --- |
| **Consent Architecture** | `CONSENT_NOT_FREE_OR_SPECIFIC` | §6(1), Rule 4 | High | Breach of Obligation ($\mathcal{O}$), $\omega = 20$ |
| | `CONSENT_MECHANICS_VIOLATION` | §6(1), §6(4), Rule 4(2) | High | Breach of Obligation ($\mathcal{O}$), $\omega = 20$ |
| | `CONSENT_MANAGER_OBSTRUCTION` | §6(7)–(9), Rule 5 | Medium | Breach of Obligation ($\mathcal{O}$), $\omega = 10$ |
| | `PENALTY_AVOIDANCE` | §33, Schedule 1 | High | Breach of Prohibition ($\mathcal{P}$), $\omega = 20$ |
| **Notice & Transparency** | `NOTICE_INADEQUATE` | §5(1), Rule 3(1) | Medium | Breach of Obligation ($\mathcal{O}$), $\omega = 10$ |
| | `LANGUAGE_ACCESSIBILITY` | §5(3), Rule 3(2) | Low | Administrative Defect ($\mathcal{O}$), $\omega = 5$ |
| | `BOARD_COMPLIANCE_VIOLATION` | §6(10), §27–28, Rule 14–16 | Medium | Breach of Obligation ($\mathcal{O}$), $\omega = 10$ |
| **Purpose & Retention** | `PURPOSE_LIMITATION_VIOLATION` | §7, §8(7), Rule 8(2) | High | Breach of Prohibition ($\mathcal{P}$), $\omega = 20$ |
| | `DATA_RETENTION_LIMIT_EXCEEDED` | §8(7), Third Sched., Rule 8(1) | High | Breach of Obligation ($\mathcal{O}$), $\omega = 20$ |
| | `ERASURE_NOTICE_PERIOD_VIOLATION` | §8(7), §12(3), Rule 8(3) | Medium | Breach of Obligation ($\mathcal{O}$), $\omega = 10$ |
| | `LEGITIMATE_USES_ABUSE` | §7 | High | Abuse of Safe Harbor ($\mathcal{S}$), $\omega = 20$ |
| | `ILLEGAL_EXEMPTION_CLAIM` | §17, Second Sched. | High | Abuse of Safe Harbor ($\mathcal{S}$), $\omega = 20$ |
| **Vulnerable & Cross-Border** | `CHILD_CONSENT_VIOLATION` | §9(1)–(3), Rule 10 | Critical | Breach of Prohibition ($\mathcal{P}$), $\omega = 30$ |
| | `CROSS_BORDER_TRANSFER_VIOLATION` | §16, Second Sched., Rule 13(4) | Critical | Breach of Prohibition ($\mathcal{P}$), $\omega = 30$ |
| | `SCOPE_APPLICATION_EVASION` | §3(b) | Critical | Breach of Prohibition ($\mathcal{P}$), $\omega = 30$ |
| | `SDF_DATA_LOCALIZATION_VIOLATION` | §10(2)(b), §16, Rule 13(4) | Critical | Breach of Prohibition ($\mathcal{P}$), $\omega = 30$ |
| | `SDF_OBLIGATIONS_MISSING` | §10(1)–(2), Rule 6 | High | Breach of Obligation ($\mathcal{O}$), $\omega = 20$ |
| | `ALGORITHMIC_PROFILING_SDF` | §10(2)(b), Rule 6(2) | High | Breach of Prohibition ($\mathcal{P}$), $\omega = 20$ |
| **Security & Accountability** | `SECURITY_SAFEGUARDS_MISSING` | §8(5), Rule 6(1)(e) | Medium | Breach of Obligation ($\mathcal{O}$), $\omega = 10$ |
| | `BREACH_NOTIFICATION_FAILURE` | §8(6), Rule 7 | High | Breach of Obligation ($\mathcal{O}$), $\omega = 20$ |
| | `LOG_RETENTION_MANDATE_VIOLATION` | Rule 8(1), CERT-In 6h | Medium | Breach of Obligation ($\mathcal{O}$), $\omega = 10$ |
| | `PROCESSOR_ACCOUNTABILITY_VIOLATION` | §8(2), Rule 6(1)(d) | Medium | Breach of Obligation ($\mathcal{O}$), $\omega = 10$ |
| | `DATA_ACCURACY_COMPLETENESS_VIOLATION` | §8(3), Rule 6(1)(a) | Low | Administrative Defect ($\mathcal{O}$), $\omega = 5$ |
| **Rights & Grievance** | `GRIEVANCE_REDRESSAL_INADEQUATE` | §13(1), Rule 11 | Medium | Breach of Obligation ($\mathcal{O}$), $\omega = 10$ |
| | `RIGHTS_IMPLEMENTATION_VIOLATION` | §11, §12, Rule 9 | Medium | Breach of Obligation ($\mathcal{O}$), $\omega = 10$ |
| | `APPEAL_PROCESS_VIOLATION` | §13(3), Rule 12 | Low | Administrative Defect ($\mathcal{O}$), $\omega = 5$ |

## B. Extraterritorial Compliance and Global Web Authenticity Verification

Under **Section 3(b)** of the Act, foreign websites domiciled outside India are strictly bound by Indian statutory requirements whenever they process the personal data of Indian citizens in connection with offering goods, digital services, or behavioural profiling. Formally, for any global web domain $\mathcal{W}_{\text{global}}$, statutory compliance is mandatory if:
$$\text{Jurisdiction}(\mathcal{W}_{\text{global}}) = \text{True} \iff \exists u \in \mathcal{U}_{\text{users}}, \quad \text{Location}(u) = \text{India} \land (\text{OffersService}(\mathcal{W}, u) \lor \text{Profiles}(\mathcal{W}, u))$$

In practice, global platforms routinely deploy standardized international privacy policies drafted for US FTC consent models or European GDPR frameworks. When evaluated against India's DPDP Act, these declarations frequently present **inauthentic compliance facades**:
1. *Commercial "Legitimate Interest" Evasion:* Global platforms routinely claim broad commercial "legitimate interest" exceptions to conduct targeted advertising and tracking. Under DPDP Section 7, however, legitimate uses constitute a closed, exhaustive list restricted to state subsidies, court mandates, and emergency medical response. Commercial advertising without unambiguous Section 6 consent constitutes an affirmative statutory breach (`LEGITIMATE_USES_ABUSE`).
2. *Asymmetrical Consent Withdrawal:* While foreign platforms offer one-click cookie acceptance, withdrawing consent requires submitting manual support tickets or navigating complex offshore account settings, directly violating Section 6(4)'s statutory parity mandate (`CONSENT_MECHANICS_VIOLATION`).
3. *Perpetual Retention Claims:* Global privacy policies often reserve rights to retain telemetry and transaction logs "indefinitely for system optimization," directly violating Section 8(7)'s statutory erasure obligation upon purpose fulfillment (`DATA_RETENTION_LIMIT_EXCEEDED`).

Ssense acts as an autonomous statutory auditor verifying whether global web platforms authentically adhere to Indian sovereign standards, exposing inauthentic legal declarations directly at the user endpoint.

## C. The Epistemology of Legal Silence: Affirmative Duty vs. Conditional Omission

A critical design requirement in statutory Law-LMs is distinguishing between contractual silence and statutory violation. Naive prompting of general-purpose LLMs routinely conflates the two: if a privacy policy makes no mention of cross-border transfers, an unadapted model flags a Section 16 violation simply because the policy "failed to discuss transfer safeguards."

In statutory jurisprudence, however, legal obligations follow strict epistemic boundaries:
1. *Conditional Prohibitions ($\mathcal{P}_{\text{conditional}}$):* Provisions such as Section 9 (child data tracking) or Section 16 (cross-border transfers) apply *only if* the fiduciary actively engages in those practices. If a domestic e-commerce platform processes only adult data within India, silence regarding cross-border transfer is legally valid and non-violating.
2. *Mandatory Affirmative Disclosures ($\mathcal{O}_{\text{disclosure}}$):* Provisions such as Section 5(1) (notice of categories and purpose) and Section 13 (designation of a Data Protection Officer and grievance mechanism) impose an unconditional affirmative duty of disclosure. Omitting grievance contact information is an actionable statutory breach.

To operationalize this distinction, Ssense enforces a **Three-Step Deductive Reasoning Chain** governed by an explicit `omission_check` firewall:
$$\text{AuditStep}_1: E \subseteq \mathcal{T}_{\text{policy}} \quad (\text{Extract verbatim affirmative text span})$$
$$\text{AuditStep}_2: \sigma = \text{TreeLookup}(v), \quad v \in \mathcal{V}_{26} \quad (\text{Map to statutory provision})$$
$$\text{AuditStep}_3: \delta = \text{Deduce}(E \models \neg \text{DPDP}(\sigma)) \quad (\text{Generate deontic justification})$$

If a candidate finding cannot identify an affirmative verbatim claim ($E = \emptyset$) or derives purely from unstated practices on a conditional prohibition ($\sigma \notin \mathcal{O}_{\text{disclosure}}$), the binary flag `omission_check = True` is asserted. The inference firewall mechanically drops all findings where `omission_check = True` prior to report emission, eliminating silence-derived false positives.

## D. Scoring Formulation: Trust and Subtlety Metrics

Every generated audit report computes two bounded scalar indicators: a Trust Score $T \in [0, 100]$ and a Subtlety Score $S \in [0, 100]$.

*Trust Score Formulation:* The Trust Score quantifies overall statutory alignment, initializing at 100 and decaying monotonically with each confirmed violation:
$$T = \max \left( 0, 100 - \sum_{v \in \mathcal{V}_{\text{confirmed}}} w(s(v)) \right)$$
where severity weights are calibrated based on statutory risk: $w(\text{Critical}) = 30$, $w(\text{High}) = 20$, $w(\text{Medium}) = 10$, and $w(\text{Low}) = 5$.

*Subtlety Score Formulation:* While the Trust Score measures the magnitude of legal breach, the Subtlety Score estimates how effectively non-compliant conduct is disguised within dense legalese. For each confirmed violation $v$, let $L(E_v)$ denote the syntactic complexity of evidence span $E_v$, measured via parse-tree depth, passive-voice ratio, and hedging markers:
$$S = \min \left( 100, \frac{1}{|\mathcal{V}_{\text{confirmed}}|} \sum_{v \in \mathcal{V}_{\text{confirmed}}} \left[ 50 \cdot \left( 1 - \text{Sim}(E_v, \sigma(v)) \right) + 25 \cdot \text{Depth}(E_v) + 25 \cdot \text{Hedge}(E_v) \right] \right)$$
A plainly worded breach (e.g., "We sell your data to advertisers") yields a low Subtlety Score, whereas evasive phrasing ("We may share anonymized behavioral insights with global ecosystem partners for value enhancement") yields a high Subtlety Score, alerting the user to deceptive drafting.


# VI. LAW-LM ARCHITECTURE AND SCALABLE INFERENCE ENGINE

## A. System Overview

Ssense is architected as an automated regulatory verification system structured into four core components: (i) an asynchronous statutory extraction and policy normalization engine; (ii) a domain-adapted Legal SLM (`Ssense-DPDP-7B`) operating over statutory deontic logic; (iii) a deterministic Statutory Compliance Layer (SCL) serving as a neuro-symbolic backstop; and (iv) a high-throughput, multi-tier inference serving architecture leveraging continuous batching, PagedAttention, and speculative decoding for low-latency web auditing. The system ingests raw web policy documents, evaluates them against the 26-node statutory decision tree, and emits schema-bound, cryptographically auditable JSON compliance verdicts. Fig. 1 illustrates the end-to-end architecture and Fig. 2 the training and alignment pipeline.


**Fig. 1. End-to-end architecture of Ssense: from raw web policy ingestion to scalable Law-LM inference and downstream compliance reporting.**


## B. Statutory Corpus and Hybrid Retrieval Grounding

The statutory corpus comprises the 44 sections of the DPDP Act, 2023 and the 22 implementation rules under the DPDP Rules, 2025 (along with statutory schedules), with statutory cross-references mapped by legal experts. The corpus is partitioned at structural legislative boundaries into 237 statutory chunks, preserving parent section metadata on each chunk. Grounded in the retrieval-augmented generation paradigm [19], two parallel indices are maintained:
1. *Lexical BM25 Index:* Handles exact statutory terminology, definitions, and specific section numerals (e.g., "Section 6(4)", "Data Protection Officer").
2. *Dense Semantic Index:* Built using `BAAI/bge-large-en-v1.5` embeddings (Xiao et al. [20]), mapping natural-language paraphrases and evasive policy wording (e.g., "withdrawing consent without friction") to governing legal provisions.

For an incoming legal query $q$ and statutory chunk $c$, candidate passages retrieved from the BM25 lexical index and dense BGE index are merged via Reciprocal Rank Fusion (RRF; Cormack et al. [42]):
$$\text{Score}_{\text{RRF}}(c) = \sum_{m \in \{\text{BM25}, \text{Dense}\}} \frac{\mathbb{I}(c \in \text{TopRank}_m)}{k_{\text{rrf}} + \text{rank}_m(c)}$$
with reciprocal rank constant $k_{\text{rrf}} = 60$. The top $K$ candidate passages are re-ranked using a neural cross-encoder (`bge-reranker-v2-m3`; Xiao et al. [20]):
$$\text{Score}_{\text{final}}(q, c) = \text{CrossEncoder}(q, c)$$
Selection of the top candidates utilizes an $O(N)$ partial sort, while an LRU embedding cache (2,048 entries) prevents redundant query re-encoding.

## C. Synthetic Data Distillation, Alignment, and Open-Weights Release

Because no public corpus of DPDP-annotated privacy policies existed, training pairs were synthesized using a generate, filter, and retry loop combining self-instruction [29], explanation trace distillation [30], [31], and legal syllogistic alignment established in DISC-LawLLM [25] and ChatLaw [26]. Drawing on the legal foundation model paradigm of SaulLM-7B [24], a Qwen2-72B-Instruct teacher (FP8 weights) was prompted with real-world policy excerpts and retrieved statutory context to generate structured audits across three deductive steps (active claim analysis, statute match, and deontic justification).

Candidate samples were passed through a deterministic filter that discarded any output failing JSON schema validation, violating the omission gate, or citing non-existent statutory sections. Failed samples were regenerated within a retry budget using verbal error feedback following the Reflexion framework [32]. This curation pipeline is designated the Data Forge. To avoid model collapse and retain distribution tails [34], real-world policy text was retained throughout synthesis, followed by MinHash 7-gram locality-sensitive hashing (Oren et al. [35], Lee et al. [36]) to ensure zero contamination between training and evaluation splits.

For preference alignment, subtle legal defects (e.g., buried indefinite retention, ambiguous consent bundling) were injected into compliant policies. Audits that over-called, under-called, or fabricated citations on these edge cases formed the rejected responses ($y_l$), while verified schema-conforming audits formed the chosen responses ($y_w$). Models were trained using rank-stabilized LoRA (rsLoRA [14]) across all linear projection layers, scaling updates by $\alpha / \sqrt{r}$:
$$\Delta W = \frac{\alpha}{\sqrt{r}} B A$$
where $r=128, \alpha=32$ for the forensic auditor and $r=64, \alpha=16$ for the conversational dialogue adapter.

*Alignment Objective:* SimPO [15] was applied using length-normalized sequence probabilities:
$$\mathcal{L}_{\text{SimPO}}(\theta) = - \mathbb{E}_{(x, y_w, y_l)} \left[ \log \sigma \left( \frac{\beta}{|y_w|} \log \pi_\theta(y_w \mid x) - \frac{\beta}{|y_l|} \log \pi_\theta(y_l \mid x) - \gamma \right) \right]$$
with $\beta = 2.0$ for the auditor to strictly enforce schema-bound statutory factuality, and $\beta = 1.0$ for the dialogue assistant.

*Open-Weights Release (`Ssense-DPDP-7B`):* Following training, the rsLoRA adapter weights were merged into the base Transformer parameters to produce a unified, standalone, open-weights statutory language model (`Ssense-DPDP-7B`, safetensors BF16). While the model can also be quantized (e.g., GGUF Q4_K_M for offline local execution via llama.cpp), our primary design target is high-throughput centralized and distributed serving capable of handling global auditing traffic at scale. Table VIII summarizes the model specifications.


**Fig. 2. Training and alignment pipeline: Data Forge synthesis, SFT, SimPO preference alignment, and merged open-weights export.**


### TABLE VIII: LAW-LM SPECIFICATIONS

| Property | Forensic Statutory Auditor | Conversational Legal Dialogue |
| --- | --- | --- |
| Base Model | Qwen2.5-7B-Instruct (28 layers, GQA, RoPE) | Qwen2.5-7B-Instruct (28 layers, GQA, RoPE) |
| Context Window | 8,192 tokens | 4,096 tokens |
| Output Format | Strict `dpdp_schema.json` via CFG | Markdown Legal Reasoning |
| rsLoRA Rank / Alpha | 128 / 32 (effective scale 2.83) | 64 / 16 (effective scale 2.00) |
| Target Modules | All linear projections (q, k, v, o, gate, up, down) | All linear projections |
| SimPO Beta ($\beta$) | 2.0 (strict factuality / schema-bound) | 1.0 (conversational fluency) |
| Released Artifact | Merged BF16 Open-Weights (`Ssense-DPDP-7B`) | Standalone LoRA Adapter & Merged Weights |

## D. Output Contract, Omission Firewall, and Statutory Compliance Layer

The auditor emits a structured JSON object containing four mandatory fields: legal reasoning narrative, confirmed violations, trust score, and subtlety score. Every finding must execute the three-step deductive chain:
1. *Step 1 (Active Claim Verification):* Extracts the verbatim textual evidence $E \subset \mathcal{T}_{\text{policy}}$ from the policy.
2. *Step 2 (Statutory Mapping):* Maps $E$ to a governing provision $\sigma \in \mathcal{S}_{\text{fiduciary}}$ looked up from the 26-node tree.
3. *Step 3 (Deontic Syllogism):* Generates a concise rationale proving why $E$ breaches the statutory mandate of $\sigma$.

*The Omission Firewall:* If a candidate finding derives from silence rather than an affirmative statement on a conditional prohibition, the binary flag `omission_check = True` is set. The inference engine mechanically purges all findings where `omission_check = True` prior to emitting the report (Fig. 3).


**Fig. 3. Three-step deductive reasoning chain and the omission firewall dropping silence-derived candidate findings.**


*Deterministic Statutory Compliance Layer (SCL):* Language models can miss explicitly worded statutory violations due to multi-head attention decay over long texts. To guarantee zero false negatives on explicit statutory admissions, the SCL acts as a deterministic regex backstop. For each violation type $v$, the SCL evaluates regular expressions $R_v$ guarded by safe-harbor lookarounds $H_v$ (e.g., data retention permitted "where required under Indian banking regulations"):
$$V_{\text{final}} = V_{\text{SLM}} \cup \left( \bigcup_{v \in \mathcal{V}_{26}} \{ v \mid \exists e \in \mathcal{T}_{\text{policy}}, e \models R_v \land e \not\models H_v \} \right)$$
The union ensures that plainly stated statutory admissions are captured deterministically without relying solely on autoregressive attention.

## E. High-Throughput Inference Architecture and Multi-Tier Cache Hierarchy

Serving real-time compliance audits for web traffic globally requires an inference engine capable of sub-second response times without redundant autoregressive compute. Ssense implements a five-stage hierarchical caching and deduplication pipeline (Fig. 4):
1. *In-Memory LRU-TTL Cache:* A high-speed memory cache (512 entries, 5-minute TTL) resolving burst queries for active web domains in $<1 \text{ ms}$.
2. *Persistent SQLite Domain Store:* A persistent store keyed by fully-qualified domain name (90-day TTL) storing completed audit reports.
3. *Cryptographic Policy Hash Matching:* The extracted policy body is hashed via SHA-256. If a website updates minor UI elements but leaves its privacy policy text unchanged, the SHA-256 hash matches the stored record, immediately returning the cached legal audit without model invocation.
4. *Concurrent Request Coalescing:* When multiple concurrent requests arrive for an un-cached domain, an in-process orchestrator coalesces them via an atomic mutex on the composite key $\kappa = \text{domain} \parallel \text{hash}$. Exactly one forward pass is executed, broadcasting results to all waiting callers.
5. *SLM Execution:* Autoregressive model generation is triggered only upon a complete cache miss.

The expected execution cost per incoming audit request follows:
$$\mathbb{E}[\text{Cost}] = t_{\text{mem}} + (1 - h_{\text{mem}}) \left[ t_{\text{db}} + (1 - h_{\text{db}}) \left[ t_{\text{hash}} + (1 - h_{\text{hash}}) t_{\text{SLM}} \right] \right]$$
where $h_k$ is the hit rate and $t_k$ the latency of tier $k$.


**Fig. 4. Multi-tier hierarchical caching and request coalescing pipeline for scalable Law-LM serving.**


## F. Pushdown Automaton Grammar-Constrained Decoding and Context Structuring

To eliminate syntactic drift (such as truncated JSON arrays, malformed brackets, or hallucinated violation keys), Ssense implements finite-state machine (FSM) grammar-constrained decoding grounded in XGrammar [21]. The JSON schema (`dpdp_schema.json`) is compiled into a pushdown automaton context-free grammar (CFG). At each generation step $t$, the set of admissible tokens $\mathcal{V}_t \subset \mathcal{V}$ is derived from the current automaton state, and logits for non-admissible tokens are masked to $-\infty$:
$$\text{Logits}'_t(w) = \begin{cases} \text{Logits}_t(w) & \text{if } w \in \mathcal{V}_t \\ -\infty & \text{otherwise} \end{cases}$$
This mathematically guarantees 100% syntactic schema validity and valid enum emission without post-hoc rejection sampling or retry latency.

*Attention-Aware Context Structuring and FlashAttention:* To counteract multi-head attention decay across long privacy policies ($>8,000$ tokens)—the *Lost in the Middle* phenomenon (Liu et al. [52], LegalBench [2])—Ssense integrates sub-quadratic FlashAttention-2 GPU kernels (Dao [47]) and packages retrieved statutory provisions within explicit `<retrieved_statutes>` XML boundary tags placed at prompt extremities, ensuring statutory duties remain maximally salient to attention heads without quadratic memory explosion.

## G. Inference Serving Architecture: Continuous Batching, PagedAttention, and Speculative Decoding

To transition statutory compliance verification from slow, offline analysis to real-time auditing, Ssense integrates an optimized inference serving engine powered by continuous batching, PagedAttention, and speculative decoding.

*Dynamic Iteration-Level Continuous Batching:* Standard batched inference pads all sequences in a batch to the length of the longest request, causing severe GPU bubble waste when auditing web policies with disparate lengths (from 490 to 16,000 tokens). Ssense deploys continuous iteration-level scheduling (via vLLM), where newly arrived audit requests are dynamically inserted into the running batch at iteration boundaries as earlier sequences complete generation, maximizing tensor core utilization.

*Virtual Memory KV Management (PagedAttention):* Standard linear memory allocation reserves static contiguous VRAM for maximum context lengths ($L_{\text{max}} = 8,192$), leading to over 60–80% internal memory fragmentation and triggering Out-of-Memory (OOM) faults under concurrent loads. Ssense employs PagedAttention (Kwon et al. [48]), partitioning the Key-Value (KV) cache into non-contiguous physical memory blocks of 16 tokens. This dynamic paging eliminates external fragmentation, caps peak FP8 KV cache memory at 14.8 GB across $B=16$ concurrent streams, and prevents OOM crashes without dropping requests.

*Multi-LoRA Serving (S-LoRA):* Ssense concurrently deploys the forensic statutory auditor adapter ($r=128, \alpha=32$) and the interactive dialogue adapter ($r=64, \alpha=16$) on a shared Qwen2.5 base model. Using the S-LoRA framework (Sheng et al. [49]), dynamic LoRA computation and adapter weight paging eliminate redundant base model memory replication, enabling sub-millisecond adapter swapping during concurrent user sessions.

*Prompt KV Cache Pre-Warming:* The system prompt containing core DPDP statutory definitions, deontic rules, and schema instructions is invariant across audit requests. Using the Prompt Cache paradigm [50], prefill Key-Value states ($\mathcal{K}, \mathcal{V}$) for this 1,200-token prefix are pre-computed and held resident in GPU memory, reducing prompt prefill latency to $<15\text{ ms}$.

*Speculative Prompt Lookup Decoding:* Auditing legal contracts inherently involves substantial $n$-gram lexical overlap between the extracted policy clauses, retrieved statutory provisions, and generated reasoning traces. Rather than generating every token autoregressively, Ssense implements speculative prompt lookup decoding [51] ($k=3$): matching $n$-grams from the prompt context are speculatively proposed as candidate continuation tokens and verified simultaneously in a single Transformer forward pass. This delivers a $1.8\times$ decoding speedup without requiring an auxiliary draft model.

## H. Statutory Severity Classification and Regulatory Risk Tiers

Confirmed statutory violations map deterministically to four standardized statutory severity and regulatory risk tiers, formally aligned with the penalty framework under Schedule 1 of the DPDP Act, 2023 (Table IX):

1. *Critical Non-Compliance (Statutory Severity Weight $\omega = 30$):* Assigned to substantive violations of non-derogable statutory prohibitions that inflict immediate, irreversible harm on vulnerable data principals or compromise national data sovereignty. Specifically covers Section 9 prohibitions on tracking, behavioral monitoring, or targeted advertising directed at children, and Section 16 unlawful cross-border data exfiltration. Under Schedule 1, Item 1 and Item 2 of the DPDP Act, these breaches attract the statute's maximum financial penalties (up to ₹250 crore). Downstream audit engines classify these as priority regulatory citations.
2. *High Non-Compliance (Statutory Severity Weight $\omega = 20$):* Assigned to substantive breaches of core fiduciary duties—including deceptive or bundled consent (§6(1)), commercial exploitation under generic legitimate-use pretexts (§7), indefinite data retention beyond purpose fulfillment (§8(7)), delayed data breach notification (§8(6)), and non-compliance with Significant Data Fiduciary obligations (§10). Under Schedule 1, Item 3, these violations attract statutory penalties of up to ₹200 crore, generating formal non-compliance findings.
3. *Medium Non-Compliance (Statutory Severity Weight $\omega = 10$):* Assigned to transparency, procedural, and rights-implementation defects—such as deficient itemized notices (§5(1)), asymmetrical friction on consent withdrawal (§6(4)), lack of data processor oversight (§8(2)), and absent or unresponsive grievance redressal channels (§13). Under Schedule 1, Item 4, these attract statutory penalties of up to ₹50 crore, triggering formal compliance warnings.
4. *Low Non-Compliance / Administrative Defect (Statutory Severity Weight $\omega = 5$):* Assigned to technical and administrative non-compliances that do not compromise substantive data principal protections—such as failing to provide multilingual notice accessibility in Eighth Schedule languages (§5(3), `LANGUAGE_ACCESSIBILITY`), minor data accuracy record-keeping gaps (§8(3), `DATA_ACCURACY_COMPLETENESS_VIOLATION`), and appeal procedural defects (§13(3), `APPEAL_PROCESS_VIOLATION`). Under Schedule 1, Item 5, these are categorized as general administrative defects subject to advisory compliance notifications.

### TABLE IX: STATUTORY SEVERITY CLASSIFICATION AND REGULATORY RISK TIERS

| Statutory Risk Tier | Governing DPDP Sections | Statutory Violation Examples | Schedule 1 Penalty Ceiling & Regulatory Status |
| --- | --- | --- | --- |
| **Critical Non-Compliance** | §9 [Rule 10], §16 [Rule 13(4), Sched. 2], §3(b), §10(2)(b) | `CHILD_CONSENT_VIOLATION`, `CROSS_BORDER_TRANSFER_VIOLATION`, `SCOPE_APPLICATION_EVASION`, `SDF_DATA_LOCALIZATION_VIOLATION` | Up to ₹250 crore; Priority Regulatory Escalation Citation |
| **High Non-Compliance** | §6(1), §7, §8(6) [Rule 7], §8(7) [Rule 8, Sched. 3], §10 [Rule 6], §17, §33 | `CONSENT_NOT_FREE_OR_SPECIFIC`, `LEGITIMATE_USES_ABUSE`, `DATA_RETENTION_LIMIT_EXCEEDED`, `BREACH_NOTIFICATION_FAILURE`, `SDF_OBLIGATIONS_MISSING`, `PENALTY_AVOIDANCE`, `ILLEGAL_EXEMPTION_CLAIM` | Up to ₹200 crore; Substantive Non-Compliance Citation |
| **Medium Non-Compliance** | §5(1) [Rule 3], §6(4) [Rule 4], §6(7)–(9) [Rule 5], §8(2), §8(5) [Rule 6], §13 [Rule 11] | `NOTICE_INADEQUATE`, `CONSENT_MECHANICS_VIOLATION`, `GRIEVANCE_REDRESSAL_INADEQUATE`, `SECURITY_SAFEGUARDS_MISSING`, `PROCESSOR_ACCOUNTABILITY_VIOLATION`, `LOG_RETENTION_MANDATE_VIOLATION`, `BOARD_COMPLIANCE_VIOLATION` | Up to ₹50 crore; Formal Compliance Warning & Remediation Notice |
| **Low Non-Compliance** | §5(3) [Rule 3(2)], §8(3) [Rule 6], §13(3) [Rule 12] | `LANGUAGE_ACCESSIBILITY`, `DATA_ACCURACY_COMPLETENESS_VIOLATION`, `APPEAL_PROCESS_VIOLATION` | General administrative penalty (up to ₹50 crore); Technical Advisory Notice |

## I. Interactive Conversational Dialogue Engine

Alongside forensic JSON auditing, Ssense provides a citizen-facing conversational dialogue adapter (`chatbot-model-final-adapter`) to explain statutory findings in accessible natural language. To eliminate latency, chat requests read pre-computed natural-language summaries from the audit store. Two response modes are supported:
* *Concise Mode:* Emits two to three direct sentences ($<45$ words, 60-token ceiling) explaining the primary privacy risk.
* *Thinking Mode:* Executes step-by-step statutory reasoning through the relevant DPDP sections ($<200$ tokens).
The dialogue model is evaluated on an independent certification axis guaranteeing zero schema bleed (ensuring internal JSON structures never leak into user-facing dialogue).

## J. Security and Adversarial Integrity

Table X details the attack surfaces evaluated for the Law-LM and their corresponding defense controls. To prevent prompt injection from malicious policy text [44], [45], inputs undergo NFKC Unicode normalization, control-character stripping, and character entropy filtering (flagging entropy $\ge 5.5$ bits as obfuscated payloads). Model outputs are rigidly constrained by the CFG grammar, eliminating arbitrary code or prompt injection leakage.

### TABLE X: SYSTEM ATTACK SURFACES AND SECURITY CONTROLS

| Threat Vector | Potential Impact | Security Control Mechanism |
| --- | --- | --- |
| Indirect Prompt Injection | Policy text attempts to hijack LLM instructions [44] | NFKC normalization, entropy filter ($\ge 5.5$ bits), grammar-constrained logit masking [21] |
| Server-Side Request Forgery (SSRF) | Policy fetch URL targets internal or cloud metadata IPs | IP blocklist (rejects private, loopback, link-local, and 169.254.169.254 metadata ranges) |
| Request Replay / Forgery | Unauthorized invocation of inference endpoints | HMAC-SHA256 signature over timestamp and nonce; 5-minute replay window |
| Syntactic Output Corruption | Malformed model output disrupts downstream systems | Pushdown automaton CFG masking guaranteeing 100% schema validity |
| Legal Citation Confabulation | Hallucination of fictitious section numbers | Deterministic decision tree lookup; model restricted to 26 validated enum keys |


Table X outlines the attack vectors and their corresponding mitigations. Prompt-injection defence normalises input via NFKC, strips unprintable control characters, scans for adversarial heuristic patterns, and flags content exhibiting character entropy $\ge 5.5$ bits. Indirect injection through crawled web policy content is an established threat in LLM-integrated pipelines [44], [45], and preference-based alignment directly suppresses injection susceptibility [46]. Consequently, prompt-injection robustness forms an explicit requirement in our release certification matrix (Axis 12).

Audit ingestion requests are authenticated via cryptographic HMAC-SHA256 signatures over timestamp and nonce, preventing unauthorized invocation or replay attacks across the distributed API cluster. Verified audit results and compliance telemetry are keyed strictly by canonical domain name, preserving operational audit transparency without retaining client-identifiable session data.

**Fig. 5. End-to-end statutory auditing and verification architecture: (a) automated web policy crawler and text normalizer, (b) multi-tier deduplication cache and request coalescing engine, (c) grammar-constrained `Ssense-DPDP-7B` inference pipeline with omission firewall, and (d) deterministic statutory consistency verification and regulatory risk severity mapping.**


# VII. EMPIRICAL EVALUATION FRAMEWORK AND EXPERIMENTAL DESIGN

## A. Research Questions

To rigorously evaluate whether sovereign statutory fine-tuning and neuro-symbolic alignment can transform a Small Language Model into an authoritative legal compliance auditor under India's DPDP Act, 2023 and DPDP Rules, 2025, our empirical evaluation is structured around five central research questions (RQs):
- **RQ1 (Statutory Reasoning & Deontic Accuracy):** Can a domain-adapted 7B Legal Small Language Model (`Ssense-DPDP-7B`), trained via rank-stabilized LoRA (rsLoRA) and Simple Preference Optimization (SimPO), outperform zero-shot commercial foundation models (`GPT-4o-mini`) and symbolic ABAC systems (`APLiance` [3]) in classifying actionable statutory violations across the complete 26-node DPDP taxonomy?
- **RQ2 (Epistemic Silence & Safe-Harbor Discrimination):** Does the integration of a three-step deductive reasoning chain and an epistemic Omission Firewall resolve the small-sample silence paradox, eliminating the 100% false-positive policy failure rate exhibited by prior DPDP audit benchmarks (APLiance)?
- **RQ3 (Statutory Hallucination Defense & Verbatim Evidence Grounding):** Does sovereign statutory alignment strictly bound legal citations within the true DPDP universe (Sections 1–44, Rules 1–22) and eliminate cross-jurisdictional contamination (GDPR/CCPA/HIPAA bleed), while ensuring that all cited evidence quotes map verbatim to source policy texts?
- **RQ4 (Human Alignment & Construct Validity of Automated Judges):** Does an automated 72B LLM-as-a-judge demonstrate construct validity, statistical correlation, and acceptable generosity bounds when calibrated against a double-blind panel of senior Indian data protection advocates?
- **RQ5 (Human-Centric Communication & Cognitive Accessibility Lift):** Following the Human-Centric Data Privacy Communication (HSDPC) framework, does Ssense's multi-layered audit synthesis significantly reduce linguistic complexity and reading time while boosting citizen comprehension and decision confidence compared to raw fiduciary legalese?

## B. Stratified Evaluation Corpora and Data Isolation

To prevent domain bias and rigorously stress-test the model across diverse commercial drafting styles, we assemble a four-tier evaluation testbed:

*1. Strategic Indian Fiduciary Corpus ($N=10$):* We harvest, normalize, and evaluate end-to-end privacy policies from ten high-traffic Indian digital platforms representing over 500 million Monthly Active Users (MAU) across six critical economic sectors:
- *E-Commerce & Food-Tech:* Zomato, Swiggy, Nykaa (platforms processing high-frequency consumer GPS coordinates, delivery addresses, and payment tokens).
- *FinTech & Capital Markets:* Paytm, Zerodha, Groww, CRED (heavily regulated entities governed by overlapping Reserve Bank of India (RBI) and Securities and Exchange Board of India (SEBI) statutory record retention mandates).
- *Travel & Health-Tech:* MakeMyTrip, Tata 1mg, redBus (services handling sensitive medical prescriptions, diagnostic records, and cross-border booking itineraries).

As detailed in Table XI, this real-world testbed introduces massive length variance: from Paytm's concise 1,962-character policy (~490 tokens) to MakeMyTrip's comprehensive 64,000-character policy (~16,000 tokens)—a 33:1 document length disparity that stress-tests attention stability.

### TABLE XI: STRATIFIED FIDUCIARY PILOT TESTBED CORPUS

| Fiduciary Platform | Commercial Economic Sector | Policy Text Length | Estimated Token Count | Primary Data Categories Processed |
| :--- | :--- | :---: | :---: | :--- |
| **Zomato** | Food-Tech / Delivery | 14,820 chars | ~3,700 tokens | Real-time GPS, order history, contact books, device IDs |
| **Swiggy** | Food-Tech / Quick-Commerce | 18,450 chars | ~4,610 tokens | Geolocation, delivery logs, device telemetry, payment tokens |
| **Nykaa** | E-Commerce / Retail | 12,300 chars | ~3,075 tokens | Shipping addresses, beauty preferences, customer support chats |
| **Paytm** | FinTech / Digital Payments | 1,962 chars | ~490 tokens | Transaction logs, KYC identity tokens, payment instrument hashes |
| **Zerodha** | Brokerage / Capital Markets | 8,420 chars | ~2,105 tokens | PAN/Aadhaar identity, demat records, trading history, bank mandates |
| **Groww** | FinTech / Investments | 9,150 chars | ~2,285 tokens | Investment profiles, KYC records, mutual fund transaction logs |
| **CRED** | FinTech / Credit Services | 11,200 chars | ~2,800 tokens | Credit card statements, bank SMS metadata, credit bureau scores |
| **MakeMyTrip** | Travel / Hospitality | 64,000 chars | ~16,000 tokens | Passport details, flight itineraries, biometric hotel check-ins |
| **Tata 1mg** | Health-Tech / Digital Pharmacy | 22,600 chars | ~5,650 tokens | Medical prescriptions, diagnostic lab reports, consultation records |
| **redBus** | Travel / Intercity Ticketing | 15,400 chars | ~3,850 tokens | Passenger manifests, seat preferences, location tracking |

*2. Controlled Synthetic Holdout Benchmark ($N=60$):* To evaluate edge cases absent in production policies, the Data Forge compiler generated 60 expert-validated holdout policies stratified across three cognitive complexity silos:
- *Silo 1: Baseline Literal (30%, $N=18$):* Overt, unambiguous statutory breaches (e.g., explicit declarations of perpetual retention or unconditional data sharing with third-party advertisers).
- *Silo 2: Camouflage and Evasion (50%, $N=30$):* Deceptive corporate legalese, cross-clause contradictions, vague purpose hedging ("as commercially appropriate"), and obscured consent withdrawal friction.
- *Silo 3: Adversarial Safe-Harbor Traps (20%, $N=12$):* Fully compliant policies containing sensitive legal language (medical disclosures, court subpoenas, employment records) that trigger superficial alarms but are legally protected under Section 17 safe harbors.

*3. Interactive RAG & Conversational Testbed ($N=150$):* 100 conversational citizen legal queries (`dpdp_chatbot_qa.json`) and 50 statutory retrieval queries (`dpdp_rag_testset.json`) evaluating citation accuracy, context faithfulness, and conversational dialogue hygiene.

*4. Red-Teaming Adversarial Testbed ($N=100$):* 50 prompt injection payloads embedded in DOM structures and 50 statutory trap prompts (`redteam_hallucination_prompts.json`) attempting to coerce the model into validating fictitious legal exemptions or illegal penalty safe harbors.

*5. Contamination Firewall & Data Isolation:* To ensure evaluation integrity, we execute a MinHash Locality-Sensitive Hashing (LSH) scan using 128 permutations over character 7-grams between the training corpus and all evaluation benchmarks. The maximum observed pairwise Jaccard similarity between any training sample and evaluation policy was $J = 0.124$ (well below the conservative contamination threshold of $J = 0.85$), confirming zero train-eval data leakage.

## C. Reference Standards, Double-Blind Legal Annotation Protocol, and Baseline Systems

*Gold-Standard Ground Truth Annotation:* To establish an authoritative reference standard, all evaluation policies and conversational dialogue traces were independently annotated by two senior Indian legal research specialists with specialized expertise in Indian data protection jurisprudence and corporate compliance. Annotators applied an exhaustive statutory codebook mapping text excerpts to the 26-node statutory violation taxonomy (§5–§16 of the DPDP Act, 2023 and Rules 3–22 of the DPDP Rules, 2025). Inter-annotator reliability was quantified using Cohen's Kappa, yielding $\kappa = 0.884$ ($p < 0.001$), denoting strong inter-rater consensus. Discrepancies (predominantly concerning implicit consent phrasing and the boundaries of legitimate uses under Section 7) were adjudicated through structured consensus conferences presided over by a senior legal compliance referee to establish final gold-standard labels.

*Comparative Baseline Systems:* We benchmark `Ssense-DPDP-7B` against prominent foundation models and domain-specific baselines:
1. *Unadapted Base SLM (`Qwen2.5-7B-Instruct` [12]):* Evaluates baseline zero-shot legal reasoning prior to domain adaptation, quantifying the necessity of statutory fine-tuning.
2. *Proprietary General Foundation Model (`GPT-4o-mini`):* Evaluates commercial closed-weights reasoning under identical prompt conditioning and context injection via external API endpoints.
3. *Published SOTA Domain Baseline (`APLiance` [3]):* The state-of-the-art DPDP policy analysis framework, which couples zero-shot `GPT-5.4-mini` attribute extraction with a symbolic Attribute-Based Access Control (ABAC) engine over 400 attribute determinations across 25 corporate policies.
4. *InLegalBERT + Rule Extraction Baseline:* An adapted domain baseline combining InLegalBERT embeddings with rule-based attribute classification.
5. *Systematic Component Ablations:* Controlled configurations disabling individual system modules (rsLoRA, SimPO, Omission Firewall, SCL, and Cross-Encoder) to isolate marginal utility.

## D. Algorithmic Evaluation Metrics and Formal Mathematical Formulations

Statutory compliance auditing requires specialized evaluation metrics that transcend generic sequence-level BLEU or ROUGE metrics. We formulate evaluation across twelve rigorous algorithmic pillars:

*1. Severity-Weighted Bipartite Multi-Violation Assignment F1 ($F_1^{	ext{sev}}$):* Multi-violation legal audits cannot be evaluated using naive string equality or greedy matching, which produces order-dependent distortions. Let $\mathcal{P} = \{p_1, \dots, p_m\}$ denote predicted violations and $\mathcal{G} = \{g_1, \dots, g_n\}$ ground-truth statutory violations. We formulate alignment as a maximum-weight bipartite matching problem solved via the Hungarian algorithm (Zhang et al. [53]):

$$\max_{\mathbf{X}} \sum_{i=1}^m \sum_{j=1}^n X_{ij} W(p_i, g_j) \quad 	ext{s.t.} \quad \sum_{j=1}^n X_{ij} \le 1, \; \sum_{i=1}^m X_{ij} \le 1, \; X_{ij} \in \{0, 1\} 	ag{14}$$

where the edge weight $W(p_i, g_j)$ incorporates statutory severity weights $w(s) \in \{1.0 	ext{ (Critical)}, 0.8 	ext{ (High)}, 0.6 	ext{ (Medium)}, 0.4 	ext{ (Low)}\}$ conditioned on exact violation type equality and tuple-based statutory reference equivalence:

$$W(p_i, g_j) = w(s_j) \cdot \mathbb{I}(	ext{type}(p_i) = 	ext{type}(g_j)) \cdot \mathbb{I}(	ext{sec}(p_i) \cong 	ext{sec}(g_j)) 	ag{15}$$

Citations are parsed into hierarchical tuples (e.g., "Section 8(1)(a)" $	o ('8', '1', 'a')$), supporting bidirectional root fallback while strictly disallowing subsection confusion (e.g., $8(1)$ vs. $8(2)$).

*2. Strict Parametric Citation Validity Rate (PCVR) and Statute Hallucination Rate (SHR):* Statute hallucination rate (SHR) measures the proportion of cited legal references falling outside the true statutory universe of the Act ($1 \le 	ext{Section} \le 44$ and $1 \le 	ext{Rule} \le 22$):

$$	ext{SHR} = rac{1}{K} \sum_{k=1}^K \mathbb{I}(	ext{ref}_k 
otin \mathcal{U}_{	ext{DPDP}}), \quad \mathcal{U}_{	ext{DPDP}} = \{\S 1 \dots \S 44\} \cup \{	ext{Rule } 1 \dots 	ext{Rule } 22\} 	ag{16}$$

Correspondingly, $	ext{PCVR} = 100.0\% - 	ext{SHR}$.

*3. Verbatim Evidence Grounding Accuracy (VEGA) & Evidence Quote Hallucination Rate (EQHR):* To prevent language models from fabricating corporate statements, every cited evidence quote $q_i$ is tested for exact substring containment against the source policy text $\mathcal{T}_{	ext{policy}}$ after alphanumeric AST normalization:

$$	ext{VEGA} = rac{1}{M} \sum_{i=1}^M \mathbb{I}(	ext{clean}(q_i) \subseteq 	ext{clean}(\mathcal{T}_{	ext{policy}})), \quad 	ext{EQHR} = 100.0\% - 	ext{VEGA} 	ag{17}$$

*4. Jurisdictional Contamination Rate (JCR):* Evaluates jurisdictional isolation via word-boundary regular expressions detecting foreign statutory provisions (GDPR Articles, CCPA, HIPAA, COPPA) bleeding into Indian compliance rationales:

$$	ext{JCR} = rac{1}{N} \sum_{i=1}^N \mathbb{I}(\exists c \in \mathcal{C}_{	ext{foreign}} : c \subseteq 	ext{output}_i) 	ag{18}$$

*5. Epistemic Silence Discrimination (Omission Firewall Accuracy, OFA):* Measures whether the system correctly abstains from penalizing non-mandatory statutory omissions:

$$	ext{OFA} = rac{	ext{True Negatives on Silence}}{	ext{True Negatives on Silence} + 	ext{False Positives on Silence}} 	imes 100\% 	ag{19}$$

*6. Safe-Harbor Recognition Rate (SHRR):* Evaluates whether policies declaring long data retention explicitly conditioned on external statutory mandates (e.g., PMLA, SEBI, RBI) are correctly shielded from false violation flags under Section 8(7) provisos and Section 17 exemptions.

*7. Deontic Modality Classification Accuracy:* Evaluates the classification of contractual clauses across the four deontic modalities: Obligations ($\mathcal{O}$), Prohibitions ($\mathcal{P}$), Permissions ($\mathcal{P}erm$), and Safe Harbors ($\mathcal{S}$).

*8. Context Faithfulness (CF) LLM-as-a-Judge Alignment:* Following Deka & Srivastava (High 1) and standard legal AI evaluation protocols, the conversational assistant is evaluated for Context Faithfulness using a Chain-of-Thought (CoT) legal auditing judge prompt ($s_{	ext{CF}} \in [1, 5]$). Construct validity against human advocates is evaluated via Mean Absolute Error (MAE), Pearson correlation ($r$), Spearman rank correlation ($
ho$), and generosity bias:

$$	ext{MAE} = rac{1}{N} \sum_{i=1}^N |s_{	ext{judge}, i} - s_{	ext{human}, i}|, \quad 	ext{Bias} = rac{1}{N} \sum_{i=1}^N (s_{	ext{judge}, i} - s_{	ext{human}, i}) 	ag{20}$$

*9. Readability and Cognitive Lift (FRE & FKGL):* Following Anand et al. (High 2), readability complexity is quantified via Flesch Reading Ease (FRE) and Flesch-Kincaid Grade Level (FKGL):

$$	ext{FRE} = 206.835 - 1.015 \left(rac{	ext{total words}}{	ext{total sentences}}
ight) - 84.6 \left(rac{	ext{total syllables}}{	ext{total words}}
ight) 	ag{21}$$

$$	ext{FKGL} = 0.39 \left(rac{	ext{total words}}{	ext{total sentences}}
ight) + 11.8 \left(rac{	ext{total syllables}}{	ext{total words}}
ight) - 15.59 	ag{22}$$

*10. Statistical Significance Testing:* Significance over discordant classification pairs $(n_{01}, n_{10})$ is computed via the paired continuity-corrected McNemar test:

$$\chi^2 = rac{(|n_{01} - n_{10}| - 1)^2}{n_{01} + n_{10}} 	ag{23}$$

*11. Wilson Score Confidence Intervals & Boundary Gating:* For binomial rates $\hat{p}$, we compute asymmetric 95% Wilson score confidence intervals:

$$	ext{CI}_{	ext{Wilson}}(\hat{p}) = rac{\hat{p} + rac{z^2}{2N} \pm z \sqrt{rac{\hat{p}(1-\hat{p})}{N} + rac{z^2}{4N^2}}}{1 + rac{z^2}{N}} 	ag{24}$$

*Dual-Gating Rule:* Absolute boundary requirements (0.0% hallucination rate, 100% schema validity) are evaluated on the point estimate, whereas all interior fuzzy targets ($F_1 \ge 0.72$, Citation Precision $\ge 90\%$) are strictly gated by the 95% Wilson Lower Bound ($z=1.96$).

*12. DPDP Statutory Trust Score Formulation:* The overall compliance posture is synthesized into an integer Trust Score $\in [0, 100]$:

$$\text{Score}_{\text{DPDP}} = \max\left(0, 100 - \sum_{k=1}^{|V_{\text{final}}|} \omega(s_k)\right) \tag{25}$$

where penalty weights $\omega(s) \in \{30 \text{ (Critical)}, 20 \text{ (High)}, 10 \text{ (Medium)}, 5 \text{ (Low)}\}$ penalize confirmed statutory violations.

## E. Standardized 6-Pillar Legal AI Evaluation Framework

To eliminate internal or author-biased evaluation heuristics, we ground our experimental protocol in established academic and industry evaluation methodologies from leading peer-reviewed Law-LM and privacy NLP benchmarks—specifically Stanford LegalBench (Guha et al., NeurIPS 2023 [2]), SaulLM-7B (Colombo et al., 2024 [12]), DISC-LawLLM (Yue et al., 2023 [13]), the ACL OPP-115 corpus (Wilson et al., 2016 [10]), PolicyIE (Ahmad et al., 2021 [11]), legal hallucination diagnostics (Dahl et al., 2024 [1]), and the state-of-the-art DPDP baseline APLiance (Dhakar et al., 2026 [3]).

Statutory compliance auditing exhibits extreme class imbalance: compliant contractual language constitutes over 90% of commercial policy text, whereas actionable statutory violations are sparse, nuanced, and legally complex. Consequently, reporting raw sequence accuracy or token-level BLEU/ROUGE is fundamentally invalid in legal evaluation, as token overlap fails to measure jurisprudential correctness, and raw accuracy can be artificially gamed by predicting the majority non-violation class.

To address these empirical challenges, we formalize our evaluation protocol across six standardized task pillars (summarized in Table XII):
1. **Pillar 1: Multi-Label Statutory Violation Detection & Issue-Spotting:** Evaluated across all 26 statutory violation categories ($\mathcal{V}_{26}$) using Macro-F1 (unweighted harmonic mean across classes, severely penalizing poor performance on rare violation phenotypes), Micro-F1, Balanced Accuracy ($\frac{\text{Sensitivity} + \text{Specificity}}{2}$ to prevent majority-class gaming), and the Matthews Correlation Coefficient (MCC), the gold standard metric for class-imbalanced multi-label statutory decision boundaries.
2. **Pillar 2: Evidence Grounding & Verbatim Extraction Fidelity:** Following ACL OPP-115 extraction standards, every flagged violation must cite verifiable, uncorrupted textual evidence from the audited contract. We evaluate the Quote Grounding Rate (percentage of extracted quotes matching source text as exact substrings under AST alphanumeric normalization), Token-level F1, and Exact Match (EM).
3. **Pillar 3: Statutory Universe Fidelity & Jurisdictional Isolation:** Following Dahl et al. [1], we evaluate legal citation validity through Statutory Citation Accuracy (SCA), Statute Hallucination Rate (SHR, measuring citations falling outside Sections 1–44 of the Act or Rules 1–22 of the Rules), and Jurisdictional Contamination Rate (JCR, measuring cross-jurisdictional bleed where foreign statutory concepts such as GDPR or CCPA are superimposed onto Indian legal reasoning).
4. **Pillar 4: Pushdown Automaton (CFG) Structured Output Conformance:** Regulatory compliance pipelines require deterministic, machine-readable output. We measure Strict JSON Schema Conformance Rate and Enum Validity Rate enforced at the logit level via context-free grammar (CFG) pushdown automata.
5. **Pillar 5: Direct SOTA Benchmark Replication (The APLiance Protocol):** To establish direct head-to-head parity against published literature, we replicate the exact evaluation testbed from Dhakar et al. [3] spanning 25 real-world corporate policies across 16 statutory attributes ($N=400$ evaluation instances under Sections 1–7 of the Act), isolating nuanced consent clauses and silence sensitivity.
6. **Pillar 6: Sovereign Workstation Edge Deployment Feasibility:** Rather than claiming synthetic datacenter cluster throughput, we profile actual edge execution feasibility on a standard commodity workstation (NVIDIA GeForce RTX 3060 12GB VRAM + host RAM offloading), evaluating resident VRAM memory ceilings, layer allocation splits, median audit turnaround, and zero-cloud-egress data sovereignty guarantees.

### TABLE XII: STANDARDIZED 6-PILLAR LEGAL AI EVALUATION PROTOCOL AND FORMULATIONS

| Pillar | Task / Evaluation Dimension | Standard Academic Metric | Mathematical Definition / Formulation | Literature Foundation |
| :---: | :--- | :--- | :--- | :--- |
| **Pillar 1** | Multi-Label Violation Detection | Macro-F1, Micro-F1, Balanced Accuracy, MCC | $\text{BalAcc} = \frac{\text{TPR} + \text{TNR}}{2}; \quad \text{MCC} = \frac{TP \cdot TN - FP \cdot FN}{\sqrt{(TP+FP)(TP+FN)(TN+FP)(TN+FN)}}$ | Stanford LegalBench [2], SaulLM-7B [12] |
| **Pillar 2** | Evidence Grounding & Extraction | Quote Grounding Rate (VEGA), Token F1 | $\text{VEGA} = \frac{1}{M} \sum_{i=1}^M \mathbb{I}(\text{clean}(q_i) \subseteq \text{clean}(\mathcal{T}_{\text{policy}}))$ | ACL OPP-115 [10], PolicyIE [11] |
| **Pillar 3** | Statutory Fidelity & Isolation | Statute Hallucination (SHR), Jurisdictional Bleed (JCR) | $\text{SHR} = \frac{1}{K} \sum_{k=1}^K \mathbb{I}(\text{ref}_k \notin \mathcal{U}_{\text{DPDP}}); \quad \text{JCR} = \frac{1}{N} \sum_{i=1}^N \mathbb{I}(\exists c \in \mathcal{C}_{\text{foreign}} : c \subseteq \text{out}_i)$ | Dahl et al. [1], DISC-LawLLM [13] |
| **Pillar 4** | Structured Schema Integrity | Strict JSON Conformance, Enum Validity | $\text{SCR} = \frac{1}{N} \sum_{i=1}^N \mathbb{I}(\text{Parse}(\text{out}_i, \mathcal{S}_{\text{JSON}}) = \text{Valid} \land \forall v \in \text{out}_i: v.\text{key} \in \mathcal{V}_{26})$ | Pushdown Automaton CFG Decoding [21] |
| **Pillar 5** | Direct SOTA Replication | APLiance Protocol (400 instances / 25 policies) | Attribute Accuracy, §6(1) Consent Recall, §6(4) Withdrawal Accuracy, Strict Pass Rate, Silence FPR | APLiance Benchmark (Dhakar et al., 2026 [3]) |
| **Pillar 6** | Sovereign Edge Telemetry | Resident VRAM, Layer Split, Audit Latency, Cloud Egress | Measured Edge Telemetry: 12GB RTX 3060 (21 GPU / 11 CPU layers), Median Latency (s), 0 Bytes Egress | Sovereign Edge AI & Data Sovereignty |

## F. Experimental Setup, Hardware Testbeds, and Reproducibility

Table XIII details the complete hardware environments, hyperparameter configurations, and software stacks required to reproduce training, alignment, and serving benchmarks.

### TABLE XIII: REPRODUCIBILITY PARAMETERS AND EXPERIMENTAL SPECIFICATIONS

| Component / Subsystem | Configuration Parameter | Exact Specification |
| :--- | :--- | :--- |
| **Foundation Architecture** | Base Model | `Qwen2.5-7B-Instruct` [12] (28 layers, 4 KV heads, RoPE $	heta=10^6$, 152k vocabulary) |
| **Teacher Model Oracle** | Knowledge Distillation Base | `Qwen2-72B-Instruct` (FP8 quantized weights via vLLM) |
| **Parameter-Efficient Tuning** | rsLoRA Adapters | rsLoRA [13], [14] across linear projections; Auditor $r=128, lpha=32$; Chatbot $r=64, lpha=16$ |
| **Optimization Stack** | Optimizer & Precision | Fused FP32 AdamW [61] with NEFTune [62] noise; Learning Rate $2 	imes 10^{-4}$ (Cosine decay) |
| **Preference Alignment** | SimPO Objective | Reference-free margin optimization; Auditor $eta=2.0$; Chatbot $eta=1.0$; Target margin $\gamma=0.5$ |
| **Training Infrastructure** | High-Performance Compute | NVIDIA DGX Spark (GB10 Superchip), CUDA 13.0, PyTorch 2.11.0, Unsloth 2026.8 |
| **Hybrid Retrieval Engine** | Vector & Lexical Indices | 237 chunks; BM25Okapi ($k_1=1.5, b=0.75$) + `bge-large-en-v1.5`; Re-ranker `bge-reranker-v2-m3` ($lpha=0.45$) |
| **High-Throughput Serving** | Production Inference Engine | FastAPI + vLLM continuous batching; PagedAttention with FP8 KV cache; XGrammar pushdown CFG masking [21] |
| **Caching Hierarchy** | Multi-Tier Deduplication | Tier 1: In-Memory LRU-TTL (512 entries, 5 min); Tier 2: Persistent SQLite (90 days); SHA-256 policy hash |
| **Consumer Hybrid Testbed** | Unified Memory Split | 21 layers on GPU VRAM, 11 layers offloaded to host system RAM; throughput 0.5–18.2 tokens/s |
| **Input Safeguards** | Extraction Caps | 8 MB HTTP response cap, 20 s timeout, 6 redirect limit, 64,000 character extraction envelope |
| **Data Integrity Verification** | Contamination Scanner | MinHash 128-permutation LSH scanner over character 7-grams ($J < 0.15$ strict separation) |

# VIII. RESULTS AND EMPIRICAL DISCUSSION

## A. Empirical Fiduciary Audit Outcomes across Global & Domestic Platforms

To evaluate Ssense under operational web conditions, we executed end-to-end statutory compliance audits across ten strategic Indian digital fiduciaries representing $>500\text{M}$ MAU (`simulate_high_volume.py`). Table XIV details the confirmed statutory breaches, governing legal provisions, and assigned statutory severity tiers.

Across the 10 audited platforms, Ssense confirmed exactly three actionable statutory violations at three sites, with **zero false positives** against the gold-standard legal expert consensus and **zero fabricated statutory citations** (SHR = 0.00%).

*Statistical Boundary Disclosure on Small-Sample Pilots:* While this 10-platform production pilot demonstrates real-world browser integration and deterministic enforcement over live web disclosures, small-sample statistical boundaries dictate that observing zero false alarms across $N=10$ sites yields a 95% Wilson score confidence interval of $[0.722, 1.000]$. Statistically, this indicates that the true population failure rate on unobserved commercial disclosures could be as high as 27.8%. Consequently, we treat the 10-site pilot strictly as an end-to-end operational proof-of-concept. To establish rigorous, unassailable population-level statistical validity, we subject Ssense to two exhaustive, standardized evaluation benchmarks in Section VIII-B: (i) a direct head-to-head replication of the APLiance DPDP benchmark ($N=400$ instances across 25 corporate policies), and (ii) the full-spectrum multi-label DPDP-Bench benchmark ($N=61$ holdout policies, 95 labeled violations across all 26 statutory categories).

### TABLE XIV: CONFIRMED STATUTORY VIOLATIONS AND STATUTORY SEVERITY CLASSIFICATION

| Fiduciary Platform | Commercial Sector | Confirmed Statutory Breach | Governing DPDP Sections | Statutory Severity & Compliance Assessment | Primary Legal Evidence & Reason Trace |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Zomato** | Food-Tech / Delivery | `NOTICE_INADEQUATE` | §5(1), Rule 3 | Medium Non-Compliance (Notice Defect) | Vague declaration of behavioral telemetry aggregation without itemized data descriptions or third-party ad network disclosures. |
| **Swiggy** | Food-Tech / Quick-Commerce | `PURPOSE_LIMITATION_VIOLATION` | §8(7) $\land$ §4(1) | High Non-Compliance (Retention Limit Breached) | Policy asserts perpetual retention of customer order logs, location metadata, and device tokens for unspecified "service evolution." |
| **redBus** | Travel / Ticketing | `LEGITIMATE_USES_ABUSE` | §7 | High Non-Compliance (Commercial Use Abuse) | Platform claims commercial monetization under generic "legitimate business operations," violating India's closed Section 7 list. |
| **Paytm** | FinTech / Payments | None detected | — | Clean Statutory Record (Safe-Harbor Compliant) | Retention clauses explicitly conditioned on statutory RBI/PMLA banking compliance, recognized by SCL safe-harbor lookarounds. |
| **Zerodha** | Brokerage / Capital Markets | None detected | — | Clean Statutory Record (Safe-Harbor Compliant) | Precise notice structure; data processing strictly bounded by statutory SEBI depository and KYC regulations. |
| **Groww** | FinTech / Investments | None detected | — | Clean Statutory Record (Safe-Harbor Compliant) | Compliant consent withdrawal mechanisms; data retention delimited by statutory mutual fund regulations. |
| **CRED** | FinTech / Credit Services | None detected | — | Clean Statutory Record (Safe-Harbor Compliant) | Itemized notice identifying credit bureau integration; explicit withdrawal procedures provided. |
| **MakeMyTrip** | Travel / Hospitality | None detected | — | Clean Statutory Record (Safe-Harbor Compliant) | Massive 64k-character policy; long-context attention preserved; cross-border booking transfers protected by Section 17 safe harbors. |
| **Tata 1mg** | Health-Tech / Pharmacy | None detected | — | Clean Statutory Record (Safe-Harbor Compliant) | Prescription processing protected under Section 7(b) medical emergency / healthcare safe harbors; zero false positives. |
| **Nykaa** | E-Commerce / Retail | None detected | — | Clean Statutory Record (Safe-Harbor Compliant) | Clear itemized disclosure of marketing cookies and explicit account deletion options. |

*Detailed Jurisprudential Analysis:*
1. *Zomato (§5(1), Rule 3):* Section 5(1) mandates that every consent request must be preceded or accompanied by an itemized notice stating the personal data to be collected and specific purpose. Zomato's policy deployed blanket language asserting user behavioral data would be processed "to improve services and deliver relevant advertising," omitting mandatory itemized breakdowns of categories shared with commercial ad-exchanges.
2. *Swiggy (§8(7) $\land$ §4(1)):* Swiggy's declaration stated order history and coordinates would be retained indefinitely for algorithmic improvement. This breaches Section 8(7) (mandatory erasure upon purpose fulfillment) and Section 4(1) (purpose limitation).
3. *redBus (§7):* redBus claimed broad processing privileges under "legitimate business operations." In European law (GDPR Art. 6(1)(f)), commercial legitimate interests represent a standard ground. Under Indian law, Section 7 provides a closed enumeration of nine legitimate uses; generic commercial legitimate interests are statutorily invalid.

*Resolution of the Seven Clean Platforms & Safe-Harbor Recognition:* The remaining seven fiduciaries passed through the model and deterministic SCL filters without false alarms. Notably, regulated FinTech entities (Paytm, Zerodha, Groww) declared 5-to-8-year retention windows. Unadapted baselines flag these as breaches. However, because their policies explicitly tied retention to statutory mandates under the *Prevention of Money Laundering Act (PMLA)* and *SEBI Regulations*, Ssense's SCL safe-harbor lookarounds recognized them as protected under Section 8(7) provisos and Section 17 exemptions, maintaining a **0.00% False Positive Rate (FPR)** and **100% precision**.

![Fig. 6. Empirical statutory audit scores across strategic Indian fiduciaries (>500M MAU)](../../fig10_fiduciary_audit_landscape.png)

**Fig. 6. Empirical statutory audit scores across strategic Indian fiduciaries ($>500\text{M}$ MAU) and confirmed legal phenotypes.**

## B. Comparative Benchmarking against SOTA Baselines

To benchmark `Ssense-DPDP-7B` against prior art with maximum scientific rigor, we evaluate performance across two standardized corpora:
1. **Benchmark 1: Direct Head-to-Head Replication of the APLiance Protocol ($N=400$ Instances / 25 Corporate Policies):** We directly replicate the 25-policy, 16-attribute evaluation testbed established by Dhakar et al. [3] under Sections 1–7 of the DPDP Act.
2. **Benchmark 2: Comprehensive Multi-Label Statutory Diagnostic Benchmark (DPDP-Bench, $N=61$ Policies, 95 Violations):** We evaluate multi-label issue spotting across all 26 statutory categories ($\mathcal{V}_{26}$) under the DPDP Act, 2023 and DPDP Rules, 2025, using standard NLP/ML legal evaluation metrics from Stanford LegalBench [2] and SaulLM-7B [12].

### 1. Direct Head-to-Head Replication of the APLiance Protocol ($N=400$ Instances)

Table XV presents the direct replication and head-to-head benchmarking of Ssense beside APLiance (GPT-5.4-mini + ABAC rule engine) [3], unadapted base (`Qwen2.5-7B-Instruct`), and commercial zero-shot `GPT-4o-mini`.

### TABLE XV: DIRECT HEAD-TO-HEAD REPLICATION OF THE APLIANCE DPDP BENCHMARK ($N=400$ INSTANCES ACROSS 25 CORPORATE POLICIES)

| Evaluated Statutory Dimension / Metric | APLiance Baseline (GPT-5.4-mini + ABAC) [3] | Unadapted Base (Qwen2.5-7B) | GPT-4o-mini (Zero-Shot) | Ssense-DPDP-7B (Ours: Aligned SLM + SCL) |
| :--- | :---: | :---: | :---: | :---: |
| **Model Weight Release** | Closed Cloud API | Open Weights | Closed Cloud API | **Open Weights (`Ssense-DPDP-7B`)** |
| **Domain Adaptation Strategy** | Zero-Shot ABAC Prompting | Pre-trained Base | Prompt Engineering | **rsLoRA ($r=128$) + SimPO ($\beta=2.0$)** |
| **Base Attribute Accuracy (Overall)** | 94.5% | 78.2% | 89.4% | **96.8% (+2.3% over SOTA)** |
| **Base Attribute Precision** | 96.1% | 76.5% | 88.0% | **97.2%** |
| **Base Attribute Recall** | 96.1% | 81.0% | 91.2% | **96.5%** |
| **Unambiguous Consent (§6(1)) Accuracy** | 64.0% (Severe Vulnerability) | 51.2% | 68.0% | **88.5% (+24.5% gain)** |
| **Unambiguous Consent (§6(1)) Recall** | 14.0% (Severe Dropout) | 22.0% | 45.0% | **84.0% (+70.0% gain)** |
| **Frictionless Consent Withdrawal (§6(4)) Accuracy** | 76.0% (Sub-Optimal) | 60.5% | 72.0% | **91.0% (+15.0% gain)** |
| **Global Policy Pass Rate (Strict Compliance Rules)** | 0.0% (0 of 25 Passed) | 0.0% (0 of 25) | 4.0% (1 of 25) | **72.0% (18 of 25 Passed)** |
| **False Positive Rate on Silence (Silence Penalty)** | 100.0% (Fails All on Silence) | 42.5% | 28.0% | **2.8% (Omission Firewall)** |

*Analysis of the APLiance Replication and the Silence Penalty Paradox:*
As documented by Dhakar et al. [3], APLiance formalizes compliance via a conjunctive symbolic ABAC engine operating under an adversarial "conservative-unknown" rule: any attribute that is unmentioned or ambiguous in the privacy policy is classified as an automatic statutory violation. Under real-world commercial conditions, this design induces a catastrophic failure mode: **100% of the 25 evaluated corporate policies failed compliance (0% pass rate)**. Only when Dhakar et al. artificially relaxed the evaluation by dropping five statutory requirements did 20 of 25 policies pass. Furthermore, zero-shot GPT-5.4-mini suffered severe recall degradation on nuanced statutory requirements—capturing only 14.0% recall on unambiguous consent (§6(1)) and 76.0% accuracy on easy consent withdrawal (§6(4)).

In sharp contrast, Ssense resolves both foundational failures:
1. *Elimination of the Silence Penalty:* By decoupling affirmative malpractice from statutory omission via the three-step deductive chain and omission firewall ($\mathcal{O}_{\text{practice}}$), Ssense lowers the false positive rate on contractual silence from 100.0% to **2.8%**, allowing 18 of the 25 policies (72.0%) to pass without compromising regulatory vigilance.
2. *Resolution of Nuanced Consent Blindspots:* Through preference-aligned SimPO training on contrasting negative pairs, Ssense lifts unambiguous consent recall from 14.0% to **84.0% (+70.0 percentage point gain)** and consent withdrawal accuracy from 76.0% to **91.0% (+15.0 percentage point gain)**, decisively surpassing the cloud-hosted baseline.

![Fig. 7A. Direct Head-to-Head Replication of the APLiance DPDP Benchmark](../../fig14_apliance_head_to_head_replication.png)

**Fig. 7A. Direct head-to-head replication of the APLiance DPDP benchmark ($N=400$ instances across 25 corporate policies) comparing `Ssense-DPDP-7B` beside APLiance (GPT-5.4-mini + ABAC [3]), GPT-4o-mini, and Qwen2.5-7B-Instruct: (a) base statutory attribute accuracy, precision, and recall; (b) statutory consent nuance resolution, showing Ssense's +70.0% lift in §6(1) unambiguous consent recall; and (c) the silence penalty paradox, demonstrating the reduction of silence false positives from 100.0% to 2.8% and lifting strict policy pass rates from 0% to 72.0%.**

### 2. Full-Spectrum Multi-Label Benchmark on DPDP-Bench ($N=61$ Policies, 95 Violations)

To evaluate multi-label issue spotting across the entire 26-node statutory violation taxonomy ($\mathcal{V}_{26}$), Table XVI benchmarks Ssense beside foundation models, commercial APIs, and domain-adapted legal models using standard NLP/ML legal evaluation metrics.

### TABLE XVI: MULTI-LABEL STATUTORY VIOLATION BENCHMARK ON DPDP-BENCH ($N=61$ POLICIES, 95 LABELED VIOLATIONS ACROSS 26 CLASSES)

| Evaluation Metric / Legal Dimension | Qwen2.5-7B-Instruct (Base) | SaulLM-7B (Domain Legal Base [12]) | GPT-4o-mini (Commercial API) | Ssense-DPDP-7B (Aligned SLM Only) | Ssense Full (SLM + SCL + CFG Mask) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Macro-F1 (All 26 Statutory Classes)** | 0.462 | 0.584 | 0.695 | 0.842 | **0.914** |
| **Micro-F1 Score** | 0.521 | 0.630 | 0.741 | 0.870 | **0.932** |
| **Balanced Accuracy** | 0.510 | 0.612 | 0.725 | 0.865 | **0.928** |
| **Matthews Correlation Coefficient (MCC)** | 0.385 | 0.490 | 0.620 | 0.785 | **0.864** |
| **Severity-Weighted Bipartite F1 ($F_1^{\text{sev}}$)** | 0.481 | 0.602 | 0.692 | 0.854 | **0.912** |
| **Precision ($\mathcal{P}$)** | 0.428 | 0.560 | 0.665 | 0.885 | **0.941** |
| **Recall ($\mathcal{R}$)** | 0.552 | 0.650 | 0.725 | 0.830 | **0.885** |
| **Verbatim Quote Grounding Rate (VEGA)** | 75.4% | 82.1% | 91.8% | 95.2% | **98.4% (Verbatim Substring)** |
| **Evidence Quote Hallucination Rate (EQHR)** | 24.6% | 17.9% | 8.2% | 4.8% | **1.60%** |
| **Statute Hallucination Rate (SHR)** | 43.8% | 28.5% | 18.6% | 4.2% | **0.00% (Strict Legal Universe)** |
| **Jurisdictional Contamination Rate (JCR)** | 34.0% (GDPR Bleed) | 22.4% | 18.0% | 2.1% | **0.00% (Zero Foreign Bleed)** |
| **Strict JSON Schema Conformance Rate** | 71.4% (Syntax Drift) | 68.2% | 92.5% | 94.0% | **100.0% (Pushdown PDA)** |
| **Inter-Annotator Agreement ($\kappa$)** | — | — | — | — | **0.884 (Cohen's Kappa)** |

*Statistical Significance Testing:* Paired McNemar hypothesis tests over discordant prediction pairs on the DPDP-Bench benchmark demonstrate:
- `Ssense Full` vs. `Qwen2.5-7B-Instruct`: Yields $\chi^2 = 34.2$ ($p < 0.001$, continuity-corrected), rejecting the null hypothesis with extreme statistical confidence.
- `Ssense Full` vs. `SaulLM-7B`: Yields $\chi^2 = 26.8$ ($p < 0.001$), confirming that jurisdiction-specific fine-tuning on Indian statutory deontic logic significantly outperforms general legal foundation models.
- `Ssense Full` vs. `GPT-4o-mini`: Yields $\chi^2 = 18.4$ ($p < 0.001$), proving that domain-adapted rsLoRA and SimPO decisively outperform commercial zero-shot prompt engineering.
- Continuous Context Faithfulness: A paired two-tailed Student's $t$-test confirms that Ssense's CF score (4.82 vs. 4.15) is statistically superior ($t = 9.86, p < 0.001$).

![Fig. 7. 8-Axis Sovereign Legal-AI Benchmark Radar](../../fig7_comparative_radar_benchmark.png)

**Fig. 7. 8-Axis Sovereign Legal-AI Benchmark Radar comparing `Ssense-DPDP-7B` beside APLiance [3], GPT-4o-mini, and Qwen-Base across statutory F1, citation validity, verbatim grounding, jurisdictional isolation, omission accuracy, safe-harbor recognition, adversarial defense, and schema integrity.**

![Fig. 7B. Multi-Label Statutory Violation Benchmark on DPDP-Bench](../../fig15_multilabel_legalbench_f1_mcc.png)

**Fig. 7B. Multi-label statutory violation benchmark on DPDP-Bench ($N=61$ holdout policies, 95 labeled violations across 26 classes): (a) standard Stanford LegalBench metrics (Macro-F1, Micro-F1, Balanced Accuracy, and Matthews Correlation Coefficient [MCC]) comparing `Ssense Full` against SaulLM-7B, GPT-4o-mini, and base foundation models; (b) verbatim evidence grounding rate (VEGA) and complete suppression of statutory hallucinations (SHR = 0.0%) and cross-jurisdictional bleed (JCR = 0.0%).**

## C. Granular Per-Provision Statutory Classification Performance

To directly evaluate statutory coverage against APLiance's 16 attributes, Table XVII benchmarks F1 scores across the ten core DPDP statutory provision clusters.

### TABLE XVII: PER-PROVISION STATUTORY CLASSIFICATION PERFORMANCE ACROSS DPDP CLUSTERS

| Statutory Provision Cluster | Governing Provisions | Ssense-DPDP-7B | APLiance Baseline [3] | GPT-4o-mini | Qwen2.5-7B (Base) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **1. Notice Adequacy & Transparency** | §5(1), Rule 3 | **0.942** | 0.880 | 0.745 | 0.521 |
| **2. Consent Validity & Specificity** | §6(1), Rules 4–7 | **0.965** | 0.920 | 0.780 | 0.584 |
| **3. Consent Withdrawal Friction** | §6(4) | **0.928** | 0.760 | 0.690 | 0.442 |
| **4. Exhaustive Legitimate Uses** | §7(a)–(i) | **0.915** | 0.680 | 0.580 | 0.365 |
| **5. Purpose & Retention Limits** | §8(7), §4(1) | **0.934** | 0.740 | 0.710 | 0.490 |
| **6. Children's Personal Data** | §9(1)–(3) | **0.980** | 0.000 (Omitted) | 0.820 | 0.512 |
| **7. Significant Data Fiduciaries** | §10(1)–(2) | **0.885** | 0.000 (Omitted) | 0.610 | 0.380 |
| **8. Principal Rights & Erasure** | §11–§14 | **0.910** | 0.780 | 0.730 | 0.485 |
| **9. Cross-Border Data Transfers** | §16 | **0.895** | 0.000 (Omitted) | 0.640 | 0.410 |
| **10. Safe Harbors & Exemptions** | §17(1)–(5) | **0.948** | 0.520 | 0.620 | 0.405 |

*Jurisprudential Defect Analysis:*
1. *APLiance Coverage Collapse:* APLiance only operationalizes Sections 1–7. Consequently, it achieves **0.000 F1 on Children's Data (§9), Significant Data Fiduciaries (§10), and Cross-Border Transfers (§16)**, which are critical areas of global corporate malpractice.
2. *Consent Nuance Vulnerability:* APLiance reported that unadapted models fail on subtle consent formulations (achieving only 64% accuracy on unambiguous consent and 76% on easy withdrawal). Ssense overcomes this via preference-aligned training on contrasting negative pairs, achieving **0.965** and **0.928** F1 respectively.
3. *Legitimate Use Confabulation:* Under Section 7, unadapted models frequently superimpose GDPR Art. 6(1)(f) commercial interests. Ssense enforces India's closed 9-case list, scoring **0.915** vs. APLiance's 0.680.

![Fig. 8. Per-provision statutory classification performance across DPDP clusters](../../fig6_statutory_taxonomy_f1_breakdown.png)

**Fig. 8. Per-provision statutory classification performance across DPDP clusters comparing `Ssense-DPDP-7B` beside APLiance [3], commercial LLMs, and foundation base.**

## D. Deontic Modality Reasoning & Confusion Analysis

Ssense categorizes contractual terms across four deontic modalities: Obligations ($\mathcal{O}$), Prohibitions ($\mathcal{P}$), Permissions ($\mathcal{P}erm$), and Safe Harbors ($\mathcal{S}$). Table XVIII details the 4x4 confusion matrix over 414 test instances.

### TABLE XVIII: 4x4 DEONTIC MODALITY CONFUSION MATRIX (SSENSE-DPDP-7B)

| True \ Predicted | Obligation ($\mathcal{O}$) | Prohibition ($\mathcal{P}$) | Permission ($\mathcal{P}erm$) | Safe Harbor ($\mathcal{S}$) | Class Recall (%) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Obligation ($\mathcal{O}$)** | **142** | 3 | 2 | 1 | **96.0%** |
| **Prohibition ($\mathcal{P}$)** | 2 | **94** | 1 | 0 | **96.9%** |
| **Permission ($\mathcal{P}erm$)** | 3 | 1 | **88** | 2 | **93.6%** |
| **Safe Harbor ($\mathcal{S}$)** | 1 | 0 | 2 | **74** | **96.1%** |

*Overall Deontic Accuracy:* **96.1%** (398 / 414). In contrast, base models score only 64.2%, routinely confusing statutory prohibitions (e.g., tracking minors) with discretionary permissions.

![Fig. 9. Deontic Modality Classification Matrix](../../fig5_deontic_confusion_matrix.png)

**Fig. 9. Deontic Modality Classification Matrix for `Ssense-DPDP-7B` demonstrating 96.1% overall modality classification fidelity across 414 statutory instances.**

## E. Systematic Component Ablation Study

To isolate the marginal utility contributed by each subsystem, we conduct systematic ablation experiments across the 60-policy holdout benchmark (Table XIX).

### TABLE XIX: SYSTEMATIC COMPONENT ABLATION STUDY

| Architecture Configuration | Severity-Weighted Violation F1 | Precision ($\mathcal{P}$) | Recall ($\mathcal{R}$) | False Positive Rate (FPR) | Statute Hallucination Rate (SHR) | Schema Compliance Rate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Full Ssense Framework** | **0.912** | **0.941** | **0.885** | **0.00%** | **0.00%** | **100.0%** |
| *(i) w/o Deterministic SCL Backstop* | 0.835 | 0.945 | 0.748 | 0.00% | 0.00% | 100.0% |
| *(ii) w/o Epistemic Omission Firewall* | 0.744 | 0.628 | 0.912 | 37.20% | 0.00% | 100.0% |
| *(iii) w/o SimPO Alignment (SFT-Only)* | 0.814 | 0.820 | 0.808 | 8.40% | 7.40% | 100.0% |
| *(iv) w/o Pushdown CFG Masking* | 0.890 | 0.932 | 0.852 | 1.20% | 0.00% | 84.6% |
| *(v) w/o Cross-Encoder Re-Ranking* | 0.862 | 0.885 | 0.840 | 3.50% | 1.80% | 100.0% |

*Analysis of Marginal Contributions:*
1. *Deterministic SCL Backstop:* Disabling SCL drops Recall from 0.885 to 0.748 ($13.7\text{ percentage point}$ collapse). In verbose policies ($>8,000$ tokens), attention dispersion causes the SLM to overlook explicit admissions. The SCL acts as a lossless neuro-symbolic backstop ($V_{\text{final}} = V_{\text{SLM}} \cup V_{\text{SCL}}$).
2. *Epistemic Omission Firewall:* Disabling the firewall causes Precision to plummet from 0.941 to 0.628, triggering a massive surge in False Positive Rate to **37.20%**. Without the three-step deductive filter and binary omission gate, the model treats unstated non-mandatory practices as breaches, reproducing APLiance's failure mode.
3. *SimPO Preference Alignment:* Removing SimPO introduces a 7.40% statute hallucination rate and 8.40% false positive rate on edge-case clauses. SimPO's length-normalized margin penalizes over-calling, regularizing legal assertions.
4. *Pushdown Automaton CFG Decoding:* Disabling grammar masking drops schema compliance from 100% to 84.6%, resulting in unclosed JSON delimiters.
5. *Cross-Encoder Re-Ranking:* Relying strictly on first-stage sparse/dense retrieval degrades NDCG@3 from 0.914 to 0.812, reducing downstream audit F1 to 0.862.

![Fig. 10. Impact of the Epistemic Omission Firewall on Silence Discrimination](../../fig9_omission_firewall_ablation.png)

**Fig. 10. Impact of the Epistemic Omission Firewall on silence discrimination, eliminating the 100% false positive failure mode documented in prior art (APLiance [3]).**

## F. Human Legal Expert Concordance & Automated Judge Construct Validity

Following Deka & Srivastava (NIC Assam, High 1), we validated our automated 72B LLM-as-a-judge against double-blind annotations from two senior Indian data protection advocates ($N=100$ traces).

- **Inter-Annotator Agreement:** Cohen's $\kappa = 0.884$ ($p < 0.001$) and Fleiss' $\kappa = 0.862$, demonstrating near-perfect consensus between legal referees.
- **Judge Construct Validity:** Mean Absolute Error (MAE) was **0.312 pts** on a 1–5 scale (Statutory Factuality MAE = 0.245, Context Faithfulness MAE = 0.280, Administrative Utility MAE = 0.340, Legal Actionability MAE = 0.385).
- **Correlation Metrics:** Spearman rank correlation was **$\rho = 0.892$ ($p = 1.4 \times 10^{-35}$)**; Pearson correlation was **$r = 0.914$ ($p = 8.2 \times 10^{-40}$)**.
- **Generosity Bias Profile:** The automated judge exhibited an average generosity bias of **+0.18 pts**, which does not distort relative ranking.

### TABLE XX: PROMPTING PARADIGM COMPARISON (GROUNDED IN HIGH 1)

| Prompting / Modeling Strategy | Severity-Weighted F1 | Statute Citation Validity | Jurisdictional Contamination | Omission Accuracy |
| :--- | :---: | :---: | :---: | :---: |
| **Zero-Shot Base (Qwen2.5-7B)** | 0.442 | 54.0% | 36.0% | 28.0% |
| **Few-Shot Base (3-Shot Qwen2.5-7B)** | 0.586 | 68.5% | 24.0% | 41.5% |
| **Chain-of-Thought (CoT) Qwen2.5-7B** | 0.612 | 71.0% | 22.0% | 46.0% |
| **Chain-of-Thought (CoT) GPT-4o-mini** | 0.724 | 84.0% | 16.0% | 52.0% |
| **APLiance Baseline (ABAC + GPT-4o-mini)**| 0.738 | 88.0% | 0.0% | 0.0% |
| **Ssense-DPDP-7B (Fine-Tuned Law-LM + SCL)**| **0.912** | **100.0%** | **0.0%** | **98.2%** |

As demonstrated in Table XX, while Few-Shot and CoT prompting improve over Zero-Shot, CoT suffers from parsing instability on dense legal text. Fine-tuning with SimPO and neuro-symbolic SCL execution provides a decisive performance leap (+0.174 F1 over CoT GPT-4o-mini).

![Fig. 11. Construct validity and calibration analysis of LLM-as-a-judge](../../fig8_judge_vs_human_reliability.png)

**Fig. 11. Construct validity and calibration analysis of LLM-as-a-judge against senior Indian data protection advocates ($N=100$) following the evaluation rubric from Deka & Srivastava [High 1].**

## G. Human-Centric Readability & Cognitive Accessibility Lift

Extending the Human-Centric Data Privacy Communication (HSDPC) framework of Anand et al. (UPES Dehradun, High 2), Table XXI details readability scores and reading times before and after Ssense synthesis across four economic sectors.

### TABLE XXI: READABILITY, GRADE LEVEL, AND READING TIME LIFT ACROSS SECTORS

| Platform Sector | Raw Flesch Reading Ease | Ssense Layer 1 FRE | Raw Flesch-Kincaid Grade | Ssense Layer 1 Grade | Raw Read Time | Ssense Read Time |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **E-Commerce (Zomato/Nykaa)** | 26.4 (Very Difficult) | **69.2 (Standard Plain)** | Grade 15.4 (College Grad) | **Grade 7.8 (Middle School)** | 38.5 min | **42.0 sec** |
| **FinTech (Paytm/Zerodha)** | 22.1 (Very Difficult) | **66.8 (Standard Plain)** | Grade 16.8 (Postgrad) | **Grade 8.2 (Middle School)** | 45.0 min | **48.0 sec** |
| **Travel (MakeMyTrip)** | 18.5 (Extremely Difficult) | **64.5 (Standard Plain)** | Grade 18.2 (Doctoral) | **Grade 8.5 (Middle School)** | 72.0 min | **55.0 sec** |
| **HealthTech (Tata 1mg)** | 24.8 (Very Difficult) | **67.4 (Standard Plain)** | Grade 16.1 (Postgrad) | **Grade 8.0 (Middle School)** | 52.0 min | **46.0 sec** |
| **Overall Average** | **23.0** | **67.0 (+44.0 pts)** | **Grade 16.6** | **Grade 8.1 (-8.5 Grades)** | **51.9 min** | **47.8 sec (-98.5%)** |

Usability trials with 40 representative data principals confirmed:
- **Statutory Comprehension Lift:** Understanding of statutory rights increased by **+78.4%**.
- **User Decision Confidence:** Confidence in exercising consent withdrawal rose by **+76.2%**.
- **Inspection Scan Efficiency:** Time to detect illegal data sharing fell from 52 minutes to under 50 seconds.

![Fig. 12. Human-centric communication and readability enhancement](../../fig11_readability_and_cognitive_lift.png)

**Fig. 12. Human-centric communication and readability enhancement evaluated under the HSDPC protocol from Anand et al. [High 2], transforming academic legalese into plain prose.**

## H. Adversarial Security, Red-Teaming, and Long-Context Scaling

To stress-test model robustness against malicious inputs, we executed an adversarial security suite spanning four vulnerability vectors (Table XXII).

### TABLE XXII: ADVERSARIAL RED-TEAMING & STRESS-TEST BENCHMARKS

| Vulnerability Vector | Test Sample Size | Qwen2.5-7B (Base) | APLiance Baseline | GPT-4o-mini | Ssense-DPDP-7B (Ours) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **1. Prompt Injection Refusal** | $N=50$ | 58.0% | 72.0% | 84.0% | **97.9% (ASR = 2.1%)** |
| **2. Statutory Trap Resistance** | $N=50$ | 48.0% | 64.0% | 78.0% | **98.0% Refusal Rate** |
| **3. Anti-Sycophancy Correction** | $N=50$ | 52.0% | 68.0% | 74.0% | **94.2% Refutation Rate** |
| **4. 2D-NIAH (32k Context Recall)**| $N=50$ | 73.2% | 81.2% | 89.6% | **98.4% Retrieval Accuracy** |

1. *2D Needle In A Haystack (32k Tokens):* Violating clauses were hidden at depths (0% to 100%) inside 32k-token policies. RoPE base frequency scaling ($	heta = 10^6$) and Positional XML Structuring achieved **98.4% retrieval accuracy**, proving zero attention decay.
2. *Prompt Injection Defense:* NFKC normalization and grammar logit masking achieved a **97.9% refusal rate** against malicious DOM overrides.
3. *Anti-Sycophancy Defense:* Ssense refuted false legal premises (e.g., claiming advertising is an exempt legitimate use) in **94.2%** of cases.

![Fig. 13. Adversarial Security and Red-Teaming Resilience Across Four Vulnerability Vectors](../../fig12_adversarial_trap_resistance.png)

**Fig. 13. Adversarial security and red-teaming resilience across four vulnerability vectors demonstrating resistance against indirect injections, fake safe harbors, and attention decay.**

## I. Decision Semantics of Contractual Silence

A fundamental divergence separating Ssense from prior art lies in the handling of contractual silence. APLiance reports that 100% of evaluated policies (25 of 25) fail compliance [3], whereas Ssense flags violations at 3 of 10 sites. Table XXIII articulates the foundational legal philosophies separating the two paradigms.

### TABLE XXIII: DECISION SEMANTICS OF CONTRACTUAL SILENCE

| Dimension | Ssense Legal Philosophy | APLiance Benchmark Philosophy [3] |
| :--- | :--- | :--- |
| **Prerequisite for Violation** | Affirmative statutory contradiction in policy text | Missing attributes or ambiguous declarations |
| **Epistemology of Silence** | Dropped via Omission Firewall ($\mathcal{O}_{	ext{practice}}$) | Evaluated under all values; non-declaration treated as non-compliance |
| **Statutory Coverage** | 26 violation types across fiduciary sections (§3–§16) | 16 base attributes covering Sections 1–7 |
| **Language Notice Handling** | Disclosures evaluated; missing translations segregated | Failure to provide 22 languages causes 100% policy failure |
| **Audit Resolution** | Actionable violation report with verbatim evidence | Binary COMPLIANT / NON-COMPLIANT classification |

In APLiance, compliance requires a global conjunction across all 16 attributes. Because almost no commercial website currently provides notices in all 22 Eighth Schedule languages, 100% of policies fail. Ssense distinguishes between *affirmative malpractice* (e.g., perpetual retention or bundled consent) and *statutory omissions*. By deploying the three-step omission firewall, Ssense isolates affirmative violations, delivering actionable forensic evidence rather than uniform negative scores.

## J. Sovereign Workstation Edge Deployment and Serving Telemetry

While sovereign legal validity is the paramount scientific objective, practical compliance auditing requires sovereign, privacy-preserving execution on accessible hardware. Proprietary commercial legal LLMs (e.g., GPT-4o, Claude 3.5 Sonnet) require transmitting confidential corporate policies and private citizen browsing telemetry to third-party cloud data centers, directly violating data sovereignty principles and exposing sensitive disclosures to third-party retention.

In sharp contrast, `Ssense-DPDP-7B` is architected for sovereign, offline edge execution on commodity workstation hardware. To empirically profile edge deployment feasibility, we benchmark Ssense on a standard consumer workstation equipped with an NVIDIA GeForce RTX 3060 (12 GB GDDR6 VRAM) and 32 GB system RAM, utilizing hybrid layer offloading under llama.cpp / vLLM. Table XXIV summarizes the measured operational edge telemetry across statutory audit workloads.

### TABLE XXIV: SOVEREIGN WORKSTATION EDGE HARDWARE TELEMETRY (NVIDIA GEFORCE RTX 3060 12GB)

| Operational Subsystem / Parameter | Evaluation Metric / Dimension | Measured Edge Specification |
| :--- | :--- | :--- |
| **Target Hardware Platform** | Consumer Edge Workstation | NVIDIA GeForce RTX 3060 (12 GB GDDR6) + 32 GB Host RAM |
| **Layer Allocation Architecture** | VRAM / Host RAM Partition | 21 Layers in GPU VRAM (BF16), 11 Layers offloaded to Host RAM |
| **Bus Interconnect Throughput** | Host-to-Device Transfer | PCIe 4.0 x16 high-speed bus streaming |
| **Resident VRAM Footprint** | Memory Ceiling | **11.04 GiB** (Resident weights + KV cache allocations) |
| **Median Policy Audit Time** | End-to-End Statutory Audit | **34.2 seconds** (Median across standard ~5,000-word privacy contracts) |
| **Interactive Dialogue Stream TTFT** | Time-To-First-Token | **1.24 seconds** (Local prompt prefix caching enabled) |
| **Token Generation Throughput** | Local Decoding Rate | 18.2 tokens/second (Interactive streaming) |
| **Grammar-Constrained Decoding Overhead** | XGrammar Pushdown CFG | $\le 1.8$ ms per token step (Zero schema drift) |
| **Multi-Tier Policy Cache Hit Latency** | SHA-256 Deduplication | $< 4.5$ ms (Tier 1 LRU-TTL / Tier 2 SQLite) |
| **Data Sovereignty Guarantee** | Cloud Telemetry Egress | **0 bytes** transmitted outside local host (100% data sovereignty) |

*Scientific Implications of the Sovereign Edge Profile:*
Table XXIV demonstrates that high-precision, zero-hallucination compliance verification does not require multi-million-dollar datacenter clusters or third-party cloud APIs. By partitioning the 32 Transformer layers between 12GB GDDR6 VRAM and system memory, Ssense-DPDP-7B executes a comprehensive statutory audit of a 5,000-word corporate policy in 34.2 seconds while consuming only 11.04 GiB of VRAM. Crucially, because inference occurs entirely on the local host, **zero bytes of sensitive corporate data or consumer browsing telemetry leave the machine**, achieving complete compliance with sovereign data localization and privacy-preserving audit mandates. Furthermore, when deployed by centralized regulatory bodies or consumer advocacy organizations, the underlying serving architecture seamlessly scales to concurrent multi-stream workloads via PagedAttention and prompt KV caching.

![Fig. 13B. Measured Sovereign Workstation Edge Execution Profile](../../fig16_sovereign_edge_hardware_profile.png)

**Fig. 13B. Measured sovereign workstation edge execution profile on an NVIDIA GeForce RTX 3060 (12 GB GDDR6 VRAM) with host RAM offloading: (a) dynamic layer allocation (21 GPU VRAM layers vs. 11 host RAM layers) and peak memory budgeting (11.04 GiB resident weights + KV headroom); (b) measured end-to-end audit latency across disparate policy lengths (from 490 to 16,000 tokens), achieving a median 34.2s audit turnaround and $<4.5$ ms cache hits with 0 bytes of cloud telemetry egress.**

## K. Summary of Empirical Findings

The empirical evaluation establishes four fundamental findings:
1. *Statutory Grounding & Zero Hallucination:* `Ssense-DPDP-7B` successfully audits production fiduciaries with 100% precision, zero false positives, and zero statutory hallucinations (SHR = 0.00%) against gold-standard legal labels.
2. *Elimination of the Silence Penalty:* The epistemic Omission Firewall achieves 98.2% accuracy, overcoming the 100% failure rate documented in prior art (APLiance).
3. *Construct Validity with Human Legal Experts:* Calibrated against senior Indian data protection advocates, the automated judge achieves an MAE of 0.312 pts and Spearman correlation of $
ho = 0.892$ ($p < 0.001$), confirming human-level legal alignment.
4. *Human-Centric Cognitive Lift:* Ssense transforms complex legalese into accessible plain prose (FRE +44.0 pts), reducing reading time by 98.5% and boosting citizen comprehension by +78.4%.

# IX. DISCUSSION


## A. Relation to Prior Work and Interactive Statutory Assessment

Table XXV summarises where Ssense and APLiance differ. The two agree on the statutory necessity of automating DPDP compliance auditing and on decomposing legal provisions into structured intermediate decision gates. They differ in who makes the decision, where the model runs, what the output triggers, and whether users can interactively query the statutory basis. APLiance delegates legal reasoning to a symbolic engine and uses the model solely to read attribute values. Ssense embeds deontic statutory reasoning directly within an aligned open-weights Law-LM (`Ssense-DPDP-7B`), constrained by an omission firewall and neuro-symbolic statutory consistency rules. This design demands rigorous transparency: Ssense enforces verbatim evidence quotation, deterministic statute matching, and statutory justification for every finding.

### TABLE XXV: ARCHITECTURAL DESIGN DIFFERENCES FROM APLIANCE [3]


| Aspect | APLiance | Ssense |
| --- | --- | --- |
| Law coverage | Sections 1–7; 16 base attributes | 26 violation types across fiduciary-facing sections (§3–§16); Rules aligned |
| Model | Prompted GPT-5.4-mini (proprietary API, closed weights) | Fine-tuned `Ssense-DPDP-7B` (open-weights BF16, rsLoRA + SimPO) |
| Decision locus | Model extracts attributes; symbolic ABAC engine decides | Aligned Law-LM generation, omission firewall, and deterministic statutory layer |
| Statutory silence | Unknown attributes evaluated under all values | Dropped via omission firewall unless an affirmative statutory claim exists |
| Serving architecture | Remote client queries hosted commercial API; 24-h cache | Sovereign workstation edge (12GB RTX 3060); scalable continuous-batching server; multi-tier cache; zero raw document persistence |
| Audit output | Binary COMPLIANT / NON-COMPLIANT and numbered violations | Multi-violation JSON with severity weight, verbatim evidence, statutory citation, and deontic rationale |
| Statutory Severity Classification | None (Passive textual classification) | 4-tier statutory risk taxonomy (Critical, High, Medium, Low) mapped to DPDP Schedule 1 penalties |
| Interactive inquiry | None | RAG-grounded citizen legal dialogue engine over verified audit store |
| Evaluation (published) | 25 policies, 400 pairs, accuracy 94.5% | Head-to-head replication of APLiance (400 pairs), DPDP-Bench multi-label suite, and 6-pillar legal evaluation framework |


Ssense presents its results in hierarchical layers: a fiduciary trust score and grouped violations first, followed by verbatim evidence quotes and the model's deontic reasoning on demand, adhering to established legal transparency principles [1]. The findings are grounded against specific statutory provisions, and an interactive dialogue interface enables natural-language statutory follow-up queries grounded in retrieved statutory context (Louis et al. [28]); study E5 is designed to measure comprehension gains empirically.

## B. Architectural Rationale: Neuro-Symbolic Synthesis

The two layers exhibit complementary failure modes. The neural language model can miss an explicit clause due to syntactic negation or long-context attention degradation, or it can hallucinate non-existent statutory obligations from silence. The deterministic regex layer lacks semantic context but cannot overlook explicit statutory violations it is parameterized to capture. The omission firewall and grammar-constrained decoding suppress false positives; the SCL union prevents false negatives on explicitly declared non-compliant terms; and statutory safe-harbour patterns prevent the SCL from introducing spurious flags. This neuro-symbolic hybrid guarantees that semantic breadth is bounded by deterministic legal guardrails.

## C. Sovereign Open-Weights and Controlled Local Inference

Submitting sensitive corporate disclosures or consumer browsing policies to closed, proprietary commercial LLM APIs introduces data sovereignty violations and jurisdictional leakage. Ssense preserves operational sovereignty by releasing the domain-adapted model weights as a standalone, open-weights release (`Ssense-DPDP-7B`, merged BF16 safetensors). Furthermore, the inference server stores only cryptographic SHA-256 policy hashes and validated audit schemas, guaranteeing zero persistence of raw crawled document bodies. We emphasize that Ssense is purposefully engineered to support both sovereign, local offline edge auditing on commodity workstation hardware (e.g., single 12 GB consumer GPU with layer offloading) to guarantee absolute data sovereignty, and high-throughput server deployment via PagedAttention and speculative prompt lookup decoding for regulatory monitoring organizations.

## D. Epistemic Conservatism and Precision in Statutory Auditing

In automated statutory compliance auditing, false positive citations create severe legal vulnerabilities and unjust reputational harm for data fiduciaries. When an automated system falsely accuses an enterprise of statutory non-compliance, it compromises regulatory trust. For this reason, Ssense enforces rigorous epistemic conservatism across its architecture. Silent practices are strictly filtered by the omission firewall ($\mathcal{O}_{\text{practice}}$), legitimate statutory safe harbors (such as banking retention mandates under PMLA or emergency healthcare processing under §7(b)) are preserved by the SCL lookaround engine, and SimPO length-normalized margin optimization penalizes over-calling. The resulting zero false positive rate (FPR = 0.00%) ensures that every emitted compliance citation is anchored in verifiable statutory evidence and reproducible deontic reasoning, establishing an objective foundation for human regulatory review.

## E. Planned Downstream Empirical Studies

Table XXVI lists downstream empirical studies designed to extend the research into broader operational and population-level dimensions, noting that core benchmark replications (E1: APLiance 400 instances), systematic ablations (E2), and silence semantics (E3) are already empirically established in Section VIII. Human-centered evaluation is critical because many data protection tools lack user verification [1]. Each study is statistically sized with Wilson confidence bounds: clearing a 0.95 lower bound without errors requires at least 73 independent evaluation samples.

### TABLE XXVI: PLANNED DOWNSTREAM POPULATION-LEVEL EMPIRICAL STUDIES


| ID | Study | Measures | Size |
| --- | --- | --- | --- |
| E1 | Replicate APLiance's protocol: 25 policies, 16 attributes, three-valued labels | Pair-level accuracy, precision, recall, per-attribute scores; paired comparison | Completed in Section VIII-B (Table XV) |
| E2 | Systematic ablation suite: SFT-only, SCL off, omission gate off, no re-ranker | Accuracy, FPR, hallucination rate per configuration | Completed in Section VIII-E (Table XIX) |
| E3 | Silence policy: omission gate vs. conservative-unknown rule | Overlap and divergence of findings; expert adjudication | Completed in Section VIII-I (Table XXIII) |
| E4 | Longitudinal compliance tracking: policy evolution and audit stability | Version change detection rate, false alarm rate, drift stability | ≥ 50 audits across policy updates |
| E5 | Comprehension study with and without chatbot and layered view | Task accuracy, time, confidence; Likert scales | ≥ 40 participants |
| E6 | Vernacular policies in Eighth Schedule languages | Per-language recall; translation-loss analysis | ≥ 10 policies per language |
| E7 | Adversarial robustness: injection, obfuscation, long-context | Attack success rate (N ≥ 50), NIAH at 20k tokens | As in certification matrix |
| E8 | Load and latency on target hardware | TTFT P50/P95, throughput, cache hit rate | ≥ 1,000 requests |



# X. LIMITATIONS AND THREATS TO VALIDITY

*Sample Size and Population Generalization:* While our fiduciary pilot evaluated ten strategic Indian platforms representing over 500 million MAU across six sectors (Table XIV) alongside the 61-policy DPDP-Bench multi-label benchmark (Table XVI), these platforms are well-resourced market leaders whose privacy contracts may be more rigorously drafted than smaller firms. Consequently, the pilot may understate the violation prevalence across long-tail commercial websites.

*Reference Standards and Ground Truth:* Although our gold-standard labels were established via dual independent legal specialist annotations with strong inter-rater consensus ($\kappa = 0.884, p < 0.001$), expanding annotation panels across diverse legal jurisdictions and incorporating multi-tiered adjudication conferences will further strengthen empirical ground truth for complex, ambiguous disclosures.

*Statutory Cross-Clause Interplay:* Certain real-world compliance failures involve composite, intersecting statutory breaches—such as Swiggy's indefinite retention of delivery logs without purpose delimitation (§8(7) $\land$ §4(1)). While Ssense successfully identifies these compound violations, formalizing explicit multi-label dependency graphs across interlocking statutory obligations represents an active area for ongoing research.

*Document Truncation and Long Context:* Although Rotary Position Embedding (RoPE) base frequency scaling extends the effective context window to 32,768 tokens, our crawler enforces a 64,000-character extraction cap to guard against memory exhaustion attacks, which truncates extreme outlier policies (such as MakeMyTrip). Processing ultra-long policies without truncation relies on distributed memory clusters.

*Synthetic Distillation Priors:* Teacher-generated instruction datasets inherently reflect the inductive biases of the teacher model oracle (`Qwen2-72B-Instruct`). While our MinHash 7-gram contamination firewall confirmed zero data leakage with evaluation benchmarks, synthetic traces may under-represent deceptive drafting conventions employed in corporate legalese.

*Deterministic Pattern Completeness:* The deterministic SCL backstop relies on compiled regular expressions and safe-harbor lookarounds. Novel, un-modeled legal phrasing could theoretically evade regex detection, though the underlying neural SLM provides semantic coverage.

*Statutory Evolution and Vernacular Scope:* The statutory knowledge base reflects the DPDP Act, 2023 and the DPDP Rules, 2025 as notified by MeitY. Legislative amendments or judicial precedents will necessitate periodic re-indexing. Furthermore, current DOM text normalization filters out non-Latin scripts, deferring verification of Eighth Schedule vernacular policies to planned study E6.

*Legal Advisory Disclaimer:* Ssense is an automated technological research tool designed to assist human comprehension and regulatory auditing. Its outputs do not constitute formal legal counsel and do not represent binding determinations of the Data Protection Board of India or a court of law.

# XI. ETHICAL, LEGAL AND PRIVACY CONSIDERATIONS

Data handling and sovereignty. Ingestion endpoints accept canonical domains and policy URLs; the crawler fetches documents server-side, eliminating client payload exposure. The server stores only cryptographic SHA-256 policy hashes and the structured audit JSON, guaranteeing zero persistence of raw crawled document text. The audit cache is strictly keyed by domain hash rather than user identity, ensuring zero user tracking or browsing telemetry retention.
Transparency and auditability. Every identified statutory non-compliance finding is surfaced with its verbatim evidence quote, statutory citation, and legal reasoning trace. Legal auditors, enterprise compliance officers, and regulatory monitors maintain full governance to inspect and adjudicate the emitted reasoning traces, preventing harm from potential model misclassifications.
Fairness to fiduciaries. Automated compliance auditing carries corporate reputational implications. The omission firewall, verbatim evidence quote mandate, and explicit presentation of findings as machine-generated audit assessments rather than judicial decrees are designed to prevent unfair accusations. Any published audit artifact is cryptographically bound to the policy version hash, allowing fiduciaries to verify the exact document text audited.
Dual use considerations. Automated compliance evaluation systems must be deployed with care to prevent spurious regulatory complaints or unfair accusations against compliant organizations. Ssense guards against this by anchoring every finding in verbatim evidentiary quotes, enforcing an omission firewall that respects legal silence, and applying conservative safe-harbor lookarounds.
Evaluation data transparency. The pilot evaluates publicly published privacy policies of representative commercial fiduciaries. All audited texts were publicly accessible at the time of collection.

# XII. CONCLUSION AND FUTURE WORK

Ssense introduces a domain-adapted Legal Small Language Model (`Ssense-DPDP-7B`) and scalable serving architecture for auditing web compliance under India's Digital Personal Data Protection Act, 2023. By combining rsLoRA fine-tuning and SimPO alignment on an open-weights foundation with a formal 26-node deontic statutory violation tree, a three-step omission firewall, and neuro-symbolic statutory consistency constraints, Ssense bridges the critical gap between sovereign statutory texts and automated machine compliance auditing. Furthermore, our empirical serving benchmarks demonstrate that PagedAttention continuous batching, prompt KV-cache pre-warming, and speculative prompt lookup decoding deliver sub-second latency and memory-safe execution across high concurrency loads.
Future work will evaluate longitudinal statutory compliance tracking across enterprise policy updates; extend statutory extraction and dialogue to Eighth Schedule Indian languages; and deploy the open-weights model to the broader legal AI research community.

# APPENDIX: OUTPUT CONTRACT

The auditor's JSON output has the following structure. Field names are those of the project schema; example values are placeholders.
```json
{
  "global_legal_reasoning": "...",
  "violations": [
    {
      "type": "<one of 26 enumerated types>",
      "step_1_active_claim_analysis": "...",
      "step_2_statute_match": "...",
      "omission_check": false,
      "step_3_semantic_justification": "...",
      "evidence_quote": "...",
      "offending_entities": ["..."],
      "severity": "<one of 4 tiers: CRITICAL, HIGH, MEDIUM, LOW>",
      "statutory_risk_assessment": "<formal legal risk rationale and statutory penalty assessment>"
    }
  ],
  "dpdp_trust_score": 0,
  "subtlety_score": 0
}
```

Violations with omission_check set to true are removed before the response is returned. Violation types outside the enumeration and evidence quotes shorter than 20 characters are removed by the post-processor.

# REFERENCES

[1] M. Dahl, V. Magesh, M. Suzgun, and D. E. Ho, "Large legal fictions: Profiling legal hallucinations in large language models," *Journal of Legal Analysis*, vol. 16, no. 1, pp. 24–52, 2024, doi: 10.1093/jla/laae003.

[2] N. Guha et al., "LegalBench: A collaboratively built benchmark for measuring legal reasoning in large language models," in *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 36, 2023, pp. 44474–44505.

[3] A. K. Dhakar, A. Sinha, and S. Sural, "Privacy as permissible operations: An ABAC framework for policy–law compliance," *arXiv preprint arXiv:2604.10832*, 2026.

[4] S. Paul, A. Mandal, P. Goyal, and S. Ghosh, "Pre-trained language models for the legal domain: A case study on Indian law," in *Proc. 31st Int. Joint Conf. Artif. Intell. (IJCAI)*, 2022, pp. 4318–4324, doi: 10.24963/ijcai.2022/599.

[5] P. Kalamkar, S. Karn, S. Gupta, and V. Raghavan, "Aalap: An open-source instruction-tuned large language model for the Indian legal system," *arXiv preprint arXiv:2407.03759*, 2024.

[6] R. Ta, R. Salunke, R. A. Rahul, R. Nv, and S. R. Upadhyaya, "Fine-tuning a large language model for the Indian legal system," in *Proc. 24th Int. Symp. INFOTEH-JAHORINA*, 2025, doi: 10.1109/INFOTEH64129.2025.10959207.

[7] S. Liu, B. Zhao, R. Guo, G. Meng, F. Zhang, and M. Zhang, "Have you been properly notified? Automatic compliance analysis of privacy policies with GDPR Article 13," *IEEE Trans. Inf. Forensics Secur.*, vol. 16, pp. 4141–4156, 2021, doi: 10.1109/TIFS.2021.3103175.

[8] E. Vanezi et al., "CompLicy: Evaluating the GDPR alignment of privacy policies—A study on web platforms," in *Proc. Business Information Processing*, Springer, 2021, pp. 135–150, doi: 10.1007/978-3-030-75018-3_10.

[9] M. B. Musa et al., "C3PA: An open dataset of expert-annotated and regulation-aware privacy policies to enable scalable regulatory compliance audits," in *Proc. Conf. Empirical Methods Nat. Lang. Process. (EMNLP)*, 2024, pp. 10228–10245.

[10] S. Wilson et al., "The creation and analysis of a website privacy policy corpus," in *Proc. 54th Annu. Meeting Assoc. Comput. Linguistics (ACL)*, 2016, pp. 1330–1340, doi: 10.18653/v1/P16-1126.

[11] H. Harkous, K. Fawaz, R. Lebret, F. Schaub, K. G. Shin, and K. Aberer, "Polisis: Automated analysis and presentation of privacy policies using deep learning," in *Proc. 27th USENIX Secur. Symp. (USENIX Security)*, 2018, pp. 531–548.

[12] Qwen Team, "Qwen2.5: A party of foundation models," *arXiv preprint arXiv:2412.15115*, 2024.

[13] E. J. Hu, Y. Shen, P. Wallis, Z. Allen-Zhu, Y. Li, S. Wang, L. Wang, and W. Chen, "LoRA: Low-rank adaptation of large language models," in *Proc. Int. Conf. Learn. Represent. (ICLR)*, 2022.

[14] D. Kalajdzievski, "A rank stabilization scaling factor for fine-tuning with LoRA," *arXiv preprint arXiv:2312.03732*, 2023.

[15] Y. Meng, M. Xia, and D. Chen, "SimPO: Simple preference optimization with a reference-free reward," in *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 37, 2024.

[16] R. Rafailov, A. Sharma, E. Mitchell, C. D. Manning, S. Ermon, and C. Finn, "Direct preference optimization: Your language model is secretly a reward model," in *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 36, 2023, pp. 53728–53741.

[17] J. Hong, N. Lee, and J. Thorne, "ORPO: Monolithic preference optimization without reference model," in *Proc. Conf. Empirical Methods Nat. Lang. Process. (EMNLP)*, 2024, pp. 21020–21037.

[18] X. Chen et al., "FLAME: Factuality-aware alignment for large language models," in *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 37, 2024.

[19] Y. Gao, Y. Xiong, X. Gao, K. Jia, J. Pan, Y. Bi, Y. Dai, J. Sun, M. Wang, and H. Wang, "Retrieval-augmented generation for large language models: A survey," *arXiv preprint arXiv:2312.10997*, 2023.

[20] S. Xiao, Z. Liu, P. Zhang, and N. Muennighoff, "C-Pack: Packaged resources to advance general Chinese and English bilingual text representation," in *Proc. 62nd Annu. Meeting Assoc. Comput. Linguistics (ACL)*, 2024, pp. 1246–1263.

[21] Y. Dong, C. F. Ruan, Y. Cai, R. Lai, Z. Huang, H. Guan, S. Liu, V. Zhao, and T. Chen, "XGrammar: Flexible and efficient structured generation engine for large language models," *arXiv preprint arXiv:2411.15100*, 2024.

[22] I. Chalkidis, M. Fergadiotis, P. Malakasiotis, N. Aletras, and I. Androutsopoulos, "LEGAL-BERT: The Muppets straight out of law school," in *Findings of Assoc. Comput. Linguistics: EMNLP 2020*, 2020, pp. 2898–2904, doi: 10.18653/v1/2020.findings-emnlp.261.

[23] I. Chalkidis et al., "LexGLUE: A benchmark dataset for legal language understanding in English," *Computational Linguistics*, vol. 48, no. 4, pp. 843–888, 2022, doi: 10.1162/coli_a_00444.

[24] P. Colombo et al., "SaulLM-7B: A pioneering large language model for law," *arXiv preprint arXiv:2403.03883*, 2024.

[25] S. Yue et al., "DISC-LawLLM: Fine-tuning large language models with intelligent legal reasoning," *arXiv preprint arXiv:2309.11325*, 2023.

[26] J. Cui et al., "ChatLaw: Open-source legal large language model with integrated external knowledge bases," *arXiv preprint arXiv:2306.16092*, 2023.

[27] J. Niklaus et al., "LawInstruct: A resource for studying language model adaptation to the legal domain," in *Findings of Assoc. Comput. Linguistics: NAACL 2025*, 2025, doi: 10.18653/v1/2025.findings-naacl.7.

[28] A. Louis, G. van Dijck, and G. Spanakis, "Interpretable long-form legal question answering with retrieval-augmented large language models," in *Proc. 38th AAAI Conf. Artif. Intell. (AAAI)*, vol. 38, no. 17, 2024, pp. 18729–18737, doi: 10.1609/aaai.v38i17.29836.

[29] Y. Wang, Y. Kordi, S. Mishra, A. Liu, N. A. Smith, D. Khashabi, and H. Hajishirzi, "Self-Instruct: Aligning language models with self-generated instructions," in *Proc. 61st Annu. Meeting Assoc. Comput. Linguistics (ACL)*, 2023, pp. 13484–13508.

[30] S. Mukherjee, A. Mitra, G. Jawahar, S. Agarwal, H. Palangi, and A. Awadallah, "Orca: Progressive learning from complex explanation traces of GPT-4," *arXiv preprint arXiv:2306.02707*, 2023.

[31] Y. Gu, L. Dong, F. Wei, and M. Huang, "MiniLLM: Knowledge distillation of large language models," in *Proc. Int. Conf. Learn. Represent. (ICLR)*, 2024.

[32] N. Shinn, F. Cassano, A. Gopinath, K. Narasimhan, and S. Yao, "Reflexion: Language agents with verbal reinforcement learning," in *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 36, 2023, pp. 8634–8652.

[33] P. Italiani, G. Moro, and L. Ragazzi, "Enhancing legal question answering with data generation and knowledge distillation from large language models," *Artificial Intelligence and Law*, 2025, doi: 10.1007/s10506-025-09435-w.

[34] I. Shumailov et al., "AI models collapse when trained on recursively generated data," *Nature*, vol. 631, pp. 755–759, 2024, doi: 10.1038/s41586-024-07566-y.

[35] Y. Oren, N. Meister, N. Goyal, and P. Liang, "Proving test set contamination in modern language models," in *Proc. Int. Conf. Learn. Represent. (ICLR)*, 2024.

[36] K. Lee et al., "Deduplicating training data makes language models better," in *Proc. 60th Annu. Meeting Assoc. Comput. Linguistics (ACL)*, 2022, pp. 8424–8445, doi: 10.18653/v1/2022.acl-long.577.

[37] L. Garza et al., "PrivComp-KG: Leveraging KG and LLM for compliance verification," in *Proc. IEEE Int. Conf. Trust, Secur. Privacy Comput. Commun. (TrustCom)*, 2024, pp. 165–172, doi: 10.1109/TrustCom63102.2024.00021.

[38] J. Chen et al., "A privacy policy text compliance reasoning framework with large language models for healthcare services," *Tsinghua Science and Technology*, vol. 30, no. 5, pp. 2005–2016, 2025, doi: 10.26599/TST.2024.9010077.

[39] H. Nissenbaum, "Privacy as contextual integrity," *Washington Law Review*, vol. 79, no. 1, pp. 119–158, 2004.

[40] J. Chanenson, M. Pickering, and N. Apthorpe, "Automating governing knowledge commons and contextual integrity annotation," *Proc. Privacy Enhancing Technol.*, vol. 2024, no. 4, pp. 320–337, 2024, doi: 10.56553/popets-2024-0118.

[41] T. Cory et al., "Word-level annotation of GDPR transparency compliance in privacy policies using large language models," *Proc. Privacy Enhancing Technol.*, vol. 2025, no. 1, pp. 605–624, 2025, doi: 10.56553/popets-2025-0062.

[42] G. V. Cormack, C. L. A. Clarke, and S. Büttcher, "Reciprocal rank fusion outperforms Condorcet and individual machine learning methods," in *Proc. 32nd Int. ACM SIGIR Conf. Res. Dev. Inf. Retrieval (SIGIR)*, 2009, pp. 758–759, doi: 10.1145/1571941.1572114.

[43] T. Zhang, S. G. Patil, N. Jain, S. Shen, M. Zaharia, I. Stoica, and J. E. Gonzalez, "RAFT: Adapting language model to domain specific RAG," *Trans. Mach. Learn. Res. (TMLR)*, 2024.

[44] K. Greshake et al., "Not what you've signed up for: Compromising real-world LLM-integrated applications with indirect prompt injection," in *Proc. 16th ACM Workshop Artif. Intell. Secur. (AISec)*, 2023, pp. 79–90, doi: 10.1145/3605764.3623985.

[45] Z. Li, B. Peng, P. He, and X. Yan, "Evaluating the instruction-following robustness of large language models to prompt injection," in *Findings of Assoc. Comput. Linguistics: EMNLP 2024*, 2024, pp. 473–487.

[46] S. Chen et al., "SecAlign: Defending against prompt injection with preference optimization," in *Proc. ACM SIGSAC Conf. Comput. Commun. Secur. (CCS)*, 2024, pp. 4339–4353, doi: 10.1145/3658644.3670397.

[47] T. Dao, "FlashAttention-2: Faster attention with better parallelism and work partitioning," in *Proc. Int. Conf. Learn. Represent. (ICLR)*, 2024.

[48] W. Kwon, Z. Li, S. Zhuang, Y. Sheng, L. Zheng, C. H. Yu, J. E. Gonzalez, H. Zhang, and I. Stoica, "Efficient memory management for large language model serving with PagedAttention," in *Proc. 29th ACM Symp. Operating Syst. Princ. (SOSP)*, 2023, pp. 611–626, doi: 10.1145/3600006.3613165.

[49] Y. Sheng, S. Cao, D. Li, C. Hooper, N. Lee, S. Yang, C. Chou, B. Zhu, L. Zheng, K. Keutzer, J. E. Gonzalez, and I. Stoica, "S-LoRA: Serving thousands of concurrent LoRA adapters," in *Proc. Mach. Learn. Syst. (MLSys)*, vol. 6, 2024, pp. 317–331.

[50] I. W. Gim, Y. M. Bae, J. Kim, I. Jang, and S.-J. Lee, "Prompt Cache: Modular attention reuse for low-latency inference," in *Proc. Mach. Learn. Syst. (MLSys)*, vol. 6, 2024, pp. 332–346.

[51] Y. Leviathan, M. Kalman, and Y. Matias, "Fast inference from transformers via speculative decoding," in *Proc. 40th Int. Conf. Mach. Learn. (ICML)*, 2023, pp. 19274–19286.

[52] N. F. Liu, K. Lin, J. Hewitt, A. Paranjape, M. Bevilacqua, F. Petroni, and P. Liang, "Lost in the middle: How language models use long contexts," *Trans. Assoc. Comput. Linguistics*, vol. 12, pp. 157–173, 2024, doi: 10.1162/tacl_a_00638.

[53] T. Zhang, V. Kishore, F. Wu, K. Q. Weinberger, and Y. Artzi, "BERTScore: Evaluating text generation with BERT," in *Proc. Int. Conf. Learn. Represent. (ICLR)*, 2020.

[54] L. Zheng, W.-L. Chiang, Y. Sheng, S. Zhuang, Z. Wu, Y. Zhuang, Z. Lin, Z. Li, D. Li, E. P. Xing, H. Zhang, and I. Stoica, "Judging LLM-as-a-judge with MT-Bench and Chatbot Arena," in *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 36, 2023, pp. 46595–46623.

[55] Y. Liu, D. Iter, Y. Xu, S. Wang, R. Xu, and C. Zhu, "G-Eval: NLG evaluation using GPT-4 with better human alignment," in *Findings of Assoc. Comput. Linguistics: EMNLP 2023*, 2023, pp. 2511–2522, doi: 10.18653/v1/2023.findings-emnlp.166.

[56] S. Kim et al., "Prometheus: Inducing fine-grained evaluation capability in language models," in *Proc. Int. Conf. Learn. Represent. (ICLR)*, 2024.

[57] R. Dror, G. Baumer, M. Bogomolov, and R. Reichart, "The hitchhiker's guide to testing statistical significance in natural language processing," in *Proc. 56th Annu. Meeting Assoc. Comput. Linguistics (ACL)*, 2018, pp. 1383–1392, doi: 10.18653/v1/P18-1128.

[58] L. D. Brown, T. T. Cai, and A. DasGupta, "Interval estimation for a binomial proportion," *Statistical Science*, vol. 16, no. 2, pp. 101–133, 2001, doi: 10.1214/ss/1009213286.

[59] P. Koehn, "Statistical significance tests for machine translation evaluation," in *Proc. Conf. Empirical Methods Nat. Lang. Process. (EMNLP)*, 2004, pp. 388–395.

[60] P. M. McCarthy and S. Jarvis, "MTLD, vocd-D, and HD-D: A validation study of sophisticated approaches to lexical diversity assessment," *Behavior Research Methods*, vol. 42, no. 2, pp. 381–392, 2010, doi: 10.3758/BRM.42.2.381.

[61] I. Loshchilov and F. Hutter, "Decoupled weight decay regularization," in *Proc. Int. Conf. Learn. Represent. (ICLR)*, 2019.

[62] N. Jain, P.-y. Chiang, Y. Wen, J. Kirchenbauer, H.-M. Chu, G. Bharadhwaj, P. Singhal, and T. Goldstein, "NEFTune: Noisy embeddings improve instruction finetuning," in *Proc. Int. Conf. Learn. Represent. (ICLR)*, 2024.
