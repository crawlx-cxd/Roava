"""
safety.py - Safety Guardrails: Human-in-the-Loop, Step Limiter, and Audit Logging

Fulfills Requirement 6: Safety: asks you first, step limit, log (📘 L7).
- HITLManager: Asks human permission before executing state-modifying actions (save_itinerary).
- StepLimiter: Hard cap at max_steps (default 8) to halt runaway loops.
- AuditLogger: Appends every thought, action, observation, and safety check to 'agent_audit.jsonl'.
"""

from __future__ import annotations
import json
import os
import time
from typing import Dict, Any, Optional, Callable


class AuditLogger:
    """
    Appends structured JSON records to 'agent_audit.jsonl' for compliance,
    debugging, and transparency.
    """
    def __init__(self, log_filepath: str = "agent_audit.jsonl"):
        self.log_filepath = log_filepath

    def log(self,
            session_id: str,
            step_index: int,
            milestone_id: Optional[int],
            thought: str,
            action: Optional[Dict[str, Any]],
            observation: Optional[Dict[str, Any]],
            hitl_status: str = "NONE",
            is_final: bool = False) -> None:
        """Appends an immutable audit entry."""
        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "session_id": session_id,
            "step_index": step_index,
            "milestone_id": milestone_id,
            "thought": thought,
            "action": action,
            "observation": observation,
            "hitl_status": hitl_status,
            "is_final": is_final
        }
        try:
            with open(self.log_filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[AuditLogger Error] Failed to write log: {e}")

    def read_logs(self) -> list[Dict[str, Any]]:
        """Reads all audit records from disk."""
        if not os.path.exists(self.log_filepath):
            return []
        records = []
        with open(self.log_filepath, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        records.append(json.loads(line))
                    except Exception:
                        pass
        return records

    def clear(self) -> None:
        """Clears audit logs (used for test teardown)."""
        if os.path.exists(self.log_filepath):
            os.remove(self.log_filepath)


class StepLimiter:
    """
    Enforces a strict cap on the number of ReAct loop iterations (default: 8).
    Prevents infinite loops and runaway costs.
    """
    def __init__(self, max_steps: int = 8):
        self.max_steps = max_steps
        self.current_step = 0

    def reset(self) -> None:
        self.current_step = 0

    def can_proceed(self) -> bool:
        """Returns True if the agent is still within the step limit."""
        return self.current_step < self.max_steps

    def increment(self) -> int:
        """Increments and returns current step count."""
        self.current_step += 1
        return self.current_step

    def is_exceeded(self) -> bool:
        """Returns True if the hard step cap has been reached or exceeded."""
        return self.current_step >= self.max_steps


class HITLManager:
    """
    Human-in-the-Loop (HITL) Safety Gate.
    Asks the human user for explicit approval before executing any destructive,
    irreversible, or disk-writing action (e.g. save_itinerary).
    """
    def __init__(self,
                 approval_callback: Optional[Callable[[str, Dict[str, Any]], bool]] = None,
                 auto_approve: bool = False,
                 auto_reject: bool = False):
        self.approval_callback = approval_callback
        self.auto_approve = auto_approve
        self.auto_reject = auto_reject

    def request_approval(self, action_name: str, args: Dict[str, Any]) -> bool:
        """
        Prompts for human approval.
        Returns True if approved, False if denied.
        """
        if self.auto_reject:
            return False
        if self.auto_approve:
            return True

        if self.approval_callback:
            return self.approval_callback(action_name, args)

        # Default interactive CLI prompt
        print(f"\n[HITL SAFETY GATE] The agent requests permission to execute '{action_name}'.")
        print(f"Parameters: {json.dumps(args, indent=2)}")
        try:
            choice = input("Do you approve this action? (yes/no): ").strip().lower()
            return choice in ["y", "yes"]
        except (EOFError, KeyboardInterrupt):
            return False

