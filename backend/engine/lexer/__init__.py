"""
SysForge engine — Lexer package.

Public interface::

    from engine.lexer import Lexer

    lexer = Lexer()
    result = lexer.analyze(source_code)

The ``Lexer`` class satisfies the ``LexerProtocol`` defined in
``engine.interfaces`` — no explicit inheritance needed (structural typing).
"""

from engine.lexer.lexer import Lexer

__all__ = ["Lexer"]
