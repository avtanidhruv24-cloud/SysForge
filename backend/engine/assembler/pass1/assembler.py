"""
SysForge — Deterministic Educational Assembler Pass-I.

Processes a structured ``SyntaxResult`` (from the Parser) and performs
Assembler Pass-I:
  1. Manages the Location Counter (LC) with detailed transition trace.
  2. Builds the Symbol Table (SYMTAB) with forward-reference resolution.
  3. Registers literals into the Literal Table (LITTAB).
  4. Manages literal pool boundaries in the Pool Table (POOLTAB).
  5. Emits the standard educational Intermediate Code (IC).
  6. Produces structured diagnostics for duplicate symbols, undefined
     symbols, invalid directives, etc.
  7. Provides educational explanations for each step.

Educational Assembly Model
--------------------------
Directives:
    START <num>     - Sets initial Location Counter.
    END             - Flushes pending literal pool, marks program end.
    ORIGIN <expr>   - Sets Location Counter to specified address / symbol.
    EQU <expr>      - Assigns value to symbol without consuming memory.
    LTORG           - Flushes pending literals, assigns addresses, starts new pool.

Declaratives:
    DC <num>        - Defines one constant word at current LC. (LC + 1)
    DS <num>        - Reserves N memory words at current LC. (LC + N)

Imperatives:
    ADD, SUB, MULT, MOVER, MOVEM, COMP, BC, DIV, READ, PRINT, STOP
    Each consumes exactly one instruction memory word. (LC + 1)

Intermediate Code:
    Record: (class, opcode, operand1, operand2)
    Class:  IS (imperative), DL (declarative), AD (directive)
    Operands: R (register), S (symbol index), L (literal index),
              C (constant), CC (condition code), - (none)
"""

from __future__ import annotations

import re
from typing import Any

from app.core.errors import ErrorCode
from app.models.assembler import (
    IntermediateRecord,
    LCTraceEntry,
    LiteralTableEntry,
    OperandField,
    Pass1Result,
    PoolTableEntry,
    SymbolTableEntry,
)
from app.models.syntax import ParsedStatement, SyntaxResult
from engine.common.enums import (
    AnalysisStage,
    ConditionCode,
    DeclarativeMnemonic,
    Directive,
    ImperativeMnemonic,
    IntermediateClass,
    OperandType,
    OPCODE_TABLE,
    DECLARATIVE_OPCODE_TABLE,
    REGISTER_NUMBER,
    CONDITION_CODE_NUMBER,
)
from engine.common.errors import DiagnosticBag, EngineDiagnostic

# Directive pseudo-opcodes used in standard educational Intermediate Code
DIRECTIVE_OPCODE_TABLE: dict[Directive, int] = {
    Directive.START: 1,
    Directive.END: 2,
    Directive.ORIGIN: 3,
    Directive.EQU: 4,
    Directive.LTORG: 5,
}


