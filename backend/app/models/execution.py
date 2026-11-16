"""
SysForge — Execution / Virtual Machine domain models.

These are the contracts for the ``/execution`` frontend view, which renders
the Educational Virtual Machine debugger: CPU registers, condition code,
memory, program output console, and execution trace.

VM specification
----------------
Registers : PC (program counter), AREG, BREG, CREG, DREG
Condition code : LT | LE | EQ | GT | GE | ANY
Memory    : flat word-addressable array
Input     : token stream (for READ instruction)
Output    : string list (for PRINT instruction)
Trace     : one row per executed instruction

These models match the panel layout already present in the frozen frontend
``ExecutionPage`` component.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from engine.common.enums import ConditionCode, Register


# ---------------------------------------------------------------------------
# VM register state
# ---------------------------------------------------------------------------


class RegisterFile(BaseModel):
    """
    Snapshot of all CPU registers at one point in execution.

    Maps directly onto the ``cpu-registers`` panel in the frontend.
    """

    pc: int = Field(
        default=0, ge=0, description="Program Counter — address of the next instruction."
    )
    areg: int = Field(default=0, description="AREG (accumulator register) value.")
    breg: int = Field(default=0, description="BREG value.")
    creg: int = Field(default=0, description="CREG value.")
    dreg: int = Field(default=0, description="DREG value.")

    def get(self, register: Register) -> int:
        """Return the value of the named register."""
        return getattr(self, register.value.lower())


# ---------------------------------------------------------------------------
# Execution step (trace row)
# ---------------------------------------------------------------------------


class MemoryChange(BaseModel):
    """Records a single memory write that occurred during an instruction."""

    address: int = Field(ge=0, description="Memory address written.")
    old_value: int | None = Field(default=None, description="Value before the write.")
    new_value: int = Field(description="Value after the write.")


class ExecutionStep(BaseModel):
    """
    One row in the execution trace table.

    Captures the complete before/after state for a single instruction.
    The frontend ``trace-table`` renders one ``ExecutionStep`` per row.

    Frontend column mapping:
        Step            → step_number
        PC              → pc_before
        Instruction     → instruction_text
        AREG            → areg_after
        BREG            → breg_after
        CREG            → creg_after
        DREG            → dreg_after
        Condition Code  → condition_code_after
        Memory Change   → memory_changes
        Output          → output_produced
    """

    step_number: int = Field(ge=1, description="Monotonically increasing step counter.")

    pc_before: int = Field(
        ge=0, description="Value of PC before this instruction executed."
    )

    instruction_text: str = Field(
        description="Human-readable representation of the instruction (e.g. 'MOVER AREG 5')."
    )

    encoded_word: int | None = Field(
        default=None,
        description="Raw encoded machine word that was fetched and executed.",
    )

    # Register values *after* instruction execution
    areg_after: int = Field(default=0)
    breg_after: int = Field(default=0)
    creg_after: int = Field(default=0)
    dreg_after: int = Field(default=0)
    pc_after: int = Field(ge=0, description="PC value after execution (next instruction).")

    condition_code_after: ConditionCode | None = Field(
        default=None,
        description="Condition code register value after this instruction.",
    )

    memory_changes: list[MemoryChange] = Field(
        default_factory=list,
        description="All memory writes caused by this instruction.",
    )

    output_produced: str | None = Field(
        default=None,
        description="String sent to PRINT output, if this was a PRINT instruction.",
    )


# ---------------------------------------------------------------------------
# VM execution state (full snapshot)
# ---------------------------------------------------------------------------


class VMState(BaseModel):
    """
    Complete snapshot of the Virtual Machine at any point in time.

    This is what the ``/execution`` view renders for the CPU panel,
    memory panel, and condition code panel.
    """

    registers: RegisterFile = Field(default_factory=RegisterFile)

    condition_code: ConditionCode | None = Field(
        default=None,
        description="Current condition code register value.",
    )

    memory: dict[int, int] = Field(
        default_factory=dict,
        description=(
            "Live memory snapshot: address → word value.  "
            "Only populated addresses are included."
        ),
    )

    halted: bool = Field(
        default=False,
        description="``True`` after STOP executes or a fatal error occurs.",
    )

    step_count: int = Field(
        default=0,
        ge=0,
        description="Number of instructions executed so far.",
    )

    status: str = Field(
        default="NOT_STARTED",
        description=(
            "Execution lifecycle status: "
            "NOT_STARTED | RUNNING | PAUSED | HALTED | ERROR"
        ),
    )


# ---------------------------------------------------------------------------
# Execution result (full run)
# ---------------------------------------------------------------------------


class ExecutionResult(BaseModel):
    """
    Complete output returned after a VM run or step sequence.

    Combines the final ``VMState`` with the full execution trace and
    program output.  This is the payload for ``/api/v1/vm/run`` responses.
    """

    final_state: VMState = Field(
        default_factory=VMState,
        description="VM register and memory state at program end.",
    )

    trace: list[ExecutionStep] = Field(
        default_factory=list,
        description="Full execution trace — one entry per executed instruction.",
    )

    output: list[str] = Field(
        default_factory=list,
        description="Lines produced by PRINT instructions, in order.",
    )

    input_consumed: list[str] = Field(
        default_factory=list,
        description="Input tokens consumed by READ instructions.",
    )

    total_steps: int = Field(
        default=0,
        ge=0,
        description="Total number of instructions executed.",
    )

    terminated_normally: bool = Field(
        default=False,
        description="``True`` if the program ended via STOP; ``False`` on error or timeout.",
    )

    diagnostics: list[dict] = Field(
        default_factory=list,
        description="Execution errors or warnings.",
    )

    success: bool = Field(
        default=True,
        description="``False`` if a fatal runtime error occurred.",
    )
