#!/usr/bin/env python3
"""
signalbox - Script execution control and monitoring
https://github.com/pdbeard/signalbox/

Entry point for the signalbox CLI. All logic is now modularized in core/.
"""

from core.cli_commands import cli

if __name__ == '__main__':
    cli()
