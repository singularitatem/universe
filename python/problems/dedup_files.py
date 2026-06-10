import argparse
import os
import hashlib
from typing import Dict, List
from lib import printArray


def get_file_sha256(filepath, chunk_size=2<<15):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for block in iter(lambda: f.read(chunk_size), b""):
            sha256_hash.update(block)
    return sha256_hash.hexdigest()


def dedupe_files(dir):
    result = {}
    for root, dirs, files in os.walk(dir):
        for filename in files:
            filepath = os.path.join(root, filename)
            sha = get_file_sha256(filepath)
            if sha not in result:
                result[sha] = []
            result[sha].append(filepath)
    return [dups for dups in result.values() if len(dups) > 1]

def main():
    parser = argparse.ArgumentParser(description="Dedup files")
    parser.add_argument("--root-dir", type=str, help="Root directory and dedupe inside")
    args = parser.parse_args()
    
    printArray(dedupe_files(args.root_dir))


if __name__ == "__main__":
    main()