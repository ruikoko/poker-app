"""Adds backend/ to sys.path so tests can `from app.services...`."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
