//! Shared utilities for the Ssense workspace.
//! Ensures consistent domain normalization, hashing, and data sanitization 
//! across the Rust utilities, the SQLite cache, and auxiliary tooling.

use sha2::{Digest, Sha256};

/// Normalizes a domain by stripping protocol, path, and common prefixes ("www.", "en.", "m.", "app.").
/// This ensures 'https://www.amazon.com/path', 'www.amazon.com', and 'amazon.com' share the exact same SQLite cache key,
/// strictly matching the SLM server's `audit_store.py::_normalise`.
pub fn normalize_domain(domain: &str) -> String {
    let mut low = domain.trim().to_lowercase();
    // Strip protocol if present
    if let Some(pos) = low.find("://") {
        low = low[pos + 3..].to_string();
    }
    // Strip path and query parameters if present
    if let Some(pos) = low.find('/') {
        low = low[..pos].to_string();
    }
    if let Some(pos) = low.find(':') {
        low = low[..pos].to_string();
    }
    // Strip common subdomains
    for prefix in &["www.", "en.", "m.", "app."] {
        if low.starts_with(prefix) {
            low = low[prefix.len()..].to_string();
            break;
        }
    }
    low
}

/// Generates a cryptographically stable SHA-256 hash of a normalized domain.
/// This is used as the PRIMARY KEY in the SQLite cache.
pub fn hash_domain(domain: &str) -> String {
    let normalized = normalize_domain(domain);
    let mut hasher = Sha256::new();
    hasher.update(normalized.as_bytes());
    format!("{:x}", hasher.finalize())
}

/// Sanitizes and clamps the trust score to strictly enforce the 0-100 boundary
/// defined in the dpdp_schema.json, protecting against LLM hallucinations.
pub fn sanitize_trust_score(score: i32) -> i32 {
    if score < 0 {
        0
    } else if score > 100 {
        100
    } else {
        score
    }
}

/// Validates that a string satisfies the minimum character constraint
/// of the `evidence_quote` field in the strict JSON schema (minLength: 20 in dpdp_schema.json).
pub fn is_valid_evidence_quote(quote: &str) -> bool {
    let trimmed = quote.trim();
    !trimmed.is_empty() && trimmed.len() >= 20
}

/// Validates that a violation type string exactly matches the 26 allowed enums
/// in the dpdp_schema.json and the SLM server's security validation layer.
pub fn is_valid_violation_type(v_type: &str) -> bool {
    matches!(
        v_type,
        "PURPOSE_LIMITATION_VIOLATION"
            | "CONSENT_NOT_FREE_OR_SPECIFIC"
            | "LEGITIMATE_USES_ABUSE"
            | "NOTICE_INADEQUATE"
            | "DATA_RETENTION_LIMIT_EXCEEDED"
            | "ERASURE_NOTICE_PERIOD_VIOLATION"
            | "LOG_RETENTION_MANDATE_VIOLATION"
            | "CHILD_CONSENT_VIOLATION"
            | "SECURITY_SAFEGUARDS_MISSING"
            | "GRIEVANCE_REDRESSAL_INADEQUATE"
            | "BREACH_NOTIFICATION_FAILURE"
            | "PROCESSOR_ACCOUNTABILITY_VIOLATION"
            | "SDF_OBLIGATIONS_MISSING"
            | "SDF_DATA_LOCALIZATION_VIOLATION"
            | "CROSS_BORDER_TRANSFER_VIOLATION"
            | "CONSENT_MANAGER_OBSTRUCTION"
            | "LANGUAGE_ACCESSIBILITY"
            | "ALGORITHMIC_PROFILING_SDF"
            | "RIGHTS_IMPLEMENTATION_VIOLATION"
            | "DATA_ACCURACY_COMPLETENESS_VIOLATION"
            | "BOARD_COMPLIANCE_VIOLATION"
            | "PENALTY_AVOIDANCE"
            | "APPEAL_PROCESS_VIOLATION"
            | "SCOPE_APPLICATION_EVASION"
            | "ILLEGAL_EXEMPTION_CLAIM"
            | "CONSENT_MECHANICS_VIOLATION"
    )
}

