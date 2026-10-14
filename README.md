# Nuclear Fission Chain Reaction — Blender Simulation

A 3D visualization of a nuclear fission chain reaction, built as a Python script
for Blender. Made as a personal project while preparing for a nuclear
engineering degree.

## What it shows

- A neutron flies in from off-screen and strikes the first nucleus
- That nucleus "fissions": it flashes with energy, splits into two fragments
  that fly apart, and releases new neutrons
- Each new neutron flies out and strikes a new nucleus, which fissions in turn
- The reaction spreads generation by generation in a branching tree pattern
  (1 → K → K² → K³ ...), visually similar to textbook fission-chain diagrams
- Each nucleus is modeled as a cluster of small spheres representing protons
  and neutrons, rather than a single plain sphere

## How to run it

1. Install [Blender](https://www.blender.org/) (free).
2. Open Blender and switch to the **Scripting** tab.
3. Open `fission_chain_reaction.py` in the text editor panel (use the
   **Open** button), or create a new text block and paste the script in.
   - Important: paste into the main text editor panel, not the small
     **Python Console** at the bottom — the console only accepts one line
     at a time.
4. Click the **▶ Run Script** button.
5. In the viewport, switch shading mode to **Material Preview** (the shaded
   sphere icon, top-right of the 3D viewport) to see the colors properly.
6. Press **Spacebar** to play the animation.

## Parameters you can tweak

All near the top of the script:

| Parameter | What it does |
|---|---|
| `MULTIPLICATION_K` | How many new neutrons each fission releases (branching factor) |
| `MAX_GENERATIONS` | How many generations the chain reaction runs for |
| `NUCLEONS_PER_NUCLEUS` | How many small spheres (protons/neutrons) make up one nucleus |
| `NUCLEON_RADIUS` | Size of each individual proton/neutron sphere |
| `CLUSTER_RADIUS` | How tightly the protons/neutrons are packed together |
| `PROTON_COLOR` / `NEUTRON_COLOR` | Colors of protons and neutrons (RGBA, 0–1 range) |
| `SPACING_X` / `BASE_SPREAD` | How far apart generations and sibling nuclei are placed |

## Tech used

- Blender 3D (Python API / `bpy`)
- Python 3

## Why I built this

I'm a high school student planning to study nuclear engineering. I wanted a
hands-on way to visualize how a fission chain reaction actually branches out,
instead of just reading about it — and to practice using Blender's Python
scripting API.
