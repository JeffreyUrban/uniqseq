# uniqseq

Stream-based deduplication for repeating sequences.

## Overview

`uniqseq` is a command-line tool and Python library for stream-based deduplication of repeating sequences. It identifies and removes repeated multi-record patterns from streaming data. Unlike the standard `uniq` command which only removes adjacent duplicate lines, `uniqseq` detects repeated patterns of multiple records.

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
