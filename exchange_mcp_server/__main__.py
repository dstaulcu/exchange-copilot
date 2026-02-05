"""
Exchange MCP Server - Entry Point
Run with: python -m mcp
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from exchange_mcp_server.server import main

if __name__ == "__main__":
    asyncio.run(main())
