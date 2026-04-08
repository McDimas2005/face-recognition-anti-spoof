# Privacy and Security

## Default posture

- strict privacy defaults
- enrollment images are not retained by default
- review snapshots are configurable
- passwords are hashed
- JWT auth with role checks protects admin routes
- all attendance writes and manual overrides are auditable

## Liveness claim boundary

Passive liveness in this V1 reduces spoofing risk. It does not guarantee protection against printed photos, replay screens, or more sophisticated presentation attacks.

## Data handling

- embeddings are stored in the database
- raw images are optional and policy-controlled
- review images should be retained only as long as operationally needed

