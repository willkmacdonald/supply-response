# Supply Response

- For multi-step feature work, the latest explicitly user-approved specification defines the business intent. An implementation plan may only operationalize it, not add requirements; stop and ask if they conflict.
- Current user direction supersedes older documents. Drafts, agent notes, review reports, and `.superpowers/sdd/` artifacts are evidence, not authorization.
- For Microsoft integrations, use documented public Microsoft APIs, native platform capabilities, and existing repository infrastructure. Propose a custom alternative only for a specific observed or documented gap, explain its cost and maintenance, and obtain approval before building it.
- Treat new cross-cutting machinery—including services, data stores or schemas, infrastructure, identities, secrets, permissions, custom authentication or cryptography, orchestration, lifecycle systems, retention systems, and repository-wide refactoring or hardening—as a scope change requiring explicit approval.
- For demo work, prioritize a complete, visible business journey over production-grade assurance that was not requested.
- Obtain explicit approval for the exact deployment, external email send, tenant permission change, or live-data deletion immediately before performing it. Approval of a specification, plan, or related implementation does not authorize the live action.
