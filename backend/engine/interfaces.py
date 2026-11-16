"""
SysForge — Engine component interfaces.

Every engine stage is represented by a ``Protocol`` (structural subtyping).
Concrete implementations written in Phase 3+ must satisfy these interfaces.
The ``AnalysisService`` depends only on these protocols, never on concrete
classes, so each stage can be developed, tested, and swapped independently.

Why Protocol instead of ABC?
-----------------------------
``typing.Protocol`` enables *structural* subtyping: a class satisfies an
interface if it has the right methods, without inheriting from the base class.
This keeps engine modules free of cross-dependencies and makes mock
implementations for tests trivially simple.

Naming conventions
------------------
- Input type  : the concrete data the stage consumes
- Output type : the domain model the stage produces (from ``app.models.*``)
- ``diagnostics`` are always returned inside the result object — stages
  never raise on recoverable errors.  They raise ``SysForgeError`` only
  for unrecoverable conditions (e.g. a completely malformed input that
  prevents producing any output at all).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.models.assembler import MacroResult, Pass1Result, Pass2Result
from app.models.execution import ExecutionResult
from app.models.linking import LinkerResult, LoaderResult
from app.models.syntax import SyntaxResult
from app.models.tokens import LexerResult


# ---------------------------------------------------------------------------
# Lexer interface
# ---------------------------------------------------------------------------


@runtime_checkable
class LexerProtocol(Protocol):
    """
    Contract for the SysForge Lexer (Phase 3).

    Accepts raw assembly source text and produces a stream of typed tokens.

    Implementation notes (for Phase 3)
    ------------------------------------
    - Must tokenise all SysForge keywords defined in ``engine.common.enums``.
    - Must never raise on unrecognised input; instead record an
      ``EngineDiagnostic`` with ``TokenType.UNKNOWN`` and continue.
    - Must preserve source positions (line, column) on every token.
    - Whitespace and blank lines are skipped but not included in output.
    - Comments (``; ...``) are tokenised with ``TokenType.COMMENT`` but
      not forwarded to the parser.
    """

    def analyze(self, source: str) -> LexerResult:
        """
        Tokenise *source* and return a ``LexerResult``.

        Args:
            source: Raw assembly source text (may be multi-line).

        Returns:
            ``LexerResult`` with ``tokens``, ``diagnostics``, and
            ``success`` fields populated.  Never returns ``None``.
        """
        ...


# ---------------------------------------------------------------------------
# Parser interface
# ---------------------------------------------------------------------------


@runtime_checkable
class ParserProtocol(Protocol):
    """
    Contract for the SysForge Parser (Phase 3).

    Consumes the token stream from the Lexer and produces one
    ``ParsedStatement`` per non-empty source line.

    Implementation notes (for Phase 3)
    ------------------------------------
    - Must validate statement structure against SysForge grammar:
        ``[LABEL]  MNEMONIC  [OPERAND1 [, OPERAND2]]``
    - Must classify each statement as IS / DL / AD (``IntermediateClass``).
    - Must record syntax errors without aborting — continue to the next
      statement after an error (error-recovery parsing).
    - Must forward label tokens to SYMTAB pre-population in Pass-I.
    """

    def parse(self, lexer_result: LexerResult) -> SyntaxResult:
        """
        Parse the token stream in *lexer_result*.

        Args:
            lexer_result: Output of the Lexer stage.

        Returns:
            ``SyntaxResult`` with ``statements``, ``diagnostics``, and
            ``success`` fields populated.
        """
        ...


# ---------------------------------------------------------------------------
# Macro Processor interface
# ---------------------------------------------------------------------------


@runtime_checkable
class MacroProcessorProtocol(Protocol):
    """
    Contract for the SysForge Macro Processor (future phase).

    Processes MACRO / MEND directives and expands macro calls in the
    source before it reaches the assembler.

    Implementation notes
    ---------------------
    - Must extract macro definitions from the source and remove them.
    - Must expand every macro call by substituting actual arguments for
      formal parameters.
    - Must detect duplicate macro definitions.
    - Must detect calls to undefined macros.
    - The educational SysForge language supports positional parameters only.
    - Returns the *expanded* source as a plain string, plus structured
      records of every definition and call for the ``/macro`` view.
    """

    def process(self, source: str) -> MacroResult:
        """
        Expand macros in *source* and return a ``MacroResult``.

        Args:
            source: Raw (or partially processed) assembly source text.

        Returns:
            ``MacroResult`` with ``expanded_source``, ``definitions``,
            ``calls``, ``diagnostics``, and ``success`` fields.
        """
        ...


# ---------------------------------------------------------------------------
# Assembler Pass-I interface
# ---------------------------------------------------------------------------


@runtime_checkable
class AssemblerPass1Protocol(Protocol):
    """
    Contract for Assembler Pass-I (Phase 4).

    Performs a single forward pass over the parsed statements to:
      1. Maintain the Location Counter (LC).
      2. Build the Symbol Table (SYMTAB).
      3. Collect literals into the Literal Table (LITTAB).
      4. Build the Pool Table (POOLTAB) at each LTORG / END.
      5. Produce the Intermediate Code representation.

    Implementation notes (for Phase 4)
    ------------------------------------
    - LC starts at the address given by the START directive.
    - Each IS/DL statement increments the LC by 1 (one word per instruction
      or DC; DS increments by the operand count).
    - Directives ORIGIN and EQU do not increment the LC in the normal way.
    - Forward references in SYMTAB are allowed; Pass-II resolves them.
    - Every LTORG (and the final END) flushes the current literal pool:
      assigns addresses to all literals since the last LTORG.
    """

    def assemble(self, syntax_result: SyntaxResult) -> Pass1Result:
        """
        Perform Pass-I on the parsed statement list.

        Args:
            syntax_result: Output of the Parser stage.

        Returns:
            ``Pass1Result`` containing SYMTAB, LITTAB, POOLTAB,
            Intermediate Code, ``diagnostics``, and ``success``.
        """
        ...


# ---------------------------------------------------------------------------
# Assembler Pass-II interface
# ---------------------------------------------------------------------------


@runtime_checkable
class AssemblerPass2Protocol(Protocol):
    """
    Contract for Assembler Pass-II (Phase 4).

    Performs a second pass over the Intermediate Code to:
      1. Resolve all symbol references using the completed SYMTAB.
      2. Resolve all literal references using the completed LITTAB.
      3. Encode each instruction into its machine word.
      4. Produce the final object code.

    Encoding for imperative instructions::

        machine_word = opcode * 1000 + register_number * 100 + operand_address

    Implementation notes (for Phase 4)
    ------------------------------------
    - SYMTAB and LITTAB must be fully populated (Pass-I completed) before
      this stage runs.
    - Undefined symbols produce UNDEFINED_SYMBOL errors; the corresponding
      object word is set to 0 with a diagnostic.
    - DC/DS words carry their literal values (DC) or zeros (DS).
    """

    def assemble(self, pass1_result: Pass1Result) -> Pass2Result:
        """
        Perform Pass-II on the Pass-I result.

        Args:
            pass1_result: Output of Assembler Pass-I.

        Returns:
            ``Pass2Result`` with ``object_code``, ``diagnostics``,
            and ``success``.
        """
        ...


# ---------------------------------------------------------------------------
# Linker interface
# ---------------------------------------------------------------------------


@runtime_checkable
class LinkerProtocol(Protocol):
    """
    Contract for the SysForge Linker (future phase).

    Combines one or more relocatable object modules into a single linked
    module with all cross-module references resolved.

    Implementation notes
    ---------------------
    - For single-module SysForge programs, linking is trivial (no external
      references to resolve), but the interface supports multi-module input.
    - Must apply relocation patches to address-containing words.
    - Must detect and report unresolved external symbols and duplicate
      global symbol definitions.
    """

    def link(self, pass2_result: Pass2Result) -> LinkerResult:
        """
        Link the object module(s) in *pass2_result*.

        Args:
            pass2_result: Output of Assembler Pass-II.

        Returns:
            ``LinkerResult`` with resolved symbols, linked code,
            ``diagnostics``, and ``success``.
        """
        ...


# ---------------------------------------------------------------------------
# Loader interface
# ---------------------------------------------------------------------------


@runtime_checkable
class LoaderProtocol(Protocol):
    """
    Contract for the SysForge Loader (future phase).

    Places the linked program into a flat word-addressable memory space
    starting at a caller-specified load address.

    Implementation notes
    ---------------------
    - Must apply address relocation based on the actual load address vs.
      the linker's assumed base address.
    - Must detect overlapping segments.
    - Must populate ``MemoryCell`` entries for every word in the program
      so the ``/memory`` view can render the full address space.
    - The entry point (program start address) must be set for the VM.
    """

    def load(self, linker_result: LinkerResult, load_address: int = 0) -> LoaderResult:
        """
        Load the linked program into memory starting at *load_address*.

        Args:
            linker_result: Output of the Linker stage.
            load_address:  Base address in the virtual address space.

        Returns:
            ``LoaderResult`` with ``memory_map``, ``entry_point``,
            ``segments``, ``diagnostics``, and ``success``.
        """
        ...


# ---------------------------------------------------------------------------
# Virtual Machine interface
# ---------------------------------------------------------------------------


@runtime_checkable
class VirtualMachineProtocol(Protocol):
    """
    Contract for the SysForge Educational Virtual Machine (future phase).

    Executes the program loaded into memory by the Loader.  The VM models:
      - Program Counter (PC)
      - Four general-purpose registers: AREG, BREG, CREG, DREG
      - Condition Code register: LT | LE | EQ | GT | GE | ANY
      - Flat word-addressable memory
      - Input buffer (for READ)
      - Output buffer (for PRINT)
      - Execution trace (one row per instruction)

    Safety requirements (enforced at implementation time)
    ------------------------------------------------------
    - MUST NOT execute shell commands, OS calls, or arbitrary Python.
    - MUST enforce a maximum instruction count (``settings.vm_max_instructions``).
    - MUST enforce a wall-clock execution timeout.
    - MUST enforce maximum output lines (``settings.vm_max_output_lines``).
    - MUST detect and halt on division by zero.
    - MUST detect and halt on invalid memory access.
    - MUST detect and halt on illegal opcode.
    - Infinite loops (e.g. unconditional BC to a prior label) are caught
      by the instruction count limit — not by semantic analysis.
    """

    def execute(
        self,
        loader_result: LoaderResult,
        input_data: list[str] | None = None,
    ) -> ExecutionResult:
        """
        Execute the program in *loader_result* to completion (or limit).

        Args:
            loader_result: Output of the Loader stage (memory map + entry point).
            input_data:    Optional list of string tokens for READ instructions.

        Returns:
            ``ExecutionResult`` with ``final_state``, ``trace``, ``output``,
            ``total_steps``, ``terminated_normally``, ``diagnostics``,
            and ``success``.
        """
        ...

    def step(
        self,
        loader_result: LoaderResult,
        current_state: "ExecutionResult",
        input_data: list[str] | None = None,
    ) -> ExecutionResult:
        """
        Execute exactly one instruction from the current VM state.

        Args:
            loader_result:  Memory and entry point (same as passed to
                            ``execute``).
            current_state:  The ``ExecutionResult`` from the previous step.
            input_data:     Remaining input tokens.

        Returns:
            Updated ``ExecutionResult`` with one additional trace entry.
        """
        ...
