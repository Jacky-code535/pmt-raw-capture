import base64
import contextlib
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import pmt_analysis as analysis
import pmt_bulk_capture as capture



def writer(stack, path, fields):
    stream = stack.enter_context(path.open("w", newline="", encoding="utf-8"))
    result = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
    result.writeheader()
    return result
