"""
Security Utilities

This module provides security utilities for the application.
"""

import re
from typing import Optional

from langsmith import traceable


class InputSanitizer:
  
  INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"forget\s+(all\s+)?previous",
    r"new\s+instructions\s*:",
    r"system\s*prompt",
    r"==-\s*end\s*(of)?\s*prompt",
    r"pretend\s+you\s+are",
    r"act\s+as\s+(if\s+)?you",
    r"bypass\s+(all\s+)?restrictions",
    r"reveal\s+(your|the)\s+(system|instructions|prompt)",
    r"you\s+are\s+now\s+(DAN|jailbroken)",
  ]
  
  def __init__(self):
    self.patterns = [
      re.compile(pattern, re.IGNORECASE)
      for pattern in self.INJECTION_PATTERNS
    ]
    
  def check(self, text: str) -> tuple[bool, Optional[str]]:
    """
    Check if input safe
    Returns: (is_safe, rejection_reason)
    """
    for pattern in self.patterns:
      if pattern.search(text):
        return False, "Blocked: potential prompt injection detected"
    return True, None
  
  def clean(self, text: str) -> str:
    """Remove potential dangerous delimiters from input."""
    text = re.sub(r'[-]{3,}', '', text)
    text = re.sub(r'[=]{3,}', '', text)
    text = text.replace('{{', '{ {').replace('}}', '} }')
    return text.strip()

class PIIDetector:
  """
  Detect and mask Personal Identifiable Information (PII) in text.
  Works on BOTH input (before LLM) and output (before client).
  """
  
  PATTERNS = {
    "email": re.compile(
      r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    ),
    "phone": re.compile(
      r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',
    ),
    "ssn": re.compile(
      r'\b\d{3}-\d{2}-\d{4}\b',
    ),
    "credit_card": re.compile(
      r'\b\d{4}[-.\s]?\d{4}[-.\s]?\d{4}[-.\s]?\d{4}\b',
    ),
  }
  
  MASK_MAP = {
    "email": "[EMAIL REDACTED]",
    "phone": "[PHONE REDACTED]",
    "ssn": "[SSN REDACTED]",
    "credit_card": "[CREDIT CARD REDACTED]",
  }
  
  def detect(self, text: str) -> dict[str, list[str]]:
    """Detect PII types present in text."""
    found = {}
    for pii_type, pattern in self.PATTERNS.items():
      matches = pattern.findall(text)
      if matches:
        found[pii_type] = matches
    return found
  
  def mask(self, text: str) -> str:
    """Replace all PII with redaction markers."""
    for pii_type, pattern in self.PATTERNS.items():
      text = pattern.sub(self.MASK_MAP[pii_type], text)
    return text
  
class OutputValidator:
  """
  Validate LLM output before returning to the client.
  Catches PII leakage and harmful content in responses.  
  """
  
  HARMFUL_PATTERNS = [
    re.compile(r"here('s| is) (how|the way) to (hack|steal|attack)", re.I),
    re.compile(r"password\s+is\s+", re.I),
    re.compile(r"api[_\s]?key\s*[:=]", re.I),
  ]
  
  def __init__(self):
    self.pii_detector = PIIDetector()
    
  def validate(self, output: str) -> tuple[str, list[str]]:
    """
    Validate and clean output.
    Returns: (cleaned_output, list_of_warnings)
    """
    
    warnings = []
    
    # check for PII leakage in output
    pii_found = self.pii_detector.detect(output)
    if pii_found:
      output = self.pii_detector.mask(output)
      warnings.append(f"PII masked in output: {list(pii_found.keys())}")
      
    # Check for harmful content
    for pattern in self.HARMFUL_PATTERNS:
      if pattern.search(output):
        output = "[Response blocked: potentially harmful content]"
        warnings.append("Harmful content blocked in response")
        
    return output, warnings
  
class SecurityPipeline:
  """
  Full security pipeline for input and output.
  This is the single class you wire into your API.
  """
  
  
  def __init__(self):
    self.sanitizer = InputSanitizer()
    self.pii_detector = PIIDetector()
    self.output_validator = OutputValidator()
    
  @traceable(name="security_check_input")
  def check_input(self, text: str) -> tuple[bool, str , list[str]]:
    """
    Process input through the security checks.
    Returns: (is_allowed, cleaned_text, security_notes)
    """
    
    notes = []
    
    # Step 1: Check for injection
    is_safe, reason = self.sanitizer.check(text)
    if not is_safe:
      return False, "", [reason]
    
    
    # Step 2: clean input
    cleaned = self.sanitizer.clean(text)
    
    # Step 3: Mask PII before it reaches the LLM
    pii_found = self.pii_detector.detect(cleaned)
    if pii_found:
      cleaned = self.pii_detector.mask(cleaned)
      notes.append(f"PII masked in input: {list(pii_found.keys())}")
    
    return True, cleaned, notes
  
  @traceable(name="security_check_output")
  def check_output(self, output: str) -> tuple[str, list[str]]:
    """
    Process output through the security checks.
    Returns: (cleaned_output, security_notes)
    """
    return self.output_validator.validate(output)
    