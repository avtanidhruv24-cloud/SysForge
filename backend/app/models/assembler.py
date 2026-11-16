"""
SysForge — Assembler domain models.

Covers the output contracts for:
  - Macro Processor   → MacroResult
  - Assembler Pass-I  → Pass1Result  (SYMTAB, LITTAB, POOLTAB, intermediate code)
  - Assembler Pass-II → Pass2Result  (object / machine code)

These are the data structures the frontend ``/macro``, ``/pass-one``,
``/symbols``, ``/literals``, ``/pools``, ``/intermediate``, ``/pass-two``,
and ``/object-code`` views will render.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from engine.common.enums import (
    IntermediateClass,
    OperandType,
)


# ---------------------------------------------------------------------------
# Macro Processor models
# ---------------------------------------------------------------------------


class MacroDefinition(BaseModel):
    """A macro definition extracted from the source."""

    name: str = Field(description="Macro name (uppercase).")
    parameters: list[str] = Field(
        default_factory=list,
        description="Formal parameter names, in order.",
    )
    body_lines: list[str] = Field(
        default_factory=list,
        description="Source lines forming the macro body (before expansion).",
    )
    definition_line: int = Field(
        ge=1, description="1-based line where MACRO directive appears."
    )


class MacroCall(BaseModel):
    """A single invocation of a macro in the source."""

    name: str = Field(description="Name of the called macro.")
    arguments: list[str] = Field(
        default_factory=list,
        description="Actual argument values passed to the macro.",
    )
    call_line: int = Field(
        ge=1, description="1-based source line of the call."
    )
    expansion_lines: list[str] = Field(
        default_factory=list,
        description="Expanded source lines replacing this call.",
    )


class MacroResult(BaseModel):
    """Complete output of the Macro Processor stage."""

    expanded_source: str = Field(
        default="",
        description="Full source after all macro definitions removed and calls expanded.",
    )

    definitions: list[MacroDefinition] = Field(
        default_factory=list,
        description="All macro definitions found in the source.",
    )

    calls: list[MacroCall] = Field(
        default_factory=list,
        description="All macro invocations encountered, with their expansions.",
    )

    diagnostics: list[dict] = Field(
        default_factory=list,
        description="Errors or warnings from the macro processor.",
    )

    success: bool = Field(default=True)


# ---------------------------------------------------------------------------
# Symbol Table
# ---------------------------------------------------------------------------


class SymbolTableEntry(BaseModel):
    """
    One entry in the Symbol Table (SYMTAB).

    Built by Assembler Pass-I.  Each label encountered in the source is
    assigned the value of the Location Counter (LC) at its definition point.

    Frontend column mapping:
        Symbol → name
        Value  → value
        Section → defined_at_line
        Binding → is_defined
    """

    name: str = Field(description="Symbol name (label), uppercase.")

    value: int = Field(
        description="Numeric value assigned to the symbol (LC at definition)."
    )

    defined_at_line: int | None = Field(
        default=None,
        ge=1,
        description="1-based source line where the symbol is defined.",
    )

    is_defined: bool = Field(
        default=True,
        description=(
            "``True`` if the symbol has been defined (has a known value).  "
            "``False`` for forward references not yet resolved in Pass-I."
        ),
    )

    references: list[int] = Field(
        default_factory=list,
        description="1-based line numbers where this symbol is referenced.",
    )

    index: int | None = Field(
        default=None,
        description="1-based index in the Symbol Table.",
    )

    forward_reference: bool = Field(
        default=False,
        description="Whether this symbol was referenced before its definition.",
    )

    status: str = Field(
        default="DEFINED",
        description="Status: 'DEFINED', 'UNRESOLVED', or 'REDEFINED'.",
    )


# ---------------------------------------------------------------------------
# Literal Table
# ---------------------------------------------------------------------------


class LiteralTableEntry(BaseModel):
    """
    One entry in the Literal Table (LITTAB).

    Literals are constant values written in the form ``='n'``.  Pass-I
    collects all literals into pools; Pass-II assigns them memory addresses.

    Frontend column mapping:
        Literal → value
        Pool    → pool_index
        Address → address
        Width   → width
    """

    value: str = Field(
        description="Literal as it appears in the source, e.g. ``='5'``."
    )

    numeric_value: int | None = Field(
        default=None,
        description="Parsed integer value of the literal.",
    )

    pool_index: int = Field(
        ge=0,
        description="0-based index of the literal pool this literal belongs to.",
    )

    address: int | None = Field(
        default=None,
        description="Memory address assigned in Pass-II / LTORG processing.",
    )

    width: int = Field(
        default=1,
        ge=1,
        description="Storage width in words (always 1 for simple literals).",
    )

    first_seen_line: int | None = Field(
        default=None,
        ge=1,
        description="1-based source line where this literal first appears.",
    )

    index: int | None = Field(
        default=None,
        description="1-based index in the Literal Table.",
    )

    references: list[int] = Field(
        default_factory=list,
        description="1-based source lines referencing this literal.",
    )


# ---------------------------------------------------------------------------
# Pool Table
# ---------------------------------------------------------------------------


class PoolTableEntry(BaseModel):
    """
    One entry in the Pool Table (POOLTAB).

    A new pool starts at the beginning of the program and after each
    ``LTORG`` directive.  The pool table records the index into LITTAB
    where each pool begins.

    Frontend column mapping:
        Pool           → pool_index
        Starts at      → littab_start_index
        Literal count  → literal_count
        Boundary       → ltorg_line
    """

    pool_index: int = Field(
        ge=0, description="0-based pool sequence number."
    )

    littab_start_index: int = Field(
        ge=0,
        description="0-based index in LITTAB where this pool's literals begin.",
    )

    literal_count: int = Field(
        ge=0,
        description="Number of literals in this pool.",
    )

    ltorg_line: int | None = Field(
        default=None,
        ge=1,
        description=(
            "1-based source line of the LTORG (or END) that closed this pool.  "
            "``None`` for the initial pool if LTORG was not yet encountered."
        ),
    )

    pool_number: int | None = Field(
        default=None,
        description="1-based pool sequence number (for display).",
    )

    ending_literal_index: int | None = Field(
        default=None,
        description="0-based ending index in LITTAB for this pool.",
    )

    trigger: str | None = Field(
        default=None,
        description="Trigger that closed this pool: 'LTORG', 'END', or None.",
    )



# ---------------------------------------------------------------------------
# Intermediate Code
# ---------------------------------------------------------------------------


class OperandField(BaseModel):
    """A single operand field in an intermediate code record."""

    type: OperandType = Field(description="Operand type tag (R, S, L, C, CC, -).")
    value: str = Field(
        description=(
            "Resolved operand value: register number, symbol name, "
            "literal index, constant, or condition code number."
        )
    )


class IntermediateRecord(BaseModel):
    """
    One record in the Intermediate Code representation.

    Produced by Assembler Pass-I.  Each executable or data-definition
    statement generates one record; directives (START, END, etc.) may also
    generate records for tracking.

    Standard educational format:
        (class, opcode/index, operand1, operand2)

    Frontend column mapping:
        Line           → source_line
        Class          → statement_class
        Opcode         → opcode_value
        Operand fields → operands
    """

    source_line: int = Field(ge=1, description="1-based source line.")

    location_counter: int = Field(
        ge=0,
        description="Value of the Location Counter at this statement.",
    )

    statement_class: IntermediateClass = Field(
        description="IS (imperative), DL (declarative), or AD (directive)."
    )

    opcode_value: int | None = Field(
        default=None,
        description=(
            "Numeric opcode (imperative) or pseudo-opcode (declarative/directive)."
        ),
    )

    mnemonic: str | None = Field(
        default=None,
        description="Original mnemonic string for display purposes.",
    )

    operands: list[OperandField] = Field(
        default_factory=list,
        description="Operand fields, in order (up to two for most instructions).",
    )

    label: str | None = Field(
        default=None,
        description="Label defined on this line, if any.",
    )


class LCTraceEntry(BaseModel):
    """
    One entry in the Location Counter (LC) trace.

    Records the step-by-step evolution of the Location Counter across each
    processed statement, explaining the transition for educational transparency.
    """

    source_line: int = Field(ge=1, description="1-based source line number.")
    statement: str = Field(description="Statement representation (e.g. 'MOVER AREG, =''5''').")
    lc_before: int | None = Field(default=None, description="LC before processing this statement.")
    action: str = Field(description="Action description (e.g. 'Advance LC by 1', 'Allocate literal').")
    lc_after: int | None = Field(default=None, description="LC after processing this statement.")
    explanation: str | None = Field(
        default=None,
        description="Deterministic educational explanation of this step.",
    )


# ---------------------------------------------------------------------------
# Pass-I Result
# ---------------------------------------------------------------------------


class Pass1Result(BaseModel):
    """
    Complete output of Assembler Pass-I.

    Contains the four canonical artifacts: SYMTAB, LITTAB, POOLTAB, and
    the Intermediate Code.  The frontend ``/pass-one`` view renders the
    flow diagram; the sub-views ``/symbols``, ``/literals``, ``/pools``,
    and ``/intermediate`` each render one artifact table.
    """

    symbol_table: list[SymbolTableEntry] = Field(
        default_factory=list,
        description="Symbol Table (SYMTAB): all defined symbols and their values.",
    )

    literal_table: list[LiteralTableEntry] = Field(
        default_factory=list,
        description="Literal Table (LITTAB): all literals encountered.",
    )

    pool_table: list[PoolTableEntry] = Field(
        default_factory=list,
        description="Pool Table (POOLTAB): pool boundaries.",
    )

    intermediate_code: list[IntermediateRecord] = Field(
        default_factory=list,
        description="Intermediate Code: one record per source statement.",
    )

    starting_address: int | None = Field(
        default=None,
        description="Program starting address from the START directive.",
    )

    final_location_counter: int | None = Field(
        default=None,
        description="Location Counter value after Pass-I completes.",
    )

    lc_trace: list[LCTraceEntry] = Field(
        default_factory=list,
        description="Step-by-step Location Counter trace.",
    )

    processed_statement_count: int = Field(
        default=0,
        ge=0,
        description="Number of statements processed.",
    )

    unresolved_symbol_count: int = Field(
        default=0,
        ge=0,
        description="Number of symbols remaining unresolved at EOF.",
    )

    literal_count: int = Field(
        default=0,
        ge=0,
        description="Total literals registered.",
    )

    pool_count: int = Field(
        default=0,
        ge=0,
        description="Total literal pools formed.",
    )

    diagnostics: list[dict] = Field(
        default_factory=list,
        description="Pass-I errors or warnings.",
    )

    success: bool = Field(default=True)



# ---------------------------------------------------------------------------
# Object / Machine Code
# ---------------------------------------------------------------------------


class RelocationEntry(BaseModel):
    """Records a relocation that the linker must apply."""

    address: int = Field(description="Address of the word requiring relocation.")
    type: str = Field(
        default="absolute",
        description="Relocation type: 'absolute' or 'relative'.",
    )
    symbol: str | None = Field(
        default=None,
        description="External symbol name this relocation references.",
    )


class ObjectWord(BaseModel):
    """
    One machine word in the object code output.

    Each ``ObjectWord`` corresponds to one memory location and carries
    the encoded instruction or data value produced by Pass-II.

    Encoding for imperative instructions::

        word = opcode * 1000 + register_number * 100 + operand_address
        e.g.  MOVER AREG ='5' at address 110 → 5 * 1000 + 1 * 100 + <lit_addr>

    Frontend column mapping:
        Address     → address
        Word        → encoded_word
        Relocations → relocations
        Source      → source_line
    """

    address: int = Field(
        ge=0, description="Memory address where this word is placed."
    )

    encoded_word: int | None = Field(
        default=None,
        description="Encoded machine word value.  ``None`` for DS-reserved words.",
    )

    mnemonic: str | None = Field(
        default=None,
        description="Original mnemonic (for display / debugging).",
    )

    source_line: int | None = Field(
        default=None,
        ge=1,
        description="1-based source line that generated this word.",
    )

    relocations: list[RelocationEntry] = Field(
        default_factory=list,
        description="Relocation entries that apply to this word.",
    )

    is_data: bool = Field(
        default=False,
        description="``True`` for DC/DS words; ``False`` for instruction words.",
    )


class Pass2Result(BaseModel):
    """Complete output of Assembler Pass-II."""

    object_code: list[ObjectWord] = Field(
        default_factory=list,
        description="Machine words in address order.",
    )

    diagnostics: list[dict] = Field(
        default_factory=list,
        description="Pass-II errors or warnings.",
    )

    success: bool = Field(default=True)
