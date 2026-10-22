# Events and asynchronous contracts

Use this guidance when a producer and consumer communicate through events or messages. A broker's guarantee is only one part of the end-to-end contract.

## Meaning and ownership

Distinguish a fact that occurred from a command requesting work. Establish producer ownership, event identity, entity identity, schema meaning, and relevant occurrence versus publication times. Decide whether payloads represent a historical snapshot, a delta, or a reference to current state. Consumers must know whether fetching current data can replace processing the original fact.

## Delivery and processing

Establish where publication becomes durable relative to the business change, and where acknowledgment occurs relative to consumer effects. Examine crash windows and recovery on both sides. Choose mechanisms such as an outbox only when the actual consistency requirement and infrastructure justify them.

Define supported duplication, ordering scope, redelivery, retention, and replay behavior. Identify how consumers deduplicate effects, how long that protection lasts, and what happens after it expires. Do not equate exactly-once broker delivery with exactly-once business effects across databases or external providers.

For failures, distinguish transient retries from messages that need intervention. Bound retries and account for poison messages, quarantine/dead-letter handling, diagnosis, and authorized replay where relevant. Establish what happens when consumers fall behind and how lag or failed processing becomes visible to an owner.

## Evolution and verification

Assess compatibility across independently deployed producers and consumers, including unknown fields/values, historical messages, and replay after schema changes. Specify coexistence or translation when required; a schema version alone does not supply compatibility.

Select evidence that challenges the promised lifecycle: publication fails after a state change; processing crashes before acknowledgment; a duplicate or out-of-order event arrives; an older payload is replayed into a newer consumer. Check side effects as well as message receipt, and document guarantees that remain unverified.
