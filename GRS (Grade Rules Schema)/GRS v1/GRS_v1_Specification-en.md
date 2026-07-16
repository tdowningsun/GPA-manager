# GRS v1 Specification

## Grade Rules Schema (GRS)

Version: 1.0

---

# 1. Introduction

GRS (Grade Rules Schema) v1 is the first version of the Grade Rules Schema specification.

GRS defines a standardized JSON format for describing institution-specific grading rules and GPA calculation policies.

The purpose of GRS is to allow software applications to support different grading systems without modifying application source code.

A GRS document describes the grading rules of exactly one institution.

One JSON file represents one institution.

---

# 2. Scope

GRS v1 supports common grading systems used by universities and educational institutions.

GRS v1 supports:

- Numeric score grading systems.
- Text-based grading systems.
- Letter grade systems.
- Special grade handling.

GRS v1 does not define:

- Course credit calculation.
- GPA weighting methods.
- User-defined formulas.
- Executable scripts.
- Automatic rule guessing.

GRS only describes grading rules.

The software implementation is responsible for applying these rules.

---

# 3. Core Principles

## 3.1 One File = One Institution

Each GRS document represents exactly one institution.

Example:

```text
University A
    |
    └── gpa_scale.json

University B
    |
    └── gpa_scale.json
```

A single GRS file must not contain multiple institutions.

---

## 3.2 Declarative Configuration

GRS files contain data only.

They must not contain:

- Programming code.
- Scripts.
- Custom functions.
- Executable expressions.

---

## 3.3 Versioned Specification

Every GRS document must declare the specification version it follows.

Example:

```json
{
    "version": "1.0"
}
```

---

# 4. Document Structure

A valid GRS v1 document contains the following top-level objects:

```json
{
    "metadata": {},
    "supported_inputs": {},
    "numeric": {},
    "text": {},
    "letter": {},
    "special": {}
}
```

---

# 5. metadata

The `metadata` object contains information about the institution and the GRS document.

Example:

```json
{
    "metadata": {
        "school": "Example University",
        "country": "Example Country",
        "version": "1.0",
        "gpa_scale": 5.0
    }
}
```

---

## 5.1 school

Type:

`string`

Required:

Yes

Description:

The name of the institution.

Example:

```json
"school": "Example University"
```

---

## 5.2 country

Type:

`string`

Required:

Yes

Description:

Country or region information.

Example:

```json
"country": "Taiwan"
```

---

## 5.3 version

Type:

`string`

Required:

Yes

Description:

The GRS specification version used by this document.

GRS v1 documents must use:

```json
"version": "1.0"
```

---

## 5.4 gpa_scale

Type:

`number`

Required:

Yes

Description:

The maximum GPA value used by the institution.

Examples:

```json
4.0
```

or

```json
5.0
```

---

## 5.5 description

Type:

`string` or `array`

Required:

No

Description:

Additional information about the grading rules.

---

# 6. supported_inputs

The `supported_inputs` object declares which input types are supported.

Example:

```json
{
    "supported_inputs": {
        "numeric": true,
        "text": true,
        "letter": true,
        "special": false
    }
}
```

---

## Supported fields

| Field | Type | Description |
|-|-|-|
| numeric | boolean | Numeric scores |
| text | boolean | Text grades |
| letter | boolean | Letter grades |
| special | boolean | Special grades |

---

If an input type is disabled:

```json
"numeric": false
```

The software should ignore the corresponding section.

---

# 7. Numeric Rules

The `numeric` object defines how numerical scores are converted into GPA values.

Example:

```json
{
    "numeric": {
        "mode": "linear",
        "min_score": 60,
        "max_score": 100,
        "min_gpa": 1.0,
        "max_gpa": 5.0
    }
}
```

---

# 7.1 mode

Type:

`string`

Required:

Yes

Allowed values:

- `range`
- `linear`
- `lookup`

Description:

Defines the numeric conversion method.

---

# 7.2 Linear Mode

Linear mode calculates GPA by interpolation between two points.

Example:

```json
{
    "mode": "linear",
    "min_score": 60,
    "max_score": 100,
    "min_gpa": 1.0,
    "max_gpa": 5.0
}
```

Meaning:

```
60 points = 1.0 GPA

100 points = 5.0 GPA
```

Scores between these values are calculated proportionally.

---

# 7.3 Range Mode

Range mode maps score intervals to fixed GPA values.

Example:

```json
{
    "mode": "range",
    "rules": [
        {
            "name": "A",
            "min": 90,
            "max": 100,
            "gpa": 4.0
        }
    ]
}
```

Each rule contains:

| Field | Type | Description |
|-|-|-|
| name | string | Grade name |
| min | number | Minimum score |
| max | number | Maximum score |
| gpa | number | GPA value |

---

# 7.4 Lookup Mode

Lookup mode maps exact numeric values.

Example:

```json
{
    "mode": "lookup",
    "rules": [
        {
            "score": 100,
            "gpa": 5.0
        }
    ]
}
```

---

# 8. Text Rules

The `text` object maps text grades to GPA values.

Example:

```json
{
    "text": {
        "Excellent": 4.0,
        "優秀": 4.0,
        "良好": 3.0,
        "中等": 2.0,
        "及格": 1.0
    }
}
```

Matching rules:

- Exact match.
- Case-sensitive.
- No automatic aliases.
- No fuzzy matching.

---

# 9. Letter Rules

The `letter` object maps letter grades to GPA values.

Example:

```json
{
    "letter": {
        "A+": 4.0,
        "A": 4.0,
        "B": 3.0,
        "F": 0.0
    }
}
```

Supported values depend on the institution.

---

# 10. Special Rules

The `special` object defines special grade behavior.

Example:

```json
{
    "special": {
        "P": "exclude",
        "W": "exclude"
    }
}
```

Supported behaviors:

| Value | Meaning |
|-|-|
| exclude | Remove from GPA calculation |
| zero | Count as zero GPA |

---

# 11. Validation Requirements

A valid GRS v1 document must:

- Contain metadata.
- Contain supported_inputs.
- Have a valid version.
- Have a valid GPA scale.
- Use supported numeric modes.
- Use correct data types.

Invalid documents should not be processed.

---

# 12. Input Matching Priority

When multiple input types exist, software should check in the following order:

1. Special grades.
2. Text grades.
3. Letter grades.
4. Numeric grades.

The first successful match is used.

---

# 13. Complete Example

Example:

```json
{
    "metadata": {
        "school": "Example University",
        "country": "Unknown",
        "version": "1.0",
        "gpa_scale": 5.0
    },

    "supported_inputs": {
        "numeric": true,
        "text": true,
        "letter": true,
        "special": false
    },

    "numeric": {
        "mode": "linear",
        "min_score": 60,
        "max_score": 100,
        "min_gpa": 1.0,
        "max_gpa": 5.0
    }
}
```

---

# 14. Future Compatibility

GRS is designed to support future extensions.

Future versions may add:

- New fields.
- New grading systems.
- Additional metadata.

Future versions should increase the version number.

Example:

```
GRS v2
```

Existing GRS v1 documents should remain readable whenever possible.

---

# End of GRS v1 Specification
