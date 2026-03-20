# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build System

This is a polyglot monorepo using **Bazel 6.4.0** with **bzlmod** enabled. Each language lives in its own top-level directory with independent BUILD files.

### Common Commands

```bash
# Build everything
bazel build //...

# Build specific targets
bazel build //go:basic-gazelle      # Go CLI binary
bazel build //python:example        # Python binary
bazel build //rust:hello            # Rust binary

# Run targets
bazel run //go:basic-gazelle
bazel run //python:example
bazel run //rust:hello

# Regenerate Go BUILD files after changing Go deps
cd go && bazel run //:gazelle
bazel run //:gazelle-update-repos   # update deps.bzl from go.mod
```

## Architecture

- **go/** — Cobra CLI app (`github.com/singularitatem/universe/go`, Go 1.20). Entry point in `main.go` → `cmd/root.go` (Cobra root) → subcommands in `cmd/`. Reusable logic in `pkg/`.
- **python/** — Python 3.11 scripts using `py_binary` rules. Dependencies in `requirements.txt`.
- **rust/** — Rust binaries using `rules_rust`.
- **proto/** — Placeholder for protocol buffer definitions (empty).

### Bazel Module Dependencies (MODULE.bazel)

- `rules_go` v0.42.0, `gazelle` v0.34.0 — Go support with automatic BUILD generation
- `rules_python` v0.26.0 — Python support
- `rules_rust` v0.56.0 — Rust support
