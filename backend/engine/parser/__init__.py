"""
SysForge engine — Parser package.

Public interface::

    from engine.parser import Parser

    parser = Parser()
    syntax_result = parser.parse(lexer_result)

The ``Parser`` class satisfies the ``ParserProtocol`` defined in
``engine.interfaces`` — no explicit inheritance needed (structural typing).
"""

from engine.parser.parser import Parser

__all__ = ["Parser"]
