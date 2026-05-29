# Distributed Systems

#cs #distributed #study

## CAP Theorem
A distributed system can only guarantee two of three properties:
- **Consistency**: every read sees the most recent write
- **Availability**: every request gets a response
- **Partition tolerance**: system works despite network splits

Partition tolerance is non-negotiable in real networks — so you choose CP or AP.

## Raft Consensus
Easier to understand than Paxos. Three roles: leader, follower, candidate.
- Leader sends heartbeats to followers
- If a follower times out waiting, it becomes a candidate and holds an election
- Log replication: leader appends, majority must acknowledge before committing

## Eventual Consistency
Writes propagate asynchronously. All replicas converge *eventually*.
Good for: shopping carts, DNS, social media counters.
Bad for: bank balances, ticket reservations — anywhere double-spend matters.

## Consistent Hashing
Maps both nodes and keys onto a ring. Adding/removing a node only remaps
a small fraction of keys. Used by DynamoDB, Cassandra, and many CDNs.
