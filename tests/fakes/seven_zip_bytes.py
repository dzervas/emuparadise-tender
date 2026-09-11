"""Tiny 7z fixtures generated with libarchive's 7zip writer; no game data.

The regular member contains only b"legal synthetic homebrew fixture".
The other archives have a ../ path or symbolic link for extraction rejection.
"""

from base64 import b64decode

VALID = b64decode(
    "N3q8ryccAAM/9oSnKgAAAAAAAABMAAAAAAAAAFZKZ5MANhlJKXs0Uivvsf9HqLRDS3FYIlSmiQvw8Ip1iZSAXkG1O5///7TAAAABBAYAAQkqAAcLAQABIwMBAQVdAACAAAwgAAgKAbynazkAAAUBERsASABvAG0AZQBiAHIAZQB3AC4AaQBzAG8AAAAVBgEAIICkgQAA"
)

TRAVERSAL = b64decode(
    "N3q8ryccAAMebezQKgAAAAAAAABOAAAAAAAAABWz8vUANhlJKXs0Uivvsf9HqLRDS3FYIlSmiQvw8Ip1iZSAXkG1O5///7TAAAABBAYAAQkqAAcLAQABIwMBAQVdAACAAAwgAAgKAbynazkAAAUBER0ALgAuAC8AZQBzAGMAYQBwAGUALgBpAHMAbwAAABUGAQAggKSBAAA="
)

SYMLINK = b64decode(
    "N3q8ryccAAMJe61JFwAAAAAAAABEAAAAAAAAAO57q3QAF2C4ynMwlPaEXhDc4/bwnCr//lr4AAEEBgABCRcABwsBAAEjAwEBBV0AAIAADA0ACAoBvynJqwAABQEREwBsAGkAbgBrAC4AaQBzAG8AAAAVBgEAIICkoQAA"
)
