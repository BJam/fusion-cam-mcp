# Fusion project feedback for the coaster
_Exported on 2/20/2026 at 08:45:53 PST from Cursor (2.5.17)_

---

**User**

give me feedback on the fusion project for the coaster

---

**Cursor**

Let me pull up the Fusion 360 CAM data for your coaster project. I'll start by discovering what tools are available and then gather the project details.

Now let me pull the project data from Fusion 360.

Let me also grab the detailed operation parameters and machining times.

Here's my feedback on your **Coaster v2** project for the Nomad 3.

---

## Project Overview

| | |
|---|---|
| **Machine** | Carbide3D Nomad 3 (3-axis, 0.13 kW spindle, max 24,000 RPM) |
| **Material** | Plywood, Finish |
| **Stock** | 100 x 100 x 10 mm (fixed box, 1 mm top offset) |
| **Tool** | #102 -- 1/8" (3.175 mm) flat end mill, 2 flute, 12.7 mm flute length |
| **Operations** | 2D Adaptive (roughing) then 2D Contour (profile finish) |
| **Total cycle time** | ~4 min 54 sec |
| **Toolpath status** | Both valid, no warnings |

---

## What looks good

- **Correct workflow order** -- adaptive clearing first to remove bulk material, then a contour pass for the final profile. Textbook approach.
- **Climb milling** on the adaptive -- correct for CNC.
- **0.5 mm radial stock to leave** on the adaptive gives the contour a clean, consistent finishing allowance.
- **Tolerances are well-tiered** -- 0.1 mm for roughing, 0.01 mm for the finish contour.
- **Coolant disabled** -- correct for the Nomad 3 (no coolant system) and plywood.
- **Helix ramp** at 2 degrees on the adaptive is gentle and safe for the small end mill.
- **Optimal load** of 1.27 mm (40% of tool diameter) is a reasonable WOC for the adaptive.

---

## Concerns

### 1. No tabs on the contour -- the part will come loose

This is the biggest issue. Your `2D Contour1` has tabs disabled. If this contour is cutting out the coaster profile (through-cutting the stock), the part will break free at the end of the cut. On a Nomad 3 this can snap the 1/8" bit or send the part flying.

**Recommendation:** Enable tabs. For a coaster in plywood, 3-4 tabs at roughly 3 mm wide and ~1 mm tall would hold the part securely and be easy to clean up with a chisel or sanding.

### 2. No multiple depths on the contour

`doMultipleDepths` is **false** on the contour operation. If you're cutting through the full 10 mm stock in a single pass with a 3.175 mm end mill on a 130W spindle, that's aggressive even in plywood. The tool has enough flute length (12.7 mm), but the Nomad's spindle will be working very hard.

**Recommendation:** Enable multiple depths with a stepdown of ~2-3 mm per pass (roughly 1x tool diameter). This will be much kinder to the tool and the machine, and won't add much time.

### 3. Chip load is on the low side for plywood

You're running 0.025 mm/tooth (~0.001 in/tooth). Wood generally likes bigger chips -- too small and you're rubbing rather than cutting, which can cause burning and fuzzy edges on plywood. For a 1/8" end mill in plywood, 0.05-0.075 mm/tooth (0.002-0.003 in/tooth) is a more typical range.

**Recommendation:** Consider bumping the cutting feed to ~2000-3000 mm/min at 20,000 RPM (giving 0.05-0.075 mm/tooth). You could also drop the RPM to ~16,000 and run ~1600 mm/min for a similar chip load with less heat. Test on scrap first -- the Nomad's feed rate limit may constrain you.

### 4. Contour runs at the same feed rate as roughing

Both operations use identical feeds and speeds (1000 mm/min, 20,000 RPM). This is fine functionally, but since the contour is your finish pass, slowing down slightly (~800 mm/min) can give a cleaner edge on plywood. That said, for a coaster this is a minor point -- the difference may not be noticeable.

### 5. Lead-in/lead-out arcs are very small

Both operations use a lead radius of 0.3175 mm (10% of tool diameter). This is tiny and almost acts like a straight plunge into the cut. Increasing this to 25-50% of tool diameter (~0.8-1.6 mm) would provide a smoother tool engagement and better surface finish at the entry point.

---

## Summary

The project structure and strategy are solid. The two actionable items I'd prioritize before cutting are **enabling tabs** on the contour (safety issue) and **enabling multiple depths** on the contour (protects the tool and machine). The feeds and speeds tweaks are secondary but would improve cut quality in plywood.

---

**User**

I have turned on full write, can you make the suggested changes 

---

**Cursor**

Let me check what other tools the full server has for things like tabs and passes settings.

The `update_operation_parameters` tool can change feeds, speeds, and engagement values, but it can't toggle settings like tabs or multiple depths. Let me make all the changes I can and note what you'll need to toggle manually in Fusion.

I'll start with the feeds and speeds changes on both operations.

All the feeds, speeds, and engagement changes are applied. Here's a summary of what was changed:

### Changes applied via MCP