/// Validates that a network action string exactly matches the 5 allowed enums
/// in the dpdp_schema.json.
pub fn is_valid_network_action(action: &str) -> bool {
    matches!(
        action,
        "BLOCK_THIRD_PARTY"
            | "STRIP_TELEMETRY_HEADER"
            | "SPOOF_HARDWARE_API"
            | "INJECT_GPC_SIGNAL"
            | "WARN_USER_ONLY"
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_domain_normalization() {
        assert_eq!(normalize_domain("WWW.Swiggy.com"), "swiggy.com");
        assert_eq!(normalize_domain("https://www.Amazon.com/privacy"), "amazon.com");
        assert_eq!(normalize_domain("en.wikipedia.org"), "wikipedia.org");
        assert_eq!(normalize_domain("m.facebook.com"), "facebook.com");
        assert_eq!(normalize_domain("app.slack.com:8080"), "slack.com");
        assert_eq!(normalize_domain("example.com"), "example.com");
    }

    #[test]
    fn test_domain_hashing_consistency() {
        let hash1 = hash_domain("www.example.com");
        let hash2 = hash_domain("example.com");
        let hash3 = hash_domain("https://example.com/privacy");
        assert_eq!(hash1, hash2, "Hashes must match regardless of 'www.' prefix");
        assert_eq!(hash2, hash3, "Hashes must match regardless of protocol and path");
        
        // Ensure it's a valid 64-char hex string (SHA-256)
        assert_eq!(hash1.len(), 64);
    }

    #[test]
    fn test_trust_score_clamping() {
        assert_eq!(sanitize_trust_score(-50), 0);
        assert_eq!(sanitize_trust_score(150), 100);
        assert_eq!(sanitize_trust_score(85), 85);
    }

    #[test]
    fn test_evidence_quote_validation() {
        assert!(!is_valid_evidence_quote(""));
        assert!(!is_valid_evidence_quote("   "));
        assert!(!is_valid_evidence_quote("Too short quote"));
        assert!(is_valid_evidence_quote("We collect your biometric and precise location data continuously without consent."));
    }

    #[test]
    fn test_schema_enum_validation() {
        // Original 10 enums
        assert!(is_valid_violation_type("NOTICE_INADEQUATE"));
        assert!(is_valid_violation_type("PURPOSE_LIMITATION_VIOLATION"));
        assert!(is_valid_violation_type("CHILD_CONSENT_VIOLATION"));
        assert!(is_valid_violation_type("CROSS_BORDER_TRANSFER_VIOLATION"));

        // Newly synchronized 16 enums from dpdp_schema.json
        assert!(is_valid_violation_type("LEGITIMATE_USES_ABUSE"));
        assert!(is_valid_violation_type("ERASURE_NOTICE_PERIOD_VIOLATION"));
        assert!(is_valid_violation_type("LOG_RETENTION_MANDATE_VIOLATION"));
        assert!(is_valid_violation_type("PROCESSOR_ACCOUNTABILITY_VIOLATION"));
        assert!(is_valid_violation_type("SDF_DATA_LOCALIZATION_VIOLATION"));
        assert!(is_valid_violation_type("CONSENT_MANAGER_OBSTRUCTION"));
        assert!(is_valid_violation_type("LANGUAGE_ACCESSIBILITY"));
        assert!(is_valid_violation_type("ALGORITHMIC_PROFILING_SDF"));
        assert!(is_valid_violation_type("RIGHTS_IMPLEMENTATION_VIOLATION"));
        assert!(is_valid_violation_type("DATA_ACCURACY_COMPLETENESS_VIOLATION"));
        assert!(is_valid_violation_type("BOARD_COMPLIANCE_VIOLATION"));
        assert!(is_valid_violation_type("PENALTY_AVOIDANCE"));
        assert!(is_valid_violation_type("APPEAL_PROCESS_VIOLATION"));
        assert!(is_valid_violation_type("SCOPE_APPLICATION_EVASION"));
        assert!(is_valid_violation_type("ILLEGAL_EXEMPTION_CLAIM"));
        assert!(is_valid_violation_type("CONSENT_MECHANICS_VIOLATION"));

        // Invalid violation type
        assert!(!is_valid_violation_type("UNKNOWN_VIOLATION"));

        // Network actions
        assert!(is_valid_network_action("BLOCK_THIRD_PARTY"));
        assert!(is_valid_network_action("STRIP_TELEMETRY_HEADER"));
        assert!(is_valid_network_action("SPOOF_HARDWARE_API"));
        assert!(is_valid_network_action("INJECT_GPC_SIGNAL"));
        assert!(is_valid_network_action("WARN_USER_ONLY"));
        assert!(!is_valid_network_action("UNKNOWN_ACTION"));
    }
}