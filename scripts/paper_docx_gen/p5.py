H1("V. LEGAL FORMALIZATION AND COMPUTATIONAL STATUTORY MODELING")
H2("A. 26-Node Actionable Violation Taxonomy")
BP("Let S_Act = {1,...,44} denote the 44 DPDP Act, 2023 sections and R_Rules = {1,...,22} the 22 DPDP Rules, 2025, plus Schedules 1-3. Partitioning away state adjudicatory provisions (S.18-26, 29-32) and Board inquiry procedures (Rules 17-22) yields actionable compliance space U_fiduciary. We construct formal 26-node statutory decision tree T_statute defining taxonomy V_26. Each leaf node v maps to quadruple v = (sigma(v), rho(v), mu(v), omega(s(v))) where sigma(v) is the governing section, rho(v) the enforcement rule, mu(v) the deontic modality, and omega(s(v)) in {30, 20, 10, 5} the statutory penalty severity weight. Citations are looked up deterministically from T_statute at inference time, mathematically eliminating fabricated statutory references.")
TC("TABLE IV: Complete 26-Node Statutory Violation Taxonomy (DPDP Act 2023 & Rules 2025)")
t=doc.add_table(rows=1,cols=5); t.style="Table Grid"; t.alignment=WD_TABLE_ALIGNMENT.CENTER
TH(t,["Deontic Domain","Violation Type Enum","Governing Section & Rule","Severity","Penalty Weight omega"],7)
TR(t,[
    ["Consent Architecture","CONSENT_NOT_FREE_OR_SPECIFIC","S.6(1), Rule 4","High","omega=20"],
    ["","CONSENT_MECHANICS_VIOLATION","S.6(1), S.6(4), Rule 4(2)","High","omega=20"],
    ["","CONSENT_MANAGER_OBSTRUCTION","S.6(7)-(9), Rule 5","Medium","omega=10"],
    ["","PENALTY_AVOIDANCE","S.33, Schedule 1","High","omega=20"],
    ["Notice & Transparency","NOTICE_INADEQUATE","S.5(1), Rule 3(1)","Medium","omega=10"],
    ["","LANGUAGE_ACCESSIBILITY","S.5(3), Rule 3(2)","Low","omega=5"],
    ["","BOARD_COMPLIANCE_VIOLATION","S.6(10), S.27-28, Rule 14-16","Medium","omega=10"],
    ["Purpose & Retention","PURPOSE_LIMITATION_VIOLATION","S.7, S.8(7), Rule 8(2)","High","omega=20"],
    ["","DATA_RETENTION_LIMIT_EXCEEDED","S.8(7), Third Sched., Rule 8(1)","High","omega=20"],
    ["","ERASURE_NOTICE_PERIOD_VIOLATION","S.8(7), S.12(3), Rule 8(3)","Medium","omega=10"],
    ["","LEGITIMATE_USES_ABUSE","S.7","High","omega=20"],
    ["","ILLEGAL_EXEMPTION_CLAIM","S.17, Second Sched.","High","omega=20"],
    ["Vulnerable & Cross-Border","CHILD_CONSENT_VIOLATION","S.9(1)-(3), Rule 10","Critical","omega=30"],
    ["","CROSS_BORDER_TRANSFER_VIOLATION","S.16, Second Sched., Rule 13(4)","Critical","omega=30"],
    ["","SCOPE_APPLICATION_EVASION","S.3(b)","Critical","omega=30"],
    ["","SDF_DATA_LOCALIZATION_VIOLATION","S.10(2)(b), S.16, Rule 13(4)","Critical","omega=30"],
    ["","SDF_OBLIGATIONS_MISSING","S.10(1)-(2), Rule 6","High","omega=20"],
    ["","ALGORITHMIC_PROFILING_SDF","S.10(2)(b), Rule 6(2)","High","omega=20"],
    ["Security & Accountability","SECURITY_SAFEGUARDS_MISSING","S.8(5), Rule 6(1)(e)","Medium","omega=10"],
    ["","BREACH_NOTIFICATION_FAILURE","S.8(6), Rule 7","High","omega=20"],
    ["","LOG_RETENTION_MANDATE_VIOLATION","Rule 8(1), CERT-In 6h","Medium","omega=10"],
    ["","PROCESSOR_ACCOUNTABILITY_VIOLATION","S.8(2), Rule 6(1)(d)","Medium","omega=10"],
    ["","DATA_ACCURACY_COMPLETENESS_VIOLATION","S.8(3), Rule 6(1)(a)","Low","omega=5"],
    ["Rights & Grievance","GRIEVANCE_REDRESSAL_INADEQUATE","S.13(1), Rule 11","Medium","omega=10"],
    ["","RIGHTS_IMPLEMENTATION_VIOLATION","S.11, S.12, Rule 9","Medium","omega=10"],
    ["","APPEAL_PROCESS_VIOLATION","S.13(3), Rule 12","Low","omega=5"],
],7)
FT(t)
H2("B. Epistemology of Legal Silence: Affirmative Duty vs. Conditional Omission")
BP("Conditional Prohibitions (P_conditional) such as S.9 (child tracking) and S.16 (cross-border transfers) apply only if the fiduciary actively engages in those practices. Mandatory Affirmative Disclosures (O_disclosure) such as S.5(1) and S.13 impose unconditional duties. Ssense enforces a Three-Step Deductive Reasoning Chain: Step 1 (AuditStep_1) extracts verbatim affirmative text span E from policy T_policy. Step 2 (AuditStep_2) maps E to governing provision sigma = TreeLookup(v), v in V_26. Step 3 (AuditStep_3) generates deontic justification delta = Deduce(E |= not DPDP(sigma)). If E is empty or derives from unstated practices on a conditional prohibition (sigma not in O_disclosure), the binary flag omission_check=True is asserted. The inference firewall mechanically drops all findings where omission_check=True before report emission.")
H2("C. Trust Score and Subtlety Score")
BP("Trust Score T in [0,100]: T = max(0, 100 - sum_{v in V_confirmed} w(s(v))), w(Critical)=30, w(High)=20, w(Medium)=10, w(Low)=5. Subtlety Score S in [0,100] estimates concealment effectiveness via parse-tree depth, passive-voice ratio, and hedging marker frequency.")
print("legal formalization ok")