class AssemblerPass1:
    """
    Deterministic Assembler Pass-I engine.

    Implements ``engine.interfaces.AssemblerPass1Protocol``.
    """

    def __init__(self) -> None:
        pass

    def assemble(self, syntax_result: SyntaxResult) -> Pass1Result:
        """
        Execute Pass-I over the parsed statements.

        Args:
            syntax_result: Output from Parser.

        Returns:
            Complete ``Pass1Result`` with SYMTAB, LITTAB, POOLTAB,
            Intermediate Code, LC trace, and diagnostics.
        """
        lc: int | None = None
        starting_address: int | None = None
        end_encountered: bool = False

        symtab: list[SymbolTableEntry] = []
        sym_map: dict[str, SymbolTableEntry] = {}

        littab: list[LiteralTableEntry] = []
        pooltab: list[PoolTableEntry] = []

        ic_records: list[IntermediateRecord] = []
        lc_trace: list[LCTraceEntry] = []
        diagnostics = DiagnosticBag()

        # Initialize Pool 0
        pooltab.append(
            PoolTableEntry(
                pool_index=0,
                pool_number=1,
                littab_start_index=0,
                literal_count=0,
                ltorg_line=None,
                trigger=None,
            )
        )

        def current_pool() -> PoolTableEntry:
            return pooltab[-1]

        # ------------------------------------------------------------------
        # Helper: Symbol Registration & References
        # ------------------------------------------------------------------
        def define_symbol(name: str, address: int, line: int) -> None:
            norm_name = name.strip().upper()
            if norm_name in sym_map:
                existing = sym_map[norm_name]
                if existing.is_defined:
                    diagnostics.add_error(
                        stage=AnalysisStage.PASS_ONE,
                        code=ErrorCode.DUPLICATE_SYMBOL,
                        message=(
                            f"Duplicate symbol definition: '{norm_name}' was already defined "
                            f"at line {existing.defined_at_line} with address {existing.value}."
                        ),
                        line=line,
                        token_value=norm_name,
                    )
                else:
                    # Resolve forward reference
                    existing.value = address
                    existing.defined_at_line = line
                    existing.is_defined = True
                    existing.status = "DEFINED"
            else:
                entry = SymbolTableEntry(
                    name=norm_name,
                    value=address,
                    defined_at_line=line,
                    is_defined=True,
                    references=[],
                    index=len(symtab) + 1,
                    forward_reference=False,
                    status="DEFINED",
                )
                sym_map[norm_name] = entry
                symtab.append(entry)

        def reference_symbol(name: str, line: int) -> int:
            norm_name = name.strip().upper()
            if norm_name in sym_map:
                entry = sym_map[norm_name]
                if line not in entry.references:
                    entry.references.append(line)
                return entry.index or 1
            else:
                entry = SymbolTableEntry(
                    name=norm_name,
                    value=0,
                    defined_at_line=None,
                    is_defined=False,
                    references=[line],
                    index=len(symtab) + 1,
                    forward_reference=True,
                    status="UNRESOLVED",
                )
                sym_map[norm_name] = entry
                symtab.append(entry)
                return entry.index or 1

        # ------------------------------------------------------------------
        # Helper: Literal Registration & Pool Allocation
        # ------------------------------------------------------------------
        def register_literal(raw_val: str, line: int) -> int:
            cleaned = raw_val.strip()
            # Normalize to ='val'
            if cleaned.startswith("="):
                inner = cleaned[1:].strip("'\"")
                norm_val = f"='{inner}'"
                try:
                    num_val: int | None = int(inner)
                except ValueError:
                    num_val = None
            else:
                norm_val = cleaned
                try:
                    num_val = int(cleaned)
                except ValueError:
                    num_val = None

            # Deduplication within the active pool context
            active_pool = current_pool()
            for idx in range(active_pool.littab_start_index, len(littab)):
                entry = littab[idx]
                if entry.value == norm_val:
                    if line not in entry.references:
                        entry.references.append(line)
                    return entry.index or (idx + 1)

            # Not found in current pool: add new entry
            entry = LiteralTableEntry(
                value=norm_val,
                numeric_value=num_val,
                pool_index=active_pool.pool_index,
                address=None,
                width=1,
                first_seen_line=line,
                index=len(littab) + 1,
                references=[line],
            )
            littab.append(entry)
            active_pool.literal_count += 1
            return entry.index or len(littab)

        def flush_pool(trigger: str, trigger_line: int) -> None:
            nonlocal lc
            active_pool = current_pool()
            start_idx = active_pool.littab_start_index
            unallocated = [entry for entry in littab[start_idx:] if entry.address is None]

            if lc is None:
                lc = 0

            for entry in unallocated:
                lit_lc_before = lc
                entry.address = lc

                # Emit intermediate code record for literal definition (DL, 01, (C, val))
                ic_val = str(entry.numeric_value if entry.numeric_value is not None else entry.value)
                ic_records.append(
                    IntermediateRecord(
                        source_line=trigger_line,
                        location_counter=lc,
                        statement_class=IntermediateClass.DL,
                        opcode_value=DECLARATIVE_OPCODE_TABLE[DeclarativeMnemonic.DC],
                        mnemonic="DC",
                        operands=[OperandField(type=OperandType.CONSTANT, value=ic_val)],
                        label=None,
                    )
                )

                lc_trace.append(
                    LCTraceEntry(
                        source_line=trigger_line,
                        statement=f"Literal {entry.value}",
                        lc_before=lit_lc_before,
                        action=f"Allocate literal {entry.value} at address {lc}",
                        lc_after=lc + 1,
                        explanation=f"Literal {entry.value} allocated at address {lc} by {trigger}.",
                    )
                )
                lc += 1

            active_pool.literal_count = len(littab) - start_idx
            active_pool.ending_literal_index = len(littab) - 1 if active_pool.literal_count > 0 else start_idx
            active_pool.ltorg_line = trigger_line
            active_pool.trigger = trigger

        # ------------------------------------------------------------------
        # Helper: Expression Evaluation (for EQU / ORIGIN)
        # ------------------------------------------------------------------
        def eval_expression(expr: str | None, line: int) -> int | None:
            if not expr or not expr.strip():
                return None
            clean = expr.strip()
            # Direct integer
            if clean.isdigit() or (clean.startswith("-") and clean[1:].isdigit()):
                return int(clean)

            # Check for binary + or -
            if "+" in clean:
                parts = clean.split("+", 1)
                left = eval_expression(parts[0], line)
                right = eval_expression(parts[1], line)
                if left is not None and right is not None:
                    return left + right
                return None

            if "-" in clean and not clean.startswith("-"):
                parts = clean.split("-", 1)
                left = eval_expression(parts[0], line)
                right = eval_expression(parts[1], line)
                if left is not None and right is not None:
                    return left - right
                return None

            # Symbol lookup
            sym_name = clean.upper()
            if sym_name in sym_map:
                sym_entry = sym_map[sym_name]
                if line not in sym_entry.references:
                    sym_entry.references.append(line)
                if sym_entry.is_defined:
                    return sym_entry.value
            return None

        # ------------------------------------------------------------------
        # Process Statements Sequentially
        # ------------------------------------------------------------------
        for stmt in syntax_result.statements:
            if end_encountered:
                # Extra statements after END
                diagnostics.add_warning(
                    stage=AnalysisStage.PASS_ONE,
                    code="UNREACHABLE_CODE",
                    message=f"Statement at line {stmt.line_number} appears after END directive.",
                    line=stmt.line_number,
                )

            # Handle START directive first (even if operand syntax was invalid, to capture INVALID_START)
            if stmt.directive == Directive.START:
                val: int | None = None
                if stmt.is_valid and stmt.operand is not None:
                    try:
                        parsed_val = int(stmt.operand.strip())
                        if parsed_val >= 0:
                            val = parsed_val
                    except ValueError:
                        val = None

                if val is None:
                    diagnostics.add_error(
                        stage=AnalysisStage.PASS_ONE,
                        code=ErrorCode.INVALID_START,
                        message=(
                            f"START directive requires a non-negative integer address, "
                            f"got '{stmt.operand}'."
                        ),
                        line=stmt.line_number,
                        token_value=str(stmt.operand) if stmt.operand is not None else None,
                    )
                    val = 0

                lc = val
                starting_address = val

                if stmt.label:
                    define_symbol(stmt.label, lc, stmt.line_number)

                ic_records.append(
                    IntermediateRecord(
                        source_line=stmt.line_number,
                        location_counter=lc,
                        statement_class=IntermediateClass.AD,
                        opcode_value=DIRECTIVE_OPCODE_TABLE[Directive.START],
                        mnemonic="START",
                        operands=[OperandField(type=OperandType.CONSTANT, value=str(lc))],
                        label=stmt.label,
                    )
                )

                lc_trace.append(
                    LCTraceEntry(
                        source_line=stmt.line_number,
                        statement=f"START {lc}",
                        lc_before=None,
                        action=f"Set Location Counter to {lc}",
                        lc_after=lc,
                        explanation=f"START directive sets initial Location Counter to {lc}.",
                    )
                )
                continue

            # Skip syntactically invalid statements while preserving error trace
            if not stmt.is_valid:
                lc_trace.append(
                    LCTraceEntry(
                        source_line=stmt.line_number,
                        statement="<SYNTAX ERROR>",
                        lc_before=lc,
                        action="Skipped due to syntax error",
                        lc_after=lc,
                        explanation=f"Line {stmt.line_number} contains syntax errors and was bypassed.",
                    )
                )
                continue

            # --------------------------------------------------------------
            # 1. DIRECTIVES
            # --------------------------------------------------------------
            if stmt.directive is not None:
                # Default LC to 0 if not yet set before other statements
                if lc is None:
                    diagnostics.add_warning(
                        stage=AnalysisStage.PASS_ONE,
                        code="MISSING_START",
                        message="Program does not begin with START; defaulting Location Counter to 0.",
                        line=stmt.line_number,
                    )
                    lc = 0
                    starting_address = 0

                # ORIGIN
                if stmt.directive == Directive.ORIGIN:
                    target_lc = eval_expression(stmt.operand, stmt.line_number)
                    lc_before = lc
                    if target_lc is None:
                        diagnostics.add_error(
                            stage=AnalysisStage.PASS_ONE,
                            code=ErrorCode.INVALID_OPERAND,
                            message=(
                                f"ORIGIN operand '{stmt.operand}' could not be resolved to a known address."
                            ),
                            line=stmt.line_number,
                            token_value=stmt.operand,
                        )
                    else:
                        lc = target_lc

                    ic_records.append(
                        IntermediateRecord(
                            source_line=stmt.line_number,
                            location_counter=lc,
                            statement_class=IntermediateClass.AD,
                            opcode_value=DIRECTIVE_OPCODE_TABLE[Directive.ORIGIN],
                            mnemonic="ORIGIN",
                            operands=[
                                OperandField(
                                    type=OperandType.CONSTANT,
                                    value=str(lc),
                                )
                            ],
                            label=stmt.label,
                        )
                    )

                    lc_trace.append(
                        LCTraceEntry(
                            source_line=stmt.line_number,
                            statement=f"ORIGIN {stmt.operand or ''}".strip(),
                            lc_before=lc_before,
                            action=f"Change Location Counter to {lc}",
                            lc_after=lc,
                            explanation=f"ORIGIN relocated the Location Counter from {lc_before} to {lc}.",
                        )
                    )
                    continue

                # EQU
                if stmt.directive == Directive.EQU:
                    if not stmt.label:
                        diagnostics.add_error(
                            stage=AnalysisStage.PASS_ONE,
                            code=ErrorCode.INVALID_OPERAND,
                            message="EQU directive requires a label to define.",
                            line=stmt.line_number,
                        )
                    else:
                        assigned_val = eval_expression(stmt.operand, stmt.line_number)
                        if assigned_val is None:
                            diagnostics.add_error(
                                stage=AnalysisStage.PASS_ONE,
                                code=ErrorCode.UNDEFINED_SYMBOL,
                                message=(
                                    f"EQU operand '{stmt.operand}' contains undefined symbol or invalid value."
                                ),
                                line=stmt.line_number,
                                token_value=stmt.operand,
                            )
                        else:
                            norm_label = stmt.label.strip().upper()
                            if norm_label in sym_map:
                                existing = sym_map[norm_label]
                                if existing.is_defined and existing.value != assigned_val:
                                    diagnostics.add_error(
                                        stage=AnalysisStage.PASS_ONE,
                                        code=ErrorCode.DUPLICATE_SYMBOL,
                                        message=f"Redefinition of symbol '{norm_label}' with conflicting value.",
                                        line=stmt.line_number,
                                        token_value=norm_label,
                                    )
                                else:
                                    existing.value = assigned_val
                                    existing.defined_at_line = stmt.line_number
                                    existing.is_defined = True
                                    existing.status = "DEFINED"
                            else:
                                entry = SymbolTableEntry(
                                    name=norm_label,
                                    value=assigned_val,
                                    defined_at_line=stmt.line_number,
                                    is_defined=True,
                                    references=[],
                                    index=len(symtab) + 1,
                                    forward_reference=False,
                                    status="DEFINED",
                                )
                                sym_map[norm_label] = entry
                                symtab.append(entry)

                    ic_records.append(
                        IntermediateRecord(
                            source_line=stmt.line_number,
                            location_counter=lc,
                            statement_class=IntermediateClass.AD,
                            opcode_value=DIRECTIVE_OPCODE_TABLE[Directive.EQU],
                            mnemonic="EQU",
                            operands=[
                                OperandField(
                                    type=OperandType.CONSTANT,
                                    value=str(assigned_val if 'assigned_val' in locals() and assigned_val is not None else (stmt.operand or '0')),
                                )
                            ],
                            label=stmt.label,
                        )
                    )

                    lc_trace.append(
                        LCTraceEntry(
                            source_line=stmt.line_number,
                            statement=f"{stmt.label or ''} EQU {stmt.operand or ''}".strip(),
                            lc_before=lc,
                            action=f"Define {stmt.label} = {stmt.operand} (LC unchanged)",
                            lc_after=lc,
                            explanation=f"EQU assigns value to '{stmt.label}' without consuming memory. LC remains {lc}.",
                        )
                    )
                    continue

                # LTORG
                if stmt.directive == Directive.LTORG:
                    lc_before = lc
                    flush_pool(trigger="LTORG", trigger_line=stmt.line_number)

                    # Start next pool
                    new_idx = len(pooltab)
                    pooltab.append(
                        PoolTableEntry(
                            pool_index=new_idx,
                            pool_number=new_idx + 1,
                            littab_start_index=len(littab),
                            literal_count=0,
                            ltorg_line=None,
                            trigger=None,
                        )
                    )

                    ic_records.append(
                        IntermediateRecord(
                            source_line=stmt.line_number,
                            location_counter=lc_before,
                            statement_class=IntermediateClass.AD,
                            opcode_value=DIRECTIVE_OPCODE_TABLE[Directive.LTORG],
                            mnemonic="LTORG",
                            operands=[],
                            label=stmt.label,
                        )
                    )
                    continue

                # END
                if stmt.directive == Directive.END:
                    end_encountered = True
                    flush_pool(trigger="END", trigger_line=stmt.line_number)

                    ic_records.append(
                        IntermediateRecord(
                            source_line=stmt.line_number,
                            location_counter=lc,
                            statement_class=IntermediateClass.AD,
                            opcode_value=DIRECTIVE_OPCODE_TABLE[Directive.END],
                            mnemonic="END",
                            operands=[],
                            label=stmt.label,
                        )
                    )

                    lc_trace.append(
                        LCTraceEntry(
                            source_line=stmt.line_number,
                            statement="END",
                            lc_before=lc,
                            action="Terminate assembly pass",
                            lc_after=lc,
                            explanation="END marks program termination. All literal pools resolved.",
                        )
                    )
                    continue

            # Default LC if statements appear before START
            if lc is None:
                diagnostics.add_warning(
                    stage=AnalysisStage.PASS_ONE,
                    code="MISSING_START",
                    message="Program does not begin with START; defaulting Location Counter to 0.",
                    line=stmt.line_number,
                )
                lc = 0
                starting_address = 0

            # --------------------------------------------------------------
            # 2. DECLARATIVES (DC, DS)
            # --------------------------------------------------------------
            if stmt.declarative is not None:
                if stmt.label:
                    define_symbol(stmt.label, lc, stmt.line_number)

                lc_before = lc

                if stmt.declarative == DeclarativeMnemonic.DC:
                    # Allocate 1 constant word
                    constant_val = 0
                    if stmt.operand:
                        try:
                            constant_val = int(stmt.operand.strip().strip("'\""))
                        except ValueError:
                            diagnostics.add_error(
                                stage=AnalysisStage.PASS_ONE,
                                code=ErrorCode.INVALID_OPERAND,
                                message=f"DC operand must be integer constant, got '{stmt.operand}'.",
                                line=stmt.line_number,
                                token_value=stmt.operand,
                            )

                    ic_records.append(
                        IntermediateRecord(
                            source_line=stmt.line_number,
                            location_counter=lc,
                            statement_class=IntermediateClass.DL,
                            opcode_value=DECLARATIVE_OPCODE_TABLE[DeclarativeMnemonic.DC],
                            mnemonic="DC",
                            operands=[OperandField(type=OperandType.CONSTANT, value=str(constant_val))],
                            label=stmt.label,
                        )
                    )

                    lc += 1
                    lc_trace.append(
                        LCTraceEntry(
                            source_line=stmt.line_number,
                            statement=f"{stmt.label or ''} DC {stmt.operand or ''}".strip(),
                            lc_before=lc_before,
                            action="Allocate 1 constant word (LC + 1)",
                            lc_after=lc,
                            explanation=f"DC allocates 1 memory word at {lc_before} with value {constant_val}. LC advances to {lc}.",
                        )
                    )
                    continue

                if stmt.declarative == DeclarativeMnemonic.DS:
                    # Reserve N words
                    size = 1
                    if stmt.operand:
                        try:
                            parsed_size = int(stmt.operand.strip())
                            if parsed_size > 0:
                                size = parsed_size
                            else:
                                diagnostics.add_error(
                                    stage=AnalysisStage.PASS_ONE,
                                    code=ErrorCode.INVALID_OPERAND,
                                    message=f"DS size must be positive, got {parsed_size}.",
                                    line=stmt.line_number,
                                    token_value=stmt.operand,
                                )
                        except ValueError:
                            diagnostics.add_error(
                                stage=AnalysisStage.PASS_ONE,
                                code=ErrorCode.INVALID_OPERAND,
                                message=f"DS size must be an integer, got '{stmt.operand}'.",
                                line=stmt.line_number,
                                token_value=stmt.operand,
                            )

                    ic_records.append(
                        IntermediateRecord(
                            source_line=stmt.line_number,
                            location_counter=lc,
                            statement_class=IntermediateClass.DL,
                            opcode_value=DECLARATIVE_OPCODE_TABLE[DeclarativeMnemonic.DS],
                            mnemonic="DS",
                            operands=[OperandField(type=OperandType.CONSTANT, value=str(size))],
                            label=stmt.label,
                        )
                    )

                    lc += size
                    lc_trace.append(
                        LCTraceEntry(
                            source_line=stmt.line_number,
                            statement=f"{stmt.label or ''} DS {stmt.operand or ''}".strip(),
                            lc_before=lc_before,
                            action=f"Reserve {size} memory words (LC + {size})",
                            lc_after=lc,
                            explanation=f"DS reserves {size} words starting at {lc_before}. LC advances to {lc}.",
                        )
                    )
                    continue

            # --------------------------------------------------------------
            # 3. IMPERATIVES (ADD, MOVER, BC, etc.)
            # --------------------------------------------------------------
            if stmt.imperative is not None:
                if stmt.label:
                    define_symbol(stmt.label, lc, stmt.line_number)

                lc_before = lc
                opcode = OPCODE_TABLE[stmt.imperative]
                operands: list[OperandField] = []

                # Register operand (e.g. AREG)
                if stmt.register is not None:
                    operands.append(
                        OperandField(
                            type=OperandType.REGISTER,
                            value=str(REGISTER_NUMBER[stmt.register]),
                        )
                    )

                # Condition code operand (for BC)
                if stmt.condition_code is not None:
                    operands.append(
                        OperandField(
                            type=OperandType.CONDITION,
                            value=str(CONDITION_CODE_NUMBER[stmt.condition_code]),
                        )
                    )

                # Second operand: Literal, Symbol, or Constant
                if stmt.operand is not None:
                    raw_op = stmt.operand.strip()
                    if raw_op.startswith("="):
                        lit_idx = register_literal(raw_op, stmt.line_number)
                        operands.append(
                            OperandField(
                                type=OperandType.LITERAL,
                                value=str(lit_idx),
                            )
                        )
                    elif raw_op.isdigit() or (raw_op.startswith("-") and raw_op[1:].isdigit()):
                        operands.append(
                            OperandField(
                                type=OperandType.CONSTANT,
                                value=raw_op,
                            )
                        )
                    else:
                        sym_idx = reference_symbol(raw_op, stmt.line_number)
                        operands.append(
                            OperandField(
                                type=OperandType.SYMBOL,
                                value=str(sym_idx),
                            )
                        )

                # STOP has no operands
                if not operands:
                    operands.append(
                        OperandField(type=OperandType.NONE, value="-")
                    )

                ic_records.append(
                    IntermediateRecord(
                        source_line=stmt.line_number,
                        location_counter=lc,
                        statement_class=IntermediateClass.IS,
                        opcode_value=opcode,
                        mnemonic=stmt.imperative.value,
                        operands=operands,
                        label=stmt.label,
                    )
                )

                lc += 1
                stmt_str = f"{stmt.label + ' ' if stmt.label else ''}{stmt.imperative.value} "
                if stmt.register:
                    stmt_str += f"{stmt.register.value}, "
                if stmt.condition_code:
                    stmt_str += f"{stmt.condition_code.value}, "
                if stmt.operand:
                    stmt_str += f"{stmt.operand}"
                stmt_str = stmt_str.strip().rstrip(",")

                lc_trace.append(
                    LCTraceEntry(
                        source_line=stmt.line_number,
                        statement=stmt_str,
                        lc_before=lc_before,
                        action="Advance Location Counter by 1",
                        lc_after=lc,
                        explanation=f"{stmt.imperative.value} is an executable instruction of width 1 word at address {lc_before}.",
                    )
                )
                continue

        # ------------------------------------------------------------------
        # Post-Processing: Flush Remaining Literals if END was omitted
        # ------------------------------------------------------------------
        if not end_encountered:
            diagnostics.add_warning(
                stage=AnalysisStage.PASS_ONE,
                code=ErrorCode.MISSING_END,
                message="Source does not end with END directive; remaining literal pool flushed.",
                line=syntax_result.statements[-1].line_number if syntax_result.statements else 1,
            )
            flush_pool(trigger="END", trigger_line=syntax_result.statements[-1].line_number if syntax_result.statements else 1)

        # ------------------------------------------------------------------
        # Post-Processing: Check for Undefined Symbols
        # ------------------------------------------------------------------
        unresolved_count = 0
        for sym in symtab:
            if not sym.is_defined:
                unresolved_count += 1
                diagnostics.add_error(
                    stage=AnalysisStage.PASS_ONE,
                    code=ErrorCode.UNDEFINED_SYMBOL,
                    message=(
                        f"Undefined symbol: '{sym.name}' was referenced at line(s) "
                        f"{sym.references} but never defined."
                    ),
                    line=sym.references[0] if sym.references else None,
                    token_value=sym.name,
                )

        # Clean up empty literal pools (do not emit pools with zero literals)
        filtered_pools = [p for p in pooltab if p.literal_count > 0]
        for idx, p in enumerate(filtered_pools):
            p.pool_index = idx
            p.pool_number = idx + 1
        pooltab = filtered_pools

        # Format diagnostics for Pass1Result
        diag_list = [
            {
                "stage": d.stage.value if hasattr(d.stage, "value") else str(d.stage),
                "severity": d.severity,
                "code": d.code,
                "message": d.message,
                "line": d.line,
                "column": d.column,
                "token_value": d.token_value,
            }
            for d in diagnostics.items
        ]

        has_fatal_errors = any(d["severity"] == "ERROR" for d in diag_list)

        return Pass1Result(
            symbol_table=symtab,
            literal_table=littab,
            pool_table=pooltab,
            intermediate_code=ic_records,
            starting_address=starting_address,
            final_location_counter=lc,
            lc_trace=lc_trace,
            processed_statement_count=len(syntax_result.statements),
            unresolved_symbol_count=unresolved_count,
            literal_count=len(littab),
            pool_count=len(pooltab),
            diagnostics=diag_list,
            success=not has_fatal_errors,
        )
