#!/usr/bin/env python3
"""
Analyze Triton-Ascend kernel intermediate IR files.

Helps understand memory access patterns and potential optimization opportunities
by parsing .ttir.mlir or .ttadapter.mlir files.
"""

import argparse
import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Optional


class IRAnalyzer:
    """Analyzer for Triton MLIR intermediate representations."""

    def __init__(self, ir_content: str):
        self.ir_content = ir_content
        self.operations = []
        self.load_ops = []
        self.store_ops = []
        self.dot_ops = []
        self.reduce_ops = []
        self.memory_patterns = []

    def parse(self):
        """Parse the IR content and extract operations."""
        lines = self.ir_content.split('\n')

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Track load operations
            if 'tt.load' in stripped or 'triton::LoadOp' in stripped:
                self.load_ops.append({
                    'line': i + 1,
                    'content': stripped,
                    'has_mask': 'mask' in stripped,
                })

            # Track store operations
            elif 'tt.store' in stripped or 'triton::StoreOp' in stripped:
                self.store_ops.append({
                    'line': i + 1,
                    'content': stripped,
                    'has_mask': 'mask' in stripped,
                })

            # Track dot operations (Cube)
            elif 'tt.dot' in stripped or 'triton::DotOp' in stripped:
                self.dot_ops.append({
                    'line': i + 1,
                    'content': stripped,
                })

            # Track reduce operations
            elif 'tt.reduce' in stripped or 'triton::ReduceOp' in stripped:
                self.reduce_ops.append({
                    'line': i + 1,
                    'content': stripped,
                })

        # Analyze memory access patterns
        self._analyze_memory_patterns()

    def _analyze_memory_patterns(self):
        """Analyze memory access patterns from load/store ops."""
        patterns = []

        for op in self.load_ops + self.store_ops:
            content = op['content']

            # Check for strided access
            if 'stride' in content.lower():
                patterns.append({
                    'type': 'strided',
                    'line': op['line'],
                    'description': 'Strided memory access detected',
                })

            # Check for masked access
            if op['has_mask']:
                patterns.append({
                    'type': 'masked',
                    'line': op['line'],
                    'description': 'Masked memory access (potential tail handling)',
                })

            # Check for potential non-contiguous access
            if '//' in content or '%' in content:
                patterns.append({
                    'type': 'non_contiguous',
                    'line': op['line'],
                    'description': 'Division/modulo in address calculation (may trigger unstructured lowering)',
                })

        self.memory_patterns = patterns

    def get_kernel_type(self) -> str:
        """Determine likely kernel type based on operations."""
        has_dot = len(self.dot_ops) > 0
        has_reduce = len(self.reduce_ops) > 0
        load_count = len(self.load_ops)
        store_count = len(self.store_ops)

        if has_dot and has_reduce:
            return "CV-Mixed (MatMul + Reduction)"
        elif has_dot:
            return "Cube-Heavy (MatMul)"
        elif has_reduce:
            return "Vector (Reduction)"
        elif load_count > 0 and store_count > 0:
            return "Vector (Memory-bound)"
        else:
            return "Unknown"

    def get_optimization_hints(self) -> List[str]:
        """Generate optimization hints based on analysis."""
        hints = []

        # Check for many small loads/stores
        if len(self.load_ops) > 10:
            hints.append("Many load operations detected. Consider fusing or using larger BLOCK sizes.")

        # Check for reduce ops
        if len(self.reduce_ops) > 3:
            hints.append("Multiple reduce operations. Consider using tl.dot to batch reductions.")

        # Check for non-contiguous patterns
        non_contig = [p for p in self.memory_patterns if p['type'] == 'non_contiguous']
        if non_contig:
            hints.append(f"Non-contiguous access at lines {[p['line'] for p in non_contig]}. "
                        "This may trigger scalar loop lowering.")

        # Check for no dot ops in a kernel with many ops
        total_ops = len(self.load_ops) + len(self.store_ops) + len(self.reduce_ops)
        if total_ops > 5 and len(self.dot_ops) == 0:
            hints.append("No Cube (tl.dot) operations. If applicable, consider using tl.dot for better performance.")

        # Check for CV fusion opportunity
        if len(self.dot_ops) > 0 and len(self.reduce_ops) > 0:
            hints.append("CV fusion opportunity: MatMul + post-processing. Consider using tl.parallel with bind_sub_block.")

        return hints

    def print_report(self):
        """Print analysis report."""
        print("=" * 60)
        print("Triton IR Analysis Report")
        print("=" * 60)

        print(f"\nKernel Type: {self.get_kernel_type()}")

        print(f"\nOperation Summary:")
        print(f"  Load operations: {len(self.load_ops)}")
        print(f"  Store operations: {len(self.store_ops)}")
        print(f"  Dot operations (Cube): {len(self.dot_ops)}")
        print(f"  Reduce operations: {len(self.reduce_ops)}")

        if self.dot_ops:
            print(f"\nDot Operations (Cube):")
            for op in self.dot_ops:
                print(f"  Line {op['line']}: {op['content'][:80]}...")

        if self.memory_patterns:
            print(f"\nMemory Access Patterns:")
            for pattern in self.memory_patterns[:10]:  # Limit output
                print(f"  [{pattern['type']}] Line {pattern['line']}: {pattern['description']}")
            if len(self.memory_patterns) > 10:
                print(f"  ... and {len(self.memory_patterns) - 10} more")

        hints = self.get_optimization_hints()
        if hints:
            print(f"\nOptimization Hints:")
            for i, hint in enumerate(hints, 1):
                print(f"  {i}. {hint}")

        print("=" * 60)


def find_ir_files(cache_dir: Optional[str] = None) -> List[Path]:
    """Find IR files in Triton cache directory."""
    if cache_dir:
        base_path = Path(cache_dir)
    else:
        base_path = Path.home() / ".triton" / "cache"

    ir_files = []
    if base_path.exists():
        ir_files.extend(base_path.rglob("*.ttir.mlir"))
        ir_files.extend(base_path.rglob("*.ttadapter.mlir"))

    return ir_files


def main():
    parser = argparse.ArgumentParser(description="Analyze Triton-Ascend kernel IR files")
    parser.add_argument("ir_file", nargs="?", help="Path to IR file (.ttir.mlir or .ttadapter.mlir)")
    parser.add_argument("--cache-dir", help="Triton cache directory to search")
    parser.add_argument("--list-cache", action="store_true", help="List IR files in cache")
    args = parser.parse_args()

    if args.list_cache:
        ir_files = find_ir_files(args.cache_dir)
        if ir_files:
            print("Found IR files:")
            for f in ir_files[:20]:
                print(f"  {f}")
            if len(ir_files) > 20:
                print(f"  ... and {len(ir_files) - 20} more")
        else:
            print("No IR files found in cache")
        return

    if not args.ir_file:
        parser.print_help()
        return

    ir_path = Path(args.ir_file)
    if not ir_path.exists():
        print(f"Error: File not found: {ir_path}")
        return

    ir_content = ir_path.read_text()
    analyzer = IRAnalyzer(ir_content)
    analyzer.parse()
    analyzer.print_report()


if __name__ == "__main__":
    main()
