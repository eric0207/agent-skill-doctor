---
name: doctor-greeting
description: Produce a deterministic greeting JSON for Skill Doctor runtime verification.
---
When asked to greet someone, return only a JSON object with exactly two keys:
"greeting": "Hello, <name>!" and "skill_marker": "doctor-greeting-v1".
Do not run scripts or access external services.
