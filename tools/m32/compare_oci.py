#!/usr/bin/env python3
"""Compare two OCI content graphs from clean builds, not archive timestamps."""

import argparse
import hashlib
import json
import tarfile


def manifest(path):
    with tarfile.open(path) as archive:
        index = json.load(archive.extractfile("index.json"))
        descriptors = index["manifests"]
        if len(descriptors) != 1:
            raise ValueError("one native image required")
        descriptor = descriptors[0]
        algorithm, value = descriptor["digest"].split(":")
        if algorithm != "sha256":
            raise ValueError("sha256 required")
        raw = archive.extractfile("blobs/sha256/" + value).read()
        if hashlib.sha256(raw).hexdigest() != value:
            raise ValueError("manifest digest mismatch")
        return descriptor["digest"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first")
    parser.add_argument("second")
    args = parser.parse_args()
    first, second = manifest(args.first), manifest(args.second)
    if first != second:
        raise SystemExit("FAIL: clean OCI builds differ")
    print(json.dumps(dict(reproducible=True, oci_manifest_sha256=first)))


if __name__ == "__main__":
    main()
