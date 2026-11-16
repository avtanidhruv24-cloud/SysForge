"""
SysForge — Linker and Loader domain models.

These are the contracts for the ``/linker``, ``/loader``, and ``/memory``
frontend views.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Linker models
# ---------------------------------------------------------------------------


class LinkerSection(BaseModel):
    """
    One section (code or data segment) within a relocatable module.

    Frontend column mapping:
        Module  → module_name
        Section → name
        Offset  → base_offset
        External refs → external_references
    """

    name: str = Field(description="Section name (e.g. 'text', 'data', 'bss').")
    base_offset: int = Field(
        ge=0, description="Byte/word offset of this section within its module."
    )
    length: int = Field(
        ge=0, description="Length of this section in words."
    )
    is_relocatable: bool = Field(
        default=True,
        description="``True`` if addresses within this section need relocation.",
    )


class ExternalReference(BaseModel):
    """An unresolved external symbol reference carried in a module."""

    name: str = Field(description="Name of the external symbol.")
    address: int = Field(
        ge=0,
        description="Address within the module that holds this reference.",
    )


class LinkerModule(BaseModel):
    """
    A single relocatable object module input to the linker.

    In the educational SysForge context there is typically only one module
    (single-file assembly), but the model supports multi-module linking for
    completeness.
    """

    name: str = Field(default="main", description="Module name.")
    sections: list[LinkerSection] = Field(default_factory=list)
    global_symbols: dict[str, int] = Field(
        default_factory=dict,
        description="Symbols exported by this module: name → address.",
    )
    external_references: list[ExternalReference] = Field(
        default_factory=list,
        description="Unresolved external symbols this module requires.",
    )


class LinkerResult(BaseModel):
    """
    Complete output of the Linker stage.

    Frontend column mapping (``/linker`` view):
        Module       → module_name
        Section      → section_name
        Offset       → resolved_offset
        External refs → resolved_externals
    """

    modules: list[LinkerModule] = Field(
        default_factory=list,
        description="Input modules that were linked.",
    )

    resolved_symbols: dict[str, int] = Field(
        default_factory=dict,
        description="All symbols resolved to final addresses after linking.",
    )

    unresolved_symbols: list[str] = Field(
        default_factory=list,
        description="Symbol names that could not be resolved (linker errors).",
    )

    linked_code: list[dict] = Field(
        default_factory=list,
        description=(
            "Merged object words after relocation, ready for the loader.  "
            "Each dict mirrors the ``ObjectWord`` schema."
        ),
    )

    diagnostics: list[dict] = Field(default_factory=list)
    success: bool = Field(default=True)


# ---------------------------------------------------------------------------
# Loader models
# ---------------------------------------------------------------------------


class LoaderSegment(BaseModel):
    """
    A contiguous segment placed into memory by the Loader.

    Frontend column mapping (``/loader`` view):
        Segment      → name
        Virtual base → load_address
        Length       → length
        Protection   → protection
    """

    name: str = Field(description="Segment name (e.g. 'text', 'data').")
    load_address: int = Field(
        ge=0,
        description="Absolute memory address where this segment is placed.",
    )
    length: int = Field(ge=0, description="Length of this segment in words.")
    protection: str = Field(
        default="RX",
        description="Access protection: 'RX' (read-execute), 'RW' (read-write), 'R' (read-only).",
    )


class MemoryCell(BaseModel):
    """
    A single word in the loaded memory map.

    Frontend column mapping (``/memory`` view):
        Address  → address
        Region   → region
        Contents → value
        Access   → protection
    """

    address: int = Field(ge=0, description="Absolute memory address.")
    value: int | None = Field(
        default=None,
        description="Contents of this memory word.  ``None`` for uninitialized cells.",
    )
    region: str = Field(
        default="code",
        description="Logical region: 'code', 'data', 'literal', 'stack', 'free'.",
    )
    source_line: int | None = Field(
        default=None,
        ge=1,
        description="Source line that placed this value here, if known.",
    )
    protection: str = Field(
        default="RX",
        description="Access protection for this cell's region.",
    )
    label: str | None = Field(
        default=None,
        description="Symbol label pointing at this address, if any.",
    )


class LoaderResult(BaseModel):
    """
    Complete output of the Loader stage.

    Contains the full memory map after the program has been placed at its
    load address.  The VM reads from this memory map to execute the program.
    """

    segments: list[LoaderSegment] = Field(
        default_factory=list,
        description="Memory segments placed by the loader.",
    )

    memory_map: list[MemoryCell] = Field(
        default_factory=list,
        description="Complete flat memory map: one ``MemoryCell`` per word.",
    )

    entry_point: int | None = Field(
        default=None,
        description="Absolute address of the program's first instruction (PC start value).",
    )

    load_address: int = Field(
        default=0,
        ge=0,
        description="Base address at which the program was loaded.",
    )

    diagnostics: list[dict] = Field(default_factory=list)
    success: bool = Field(default=True)
