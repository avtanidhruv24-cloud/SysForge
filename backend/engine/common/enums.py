"""
SysForge educational assembly language — canonical enumeration definitions.

This module is the single source of truth for every keyword, mnemonic,
register, directive, condition code, and stage identifier used across the
entire SysForge toolchain.

Rules
-----
- Do NOT use x86, ARM, NASM, MASM, or any real-world ISA terminology.
- Every new language keyword must be added here first, then referenced
  from the lexer/parser/assembler — never hard-coded in engine logic.
- All enums use ``StrEnum`` so their values are plain strings that survive
  JSON serialisation without an extra ``.value`` call.
"""

from __future__ import annotations

from enum import StrEnum, auto


# ---------------------------------------------------------------------------
# Pipeline stage identifiers
# ---------------------------------------------------------------------------


class AnalysisStage(StrEnum):
    """
    Identifies a single stage in the SysForge transformation pipeline.

    These names match the route paths in the React frontend (e.g. the
    ``/lexical`` route corresponds to ``LEXICAL``).  They are also used as
    keys in ``AnalysisSession.results`` and as the ``stage`` field on
    ``StageStatus``.
    """

    LEXICAL = "lexical"
    SYNTAX = "syntax"
    MACRO = "macro"
    PASS_ONE = "pass-one"
    SYMBOLS = "symbols"          # Sub-view of pass-one output
    LITERALS = "literals"        # Sub-view of pass-one output
    POOLS = "pools"              # Sub-view of pass-one output
    INTERMEDIATE = "intermediate"  # Sub-view of pass-one output
    PASS_TWO = "pass-two"
    OBJECT_CODE = "object-code"
    LINKER = "linker"
    LOADER = "loader"
    MEMORY = "memory"
    EXECUTION = "execution"
    AI = "ai"
    RESULT = "result"


class StageStatus(StrEnum):
    """
    Lifecycle status of a single pipeline stage within an ``AnalysisSession``.

    - ``NOT_STARTED``    — stage has not been requested or run yet.
    - ``IN_PROGRESS``    — stage is currently executing (future: streaming).
    - ``COMPLETED``      — stage ran successfully; result is available.
    - ``ERROR``          — stage ran but produced one or more fatal errors.
    - ``NOT_IMPLEMENTED``— stage is recognised but the engine has not been
                           built yet.  The frontend shows a waiting state.
    """

    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


# ---------------------------------------------------------------------------
# Token classification
# ---------------------------------------------------------------------------


class TokenType(StrEnum):
    """
    Lexical token categories produced by the SysForge lexer.

    Each category corresponds to a distinct syntactic role in the
    educational assembly language.
    """

    # Assembler directives (START, END, ORIGIN, EQU, LTORG)
    DIRECTIVE = "DIRECTIVE"

    # Imperative mnemonics (ADD, SUB, MOVER, …)
    IMPERATIVE = "IMPERATIVE"

    # Declarative mnemonics (DC, DS)
    DECLARATIVE = "DECLARATIVE"

    # Register names (AREG, BREG, CREG, DREG)
    REGISTER = "REGISTER"

    # Condition codes used with BC (LT, LE, EQ, GT, GE, ANY)
    CONDITION_CODE = "CONDITION_CODE"

    # A user-defined symbolic label or symbol reference
    SYMBOL = "SYMBOL"

    # An integer constant (e.g. the operand of DC, or START address)
    NUMBER = "NUMBER"

    # A literal value enclosed in quotes (e.g. ='5')
    LITERAL = "LITERAL"

    # A source-code comment (; …)
    COMMENT = "COMMENT"

    # Signals end-of-line / end-of-statement
    NEWLINE = "NEWLINE"

    # Signals end-of-file / end-of-source
    EOF = "EOF"

    # Catch-all for characters the lexer could not classify
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Assembler directives
# ---------------------------------------------------------------------------


class Directive(StrEnum):
    """
    Assembler directives in the SysForge educational assembly language.

    These are processed by the assembler (Pass-I) and do NOT generate
    machine instructions directly.
    """

    START = "START"    # Marks program start; operand sets initial LC value
    END = "END"        # Marks program end; triggers final LTORG if needed
    ORIGIN = "ORIGIN"  # Sets the location counter to the given expression
    EQU = "EQU"        # Assigns a symbolic name to a constant expression
    LTORG = "LTORG"    # Closes the current literal pool; assigns addresses


# ---------------------------------------------------------------------------
# Imperative (executable) mnemonics
# ---------------------------------------------------------------------------


class ImperativeMnemonic(StrEnum):
    """
    Executable instructions in the SysForge educational ISA.

    These generate machine code words during Assembler Pass-II.
    Opcodes (numeric values) are defined in the engine's MOT/POT tables —
    not here.
    """

    ADD = "ADD"        # Rx ← Rx + operand
    SUB = "SUB"        # Rx ← Rx − operand
    MULT = "MULT"      # Rx ← Rx × operand
    MOVER = "MOVER"    # Rx ← value(operand)
    MOVEM = "MOVEM"    # memory[operand] ← Rx
    COMP = "COMP"      # Set condition code: Rx vs operand
    BC = "BC"          # Branch on condition code
    DIV = "DIV"        # Rx ← Rx ÷ operand
    READ = "READ"      # memory[operand] ← next input token
    PRINT = "PRINT"    # output ← str(memory[operand])
    STOP = "STOP"      # Halt execution


# ---------------------------------------------------------------------------
# Declarative (data-definition) mnemonics
# ---------------------------------------------------------------------------


