Added a new `allow_package_substitution` boolean field to PythonRepository (default: True).
When set to False, any new repository version that would implicitly replace existing content
with content that has the same filename but a different sha256 checksum is rejected. This
applies to all repository version creation paths including uploads, modify, and sync. Content
with a matching checksum is allowed through idempotently.
