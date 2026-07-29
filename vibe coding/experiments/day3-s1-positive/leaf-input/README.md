# Day 3 S1 Leaf-Gate input adapter

This directory is a derived, formal Leaf-Gate package. It does not replace the
raw S1 Architecture, testcase, or Mocktest artifacts.

The strict S1 package uses `REQ-S1-NOTE-CREATE` in generated envelopes while
the checked Feature and Mocktest formal evidence use `REQ-S1`. The Leaf Gate
requires exact identity and requirement-id equality across all four inputs, so
this adapter records the one-to-one `REQ-S1` calibration identity and the
source artifact references. The adapter uses Leaf Gate's required structured
input version `1.0`; it does not alter the shared v0.2 Contract. Its `mocktest_report.json` is a lossless summary of
the PASS/zero-defect fields in `strict-run-20260729-j/formal/mocktest_report.json`.

Do not use this derived package as C0-C5 data or as a replacement for the
shared Artifact Contract.