**2D Adaptive1 (roughing):**
| Parameter | Before | After |
|---|---|---|
| Spindle Speed | 20,000 rpm | 18,000 rpm |
| Cutting Feed | 1,000 mm/min | 1,800 mm/min |
| Plunge / Ramp Feed | 333 mm/min | 500 mm/min |
| Entry / Exit / Transition | 1,000 mm/min | 1,800 mm/min |
| **Chip load** | **0.025 mm/tooth** | **0.05 mm/tooth** |

**2D Contour1 (finishing):**
| Parameter | Before | After |
|---|---|---|
| Spindle Speed | 20,000 rpm | 18,000 rpm |
| Cutting Feed | 1,000 mm/min | 1,500 mm/min |
| Plunge / Ramp Feed | 333 mm/min | 500 mm/min |
| Entry / Exit / Transition | 1,000 mm/min | 1,500 mm/min |
| Max Stepdown | (default expression) | 3 mm |
| **Chip load** | **0.025 mm/tooth** | **0.042 mm/tooth** |

---

### 3 things you need to toggle manually in Fusion

The MCP write tool only supports feeds/speeds/engagement parameters -- it can't flip boolean toggles or change linking geometry. You'll need to do these by hand:

1. **Enable tabs on `2D Contour1`** -- Edit the operation, go to the **Passes** tab, check **Tabs**. Set width to ~3 mm, height to ~1 mm, and use "By Distance" with ~60 mm spacing (should give you 3-4 tabs around the coaster).

2. **Enable Multiple Depths on `2D Contour1`** -- In the **Passes** tab, check **Multiple Depths**. The stepdown value is already set to 3 mm (I pushed that through), so once you toggle it on, it will step down in 3 mm passes.

3. **Increase lead-in/lead-out radii** -- Edit each operation, go to the **Linking** tab. Under Lead-In, increase the radius from 0.3175 mm to ~1.0-1.5 mm (about 30-50% of tool diameter). Do the same for Lead-Out. This gives a smoother arc entry into the cut.

After making those manual toggles, you'll need to regenerate toolpaths -- I can do that for you once you're ready.

---

**User**

1 - I don't want tabs, I'll be fixturing it with painters tape and CA glue, 2 - done, 3 - why?

---

**Cursor**

Good call on the tape and CA glue method -- that holds the whole bottom face, so no tabs needed and no cleanup. Let me update my notes.

Regarding **lead-in/lead-out radii**: with your current values at 0.3175 mm (10% of the 3.175 mm tool diameter), the tool enters the cut on an extremely tight arc -- almost a straight plunge into the material wall. A larger radius (say 1.0-1.5 mm) gives the tool a gentler, sweeping entry into the cut, which:

- Reduces the shock load on the cutter at the moment of engagement
- Avoids leaving a witness mark (small gouge or dwell mark) at the entry/exit point on the finished edge
- Is kinder to a small 1/8" end mill on the Nomad's light spindle

That said, for a coaster in plywood with a tape-and-glue fixture, this is a pretty minor cosmetic detail. The entry mark would likely sand out in seconds. So it's entirely optional -- skip it if you don't want to fuss with it.

All the MCP changes are done. Once you've toggled on **Multiple Depths** in the Passes tab of `2D Contour1`, you should be ready to regenerate toolpaths. Want me to kick that off?

---

**User**

can you give estimates on the improvement in machine time?

---

**Cursor**

The toolpaths haven't been regenerated yet so I can't get exact numbers from Fusion, but the math is straightforward. Machining time scales roughly inversely with feed rate for cutting moves.

### 2D Adaptive1 (roughing)

| | Before | After | Change |
|---|---|---|---|
| Cutting feed | 1,000 mm/min | 1,800 mm/min | 1.8x faster |
| Plunge/ramp | 333 mm/min | 500 mm/min | 1.5x faster |
| Estimated time | **4m 31s** | **~2m 40s** | **-1m 51s** |

The toolpath geometry is identical -- same optimal load, same stepdown -- so the machine just traverses it faster. Roughly 85% of the time is cutting moves (1.8x speedup) with the rest in plunge/ramp/rapids.

### 2D Contour1 (finishing)

This one is a trade-off. The feed is faster, but multiple depths adds passes:

| | Before | After | Change |
|---|---|---|---|
| Cutting feed | 1,000 mm/min | 1,500 mm/min | 1.5x faster |
| Depths | 1 pass (full depth) | ~3-4 passes at 3 mm | 3-4x more passes |
| Estimated time | **22s** | **~50s** | **+28s** |

The contour gets slower because you're trading speed for safety -- much less stress on the tool and machine per pass.

### Total

| | Before | After | Change |
|---|---|---|---|
| Total | **4m 54s** | **~3m 30s** | **~28% faster** |

The adaptive speedup more than makes up for the extra contour passes. Net savings of roughly **1 minute 24 seconds** per coaster. If you're making a batch, that adds up.

Want me to regenerate toolpaths so we can get exact numbers from Fusion?

