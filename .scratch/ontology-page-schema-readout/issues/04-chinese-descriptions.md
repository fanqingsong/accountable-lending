# Chinese descriptions for known lending-schema names

Status: done

## Parent

`.scratch/ontology-page-schema-readout/PRD.md`

## What to build

Class, property, and relationship descriptions on the ontology page are Chinese for names already in the lending schema. Map in the readout mapper using CONTEXT terms: Application is one loan case; Decision is a recorded outcome; Document is an ingested applicant file; Entity is an extracted participant or fact (never an Application, Document, or Decision); `HAS_DECISION` attaches, it does not replace `CAUSED`; `CAUSED` is Decision-to-Decision causality on the Audit trail.

If a name has no mapping, fall back to the JSON `description`. Do not change the schema document or required flags to add Chinese.

## Acceptance criteria

- [x] Known classes, properties, and relationships show Chinese descriptions on the page.
- [x] Entity / `HAS_DECISION` / `CAUSED` wording matches CONTEXT (no “case service”, attach is not the Audit trail).
- [x] Unmapped names still show the JSON description when present.
- [x] `lending.json` is unchanged.
- [x] Browser check: ontology page descriptions are Chinese for the current schema names.

## Blocked by

- `.scratch/ontology-page-schema-readout/issues/01-schema-tables.md`

## Comments

Chinese strings live in the readout mapper; `lending.json` was not edited.
