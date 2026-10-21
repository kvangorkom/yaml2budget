# yaml2budget

Build a self-contained HTML viewer for hierarchical performance budgets from a directory of
YAML files. Each budget is a tree of current best estimates and allocations that `yaml2budget` rolls
up (RSS, sum or product), including wavelength-dependent terms read from CSV, and renders as an
interactive table, a flowchart and a spectrum plot, with exports to YAML, Excel, PDF and PNG.

```bash
pip install yaml2budget
yaml2budget examples -o budgets.html && open budgets.html
```

[**Usage and YAML schema →**](docs/usage.md)
