# uniqseq

Deduplicate repeated sequences of lines in text streams and files.

## Overview

`uniqseq` is a command-line tool and Python library for detecting and removing repeated sequences of lines in text streams. Unlike the standard `uniq` command which only removes adjacent duplicate lines, `uniqseq` detects repeated patterns of multiple lines.

## Features

- **Sequence Detection**: Identifies repeated patterns of 1 or more lines
- **Streaming Processing**: Memory-efficient processing of large files
- **Pattern Filtering**: Track or bypass specific patterns with regex
- **Annotations**: Mark duplicates with customizable annotations
- **Inverse Mode**: Show only duplicates for analysis
- **Library and CLI**: Use as a command-line tool or Python library

## Getting Started

- [Installation](getting-started/installation.md) - Install uniqseq
- [Quick Start](getting-started/quick-start.md) - Get started in 5 minutes
- [Basic Concepts](getting-started/basic-concepts.md) - Understand how uniqseq works
