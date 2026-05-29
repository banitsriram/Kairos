# Operating Systems

#cs #os #study

## Processes vs Threads
A process is an independent program in execution with its own address space.
A thread shares the address space of its parent process — cheaper to create,
harder to reason about safely.

## Scheduling Algorithms
- **FCFS** (First Come First Served): simple, causes convoy effect
- **SJF** (Shortest Job First): optimal average wait time but needs future knowledge
- **Round Robin**: preemptive, fair, good for interactive systems

## Virtual Memory
The OS gives each process the illusion it has the full address space.
Page tables map virtual → physical addresses.
A **page fault** fires when a page isn't in RAM and must be loaded from disk.

**TLB** (Translation Lookaside Buffer): a small hardware cache for page table entries.
TLB miss is expensive — this is why spatial and temporal locality matter so much.

## Deadlock — Coffman Conditions
All four must hold simultaneously for deadlock to occur:
1. Mutual exclusion
2. Hold and wait
3. No preemption
4. Circular wait

Break any one of them and deadlock can't happen.
