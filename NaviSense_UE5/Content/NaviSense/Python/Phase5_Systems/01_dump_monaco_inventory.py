# =====================================================================
# NaviSense Phase 5 - Monaco level actor inventory dumper
# =====================================================================
# Run from:  Tools > Execute Python Script...  (with NaviSense_Monaco open)
#
# Writes a full inventory of every actor in the current level to:
#   <project>/Saved/NaviSense_Reports/monaco_inventory.json
#   ...and prints a class-count summary to the Output Log.
#
# Purpose: a ground-truth snapshot of what is actually placed in Monaco
# (water, lighting, Cesium, bollards, yacht, etc.) so planning continues
# from reality instead of guesswork. Safe / read-only.
# =====================================================================

import unreal, json, os, collections

TAG = "[NaviSense P5-01]"
def log(m):  unreal.log(TAG + " " + str(m))
def warn(m): unreal.log_warning(TAG + " " + str(m))

def actor_subsys():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

def main():
    actors = actor_subsys().get_all_level_actors()
    rows = []
    counts = collections.Counter()
    for a in actors:
        cls = a.get_class().get_name()
        counts[cls] += 1
        loc = a.get_actor_location()
        rows.append({
            "label": a.get_actor_label(),
            "class": cls,
            "x_cm": round(loc.x, 1), "y_cm": round(loc.y, 1), "z_cm": round(loc.z, 1),
        })

    proj = unreal.Paths.project_dir()
    out_dir = os.path.join(proj, "Saved", "NaviSense_Reports")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "monaco_inventory.json")
    with open(out, "w") as f:
        json.dump({"actor_count": len(rows),
                   "class_counts": dict(counts),
                   "actors": sorted(rows, key=lambda r: r["class"])}, f, indent=2)

    log("==== Monaco actor inventory ====")
    log("Total actors: %d" % len(rows))
    for cls, n in counts.most_common():
        log("  %4d  %s" % (n, cls))
    log("Full JSON written to: %s" % out)

    # quick presence checks for the systems we care about
    def has(substr):
        return any(substr.lower() in c.lower() for c in counts)
    log("---- system presence ----")
    for name, key in [("Water Body Ocean", "WaterBodyOcean"),
                      ("Water Zone", "WaterZone"),
                      ("Cesium Georeference", "CesiumGeoreference"),
                      ("Cesium 3D Tileset", "Cesium3DTileset"),
                      ("Cartographic Polygon", "CartographicPolygon"),
                      ("Directional Light (Sun)", "DirectionalLight"),
                      ("Sky Atmosphere", "SkyAtmosphere"),
                      ("Sky Light", "SkyLight"),
                      ("Post Process Volume", "PostProcessVolume"),
                      ("Ship pawn", "ShipPawn"),
                      ("PCG Volume", "PCGVolume")]:
        log("  [%s] %s" % ("X" if has(key) else " ", name))

main()
