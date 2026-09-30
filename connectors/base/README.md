# Connector contract

The typed `PublishingConnector` protocol and `Draft` value object live in `contentmaxxing/connectors/base.py`. Accounts, drafts, creation, updates, scheduling, publishing, post analytics and follower analytics form the shared transport interface. Capabilities can be absent and must raise an explicit `CapabilityError`. Connectors do not select topics, write content or compute winners. The publishing service owns review gates and remote reconciliation.
