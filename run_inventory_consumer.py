#!/usr/bin/env python3
import logging
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import DATABASE_URL

logging.basicConfig(level=logging.INFO)

if __name__ == '__main__':
    from consumers.run_consumer import main
    main()