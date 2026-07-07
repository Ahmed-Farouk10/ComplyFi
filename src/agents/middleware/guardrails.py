from __future__ import annotations

import re
from typing import Any


class InputGuardrail:
    MAX_INPUT_LENGTH = 16000
    INJECTION_PATTERNS = [
        r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|directives?|prompts?)",
        r"(?i)system:\s*$",
        r"(?i)you\s+are\s+now\s+DAN",
        r"(?i)pretend\s+you\s+are",
        r"(?i)forget\s+everything",
        r"(?i)new\s+instructions?:\s*$",
        r"(?i)bypass\s+(kyc|aml|sanctions?|compliance|screening)",
        r"(?i)mark\s+(as\s+)?(approved|verified|cleared)\s+(without|bypassing)\s+(check|screening|verification)",
    ]

    SANCTIONS_KEYWORDS = [
        r"(?i)\b(OFAC|SDN|Hizballah|Al-Qaeda|Taliban|North\s*Korea|Iran|Syria|Cuba|Crimea)\b",
        r"(?i)\b(weapon\s*of\s*mass\s*destruction|WMD)\b",
    ]

    def __init__(self, max_length: int | None = None) -> None:
        self.max_length = max_length or self.MAX_INPUT_LENGTH

    def validate(self, content: str) -> tuple[bool, str | None]:
        if not content or not content.strip():
            return False, "Input is empty or whitespace only."

        if len(content) > self.max_length:
            return False, f"Input exceeds maximum length of {self.max_length} characters (got {len(content)})."

        for pattern in self.INJECTION_PATTERNS:
            if re.search(pattern, content):
                return False, "Input matches potential prompt injection pattern."

        return True, None

    def check_sanctions_trigger(self, content: str) -> tuple[bool, list[str]]:
        hits: list[str] = []
        for pattern in self.SANCTIONS_KEYWORDS:
            if re.search(pattern, content):
                hits.append("Sanctions-related term detected in input")
                break
        return len(hits) == 0, hits


class OutputGuardrail:
    PII_PATTERNS = [
        (r"\b\d{3}-\d{2}-\d{4}\b", "US Social Security Number (SSN)"),
        (r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "Credit card / payment account number"),
        (r"\b\d{9}\b", "US routing number (9 digits)"),
        (r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b", "IBAN (International Bank Account Number)"),
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "Email address (PII)"),
        (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "IP address (potential PII)"),
        (r"\bpassport[:\s#]*[A-Z0-9]{5,15}\b", "Passport number"),
        (r"\b\d{2,4}[-\s]?\d{2,4}[-\s]?\d{4,7}\b", "Generic account number pattern"),
    ]

    TRANSACTION_LIMIT_PATTERNS = [
        (r"(?i)\btransaction\s+amount[:\s]*\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\b", "Transaction amount exposed"),
        (r"(?i)\b(amount|value)[:\s]*\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)(\s*million|\s*billion)?\b", "Monetary amount in output"),
    ]

    SANCTIONS_ESCAPE_PATTERNS = [
        (r"(?i)\b(no\s+match|clear|negative)\s+on\s+(sanctions?|watchlist|OFAC)\b", "Sanctions clearance statement"),
        (r"(?i)\boverride\b.*\b(sanctions?|screening|risk\s+score|compliance)\b", "Screening override"),
        (r"(?i)\b(suppress|skip|ignore)\b.*\b(flag|alert|warning|hit)\b", "Alert suppression"),
    ]

    def __init__(
        self,
        pii_patterns: list[tuple[str, str]] | None = None,
        txn_limit_patterns: list[tuple[str, str]] | None = None,
        sanctions_patterns: list[tuple[str, str]] | None = None,
    ) -> None:
        self.pii_patterns = pii_patterns or self.PII_PATTERNS
        self.txn_limit_patterns = txn_limit_patterns or self.TRANSACTION_LIMIT_PATTERNS
        self.sanctions_patterns = sanctions_patterns or self.SANCTIONS_ESCAPE_PATTERNS

    def validate(self, content: str) -> tuple[bool, list[str]]:
        violations: list[str] = []

        for pattern, label in self.pii_patterns:
            if re.search(pattern, content):
                violations.append(f"PII detected: {label}")

        for pattern, label in self.txn_limit_patterns:
            if re.search(pattern, content):
                violations.append(f"Financial data exposure: {label}")

        for pattern, label in self.sanctions_patterns:
            if re.search(pattern, content):
                violations.append(f"Compliance flag: {label}")

        return len(violations) == 0, violations


class Guardrails:
    def __init__(self) -> None:
        self.input_guard = InputGuardrail()
        self.output_guard = OutputGuardrail()

    def check_input(self, content: str) -> tuple[bool, str | None]:
        return self.input_guard.validate(content)

    def check_output(self, content: str) -> tuple[bool, list[str]]:
        return self.output_guard.validate(content)

    def check_sanctions(self, content: str) -> tuple[bool, list[str]]:
        return self.input_guard.check_sanctions_trigger(content)
