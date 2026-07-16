# Grade Rules Schema (GRS)

**Grade Rules Schema (GRS)** is an open JSON specification designed to describe university GPA calculation rules in a consistent, portable, and human-readable format.

GRS was originally developed as part of the **GPA Manager** project to support different grading systems used by universities around the world.

Rather than hard-coding GPA calculation logic into software, GRS allows each institution to describe its grading policy using a single JSON document.

## Design Principles

GRS is designed around the following principles:

* **One file = One institution**
* **Human-readable JSON**
* **Easy to edit**
* **Versioned specification**
* **Backward-compatible whenever possible**
* **No scripting or executable code**
* **No user-defined formulas**

## Features

GRS currently supports:

* Numeric score systems
* Text-based grade systems
* Letter grade systems
* Special grade handling (e.g. Pass, Withdraw)

Numeric grading supports multiple calculation models, including:

* Range
* Linear
* Lookup

## Versioning

GRS evolves through versioned specifications.

Current version:

* **GRS v1**

Future revisions may introduce new features while maintaining compatibility whenever practical.

## Documentation

* **GRS v1 Specification**
* Future versions (GRS v2, GRS v3, …) will be published as separate specification documents.

## Reference Implementation

The reference implementation of GRS is included in the **GPA Manager** project.

Repository:

https://github.com/tdowningsun/GPAManager

## License

GRS is part of the GPA Manager project and is distributed under the same license as GPA Manager.
