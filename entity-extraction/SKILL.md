---
name: entity-extraction
description: Extracting entities and relations from knowledge blocks — Stage 2 of architecting-knowledge-forms pipeline
version: 0.1.0
tags: [knowledge-management, ner, relation-extraction, data-modeling]
author: leislicai
---

# Entity Extraction

## Overview

Stage 2 of the [architecting-knowledge-forms](../architecting-knowledge-forms/SKILL.md) pipeline. Extracts entities from `blocks.entities[]` and derives relations between them. Outputs a flat entity catalog with edges.

See [architecting-knowledge-forms/data-model.md](../architecting-knowledge-forms/data-model.md) for the Entity schema.

**Previous stage:** [knowledge-block-extraction](../knowledge-block-extraction/SKILL.md)
**Next stage:** [wiki-compilation](../wiki-compilation/SKILL.md)
