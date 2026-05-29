# VoidWalker

#project #c #systems #on-hold

A terminal-based space roguelike written in C. My first real systems project.
Currently on hold while OS coursework is heavy.

## Status
- [x] Basic map generation (2D array, random rooms)
- [x] Player movement
- [ ] Enemy AI — need to study pathfinding first
- [ ] Save/load system (binary file format, good stdio practice)
- [ ] ncurses TUI polish

## Design notes
Using ncurses for rendering. Each entity is a struct with position, glyph, and HP.
Considering A* for enemies but it might be overkill for a small grid.

## Resources to read
- Robert Nystrom, "Game Programming Patterns" (free at gameprogrammingpatterns.com)
- ncurses HOWTO
- Amit Patel's pathfinding guide at redblobgames.com

## Next session
Pick up enemy AI. Start with a dumb "move toward player" approach before A*.