class DeclarativeMnemonic(StrEnum):
    """
    Data-definition pseudo-instructions in the SysForge educational language.

    These reserve or initialise storage; they advance the location counter
    but do not generate executable machine code.
    """

    DC = "DC"    # Define Constant — reserve one word and initialise it
    DS = "DS"    # Define Storage  — reserve N words (operand = count)


# ---------------------------------------------------------------------------
# Registers
# ---------------------------------------------------------------------------


class Register(StrEnum):
    """
    General-purpose registers of the SysForge Educational Virtual Machine.

    Register numbers (used in machine code encoding):
        AREG = 1, BREG = 2, CREG = 3, DREG = 4
    """

    AREG = "AREG"    # Accumulator register
    BREG = "BREG"    # B register
    CREG = "CREG"    # C register
    DREG = "DREG"    # D register


# Register number mapping — used by the assembler and VM
REGISTER_NUMBER: dict[Register, int] = {
    Register.AREG: 1,
    Register.BREG: 2,
    Register.CREG: 3,
    Register.DREG: 4,
}


# ---------------------------------------------------------------------------
# Condition codes
# ---------------------------------------------------------------------------


class ConditionCode(StrEnum):
    """
    Condition codes used with the ``BC`` (Branch on Condition) instruction.

    The VM's condition register is set by the ``COMP`` instruction and
    evaluated by ``BC``.
    """

    LT = "LT"    # Less than
    LE = "LE"    # Less than or equal
    EQ = "EQ"    # Equal
    GT = "GT"    # Greater than
    GE = "GE"    # Greater than or equal
    ANY = "ANY"  # Unconditional branch (always taken)


# Condition code number mapping — used by the assembler and VM
CONDITION_CODE_NUMBER: dict[ConditionCode, int] = {
    ConditionCode.LT: 1,
    ConditionCode.LE: 2,
    ConditionCode.EQ: 3,
    ConditionCode.GT: 4,
    ConditionCode.GE: 5,
    ConditionCode.ANY: 6,
}


# ---------------------------------------------------------------------------
# Machine Operation Table (MOT) — opcode assignments
# ---------------------------------------------------------------------------


# Maps each imperative mnemonic to its numeric opcode used in machine words.
# These values are part of the language specification and must not change.
OPCODE_TABLE: dict[ImperativeMnemonic, int] = {
    ImperativeMnemonic.STOP:  1,
    ImperativeMnemonic.ADD:   2,
    ImperativeMnemonic.SUB:   3,
    ImperativeMnemonic.MULT:  4,
    ImperativeMnemonic.MOVER: 5,
    ImperativeMnemonic.MOVEM: 6,
    ImperativeMnemonic.COMP:  7,
    ImperativeMnemonic.BC:    8,
    ImperativeMnemonic.DIV:   9,
    ImperativeMnemonic.READ:  10,
    ImperativeMnemonic.PRINT: 11,
}

# Reverse lookup: opcode → mnemonic
OPCODE_TO_MNEMONIC: dict[int, ImperativeMnemonic] = {
    v: k for k, v in OPCODE_TABLE.items()
}

# Declarative pseudo-opcodes (used in intermediate code, not in machine words)
DECLARATIVE_OPCODE_TABLE: dict[DeclarativeMnemonic, int] = {
    DeclarativeMnemonic.DC: 1,
    DeclarativeMnemonic.DS: 2,
}


# ---------------------------------------------------------------------------
# Keyword sets — used by the lexer for O(1) classification
# ---------------------------------------------------------------------------

#: All directive keywords as plain strings
DIRECTIVE_KEYWORDS: frozenset[str] = frozenset(d.value for d in Directive)

#: All imperative mnemonic keywords as plain strings
IMPERATIVE_KEYWORDS: frozenset[str] = frozenset(m.value for m in ImperativeMnemonic)

#: All declarative mnemonic keywords as plain strings
DECLARATIVE_KEYWORDS: frozenset[str] = frozenset(m.value for m in DeclarativeMnemonic)

#: All register keywords as plain strings
REGISTER_KEYWORDS: frozenset[str] = frozenset(r.value for r in Register)

#: All condition code keywords as plain strings
CONDITION_CODE_KEYWORDS: frozenset[str] = frozenset(c.value for c in ConditionCode)

#: Union of all reserved keywords — a symbol may not share a name with these
ALL_KEYWORDS: frozenset[str] = (
    DIRECTIVE_KEYWORDS
    | IMPERATIVE_KEYWORDS
    | DECLARATIVE_KEYWORDS
    | REGISTER_KEYWORDS
    | CONDITION_CODE_KEYWORDS
)


# ---------------------------------------------------------------------------
# Intermediate code class tags
# ---------------------------------------------------------------------------


class IntermediateClass(StrEnum):
    """
    Classifies a statement in the intermediate code representation.

    Each intermediate record is tagged with one of these classes so that
    Pass-II can dispatch correctly.
    """

    IS = "IS"    # Imperative Statement (executable instruction)
    DL = "DL"    # Declarative (data definition: DC, DS)
    AD = "AD"    # Assembler Directive (START, END, ORIGIN, EQU, LTORG)


# ---------------------------------------------------------------------------
# Operand type tags (used in intermediate code records)
# ---------------------------------------------------------------------------


class OperandType(StrEnum):
    """
    Tags the type of an operand field in an intermediate code record.

    Used by Pass-II to resolve each operand to its final numeric value.
    """

    REGISTER = "R"       # Register reference (AREG/BREG/CREG/DREG)
    SYMBOL = "S"         # Symbol reference (resolved via SYMTAB)
    LITERAL = "L"        # Literal reference (resolved via LITTAB)
    CONSTANT = "C"       # Immediate integer constant
    CONDITION = "CC"     # Condition code (LT/LE/EQ/GT/GE/ANY)
    NONE = "-"           # No operand (e.g. STOP)
