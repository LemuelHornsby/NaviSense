# =====================================================================
# NaviSense Phase 4 - Port Realism
# Script 02: Create Substrate master materials + per-slot MIs for Monacomap
# =====================================================================
#
# WHAT THIS DOES
#   - Creates 7 master materials under Content/NaviSense/Materials/Masters/Substrate/
#       M_PortConcrete_Substrate
#       M_AsphaltWorn_Substrate
#       M_StonePaver_Substrate
#       M_Gravel_Substrate
#       M_RoofTiled_Substrate
#       M_RoofColored_Substrate
#       M_PaintedWall_Substrate
#   - Creates per-slot Material Instances under
#       Content/NaviSense/Materials/Instances/Monaco/
#     using a SLOT_MAP (slot name -> master + tint + UV tile) authored below.
#   - Auto-assigns each MI to its slot on
#       /Game/NaviSense/Ports/Monaco/Monacomap/StaticMeshes/Monacomap
#
# WHY
#   The Monacomap FBX has 40 raw OSM material slots. Without consolidation
#   that's 40 master materials to author by hand. We collapse them into 7
#   parameterized masters (each driven by tint + UV scale + wetness) and
#   spawn cheap MIs per slot in one click. You then wire the 7 master graphs
#   inside the Material Editor following the recipes in
#   Documents/PHASE_4_MASTER_MATERIAL_RECIPES.md.
#
# HOW TO RUN
#   Inside Unreal:  Tools > Execute Python Script...
#     Browse to Content/NaviSense/Python/Phase4_PortRealism/02_create_substrate_masters_and_mis.py
#
# IDEMPOTENT
#   Safe to re-run. Skips any asset that already exists.
# =====================================================================

import unreal

# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------
MASTERS_DIR    = "/Game/NaviSense/Materials/Masters/Substrate"
INSTANCES_DIR  = "/Game/NaviSense/Materials/Instances/Monaco"
TARGET_MESH    = "/Game/NaviSense/Ports/Monaco/Monacomap/StaticMeshes/Monacomap"

# Seven master materials we need. Each entry: (asset_name, comment)
MASTERS = [
    ("M_PortConcrete_Substrate",  "Hero quay - Substrate Slab + Wetness param"),
    ("M_AsphaltWorn_Substrate",   "Road master - tint + UV tile + lane wear"),
    ("M_StonePaver_Substrate",    "Monaco cobblestone - 0.5 m UV tile"),
    ("M_Gravel_Substrate",        "Crushed ballast - railways"),
    ("M_RoofTiled_Substrate",     "Generic terracotta roof - tint param"),
    ("M_RoofColored_Substrate",   "Procedural colored roof - HexTint driven"),
    ("M_PaintedWall_Substrate",   "Mediterranean stucco - tint param"),
]

# Slot -> (master, color hint, uv tile m)
# Color hint is a sensible default tint; you can change in the MI later.
def H(r, g, b):
    return unreal.LinearColor(r, g, b, 1.0)

WHITE  = H(0.92, 0.92, 0.88)
ASPH   = H(0.18, 0.18, 0.19)
STONE  = H(0.62, 0.58, 0.50)
TERRA  = H(0.55, 0.27, 0.18)
GRAVEL = H(0.45, 0.42, 0.38)
PAINT  = H(0.83, 0.78, 0.65)

SLOT_MAP = {
    # named OSM slots
    "roof":               ("M_RoofTiled_Substrate",    TERRA,  1.0),
    "wall":               ("M_PaintedWall_Substrate",  PAINT,  1.0),
    "areas_pedestrian":   ("M_StonePaver_Substrate",   STONE,  0.5),
    "areas_footway":      ("M_StonePaver_Substrate",   STONE,  0.5),
    "paths_footway":      ("M_StonePaver_Substrate",   STONE,  0.5),
    "paths_steps":        ("M_StonePaver_Substrate",   STONE,  0.5),
    "railways":           ("M_Gravel_Substrate",       GRAVEL, 1.0),
    "roads_primary":      ("M_AsphaltWorn_Substrate",  ASPH,   2.0),
    "roads_secondary":    ("M_AsphaltWorn_Substrate",  ASPH,   2.0),
    "roads_tertiary":     ("M_AsphaltWorn_Substrate",  ASPH,   2.0),
    "roads_residential":  ("M_AsphaltWorn_Substrate",  ASPH,   2.0),
    "roads_service":      ("M_AsphaltWorn_Substrate",  ASPH,   1.5),
    "roads_pedestrian":   ("M_AsphaltWorn_Substrate",  ASPH,   1.0),
    "roads_track":        ("M_AsphaltWorn_Substrate",  ASPH,   1.5),
    "roads_other":        ("M_AsphaltWorn_Substrate",  ASPH,   2.0),
    "roads_unclassified": ("M_AsphaltWorn_Substrate",  ASPH,   2.0),
    # named colors
    "white":              ("M_RoofColored_Substrate",  WHITE,  1.0),
    "black":              ("M_RoofColored_Substrate",  H(0.05,0.05,0.05), 1.0),
    "yellow":             ("M_RoofColored_Substrate",  H(0.95,0.82,0.32), 1.0),
}

# Hex-coded roof color slots - parsed from name into LinearColor at runtime.
HEX_ROOF_SLOTS = [
    "4da3dc","54b6e3","57a5b2","62562f","6a6583","80a584","81c9f1",
    "90736d","969791","9ba7fb","9ce78c","a8e7ec","afc5ea","bbc7f1",
    "bdb9ba","eecfaf","f0dac3","fb5569","ff6330","ffbe34","ffe0a0",
]

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def log(m): unreal.log("[NaviSense P4-02] " + str(m))
def warn(m): unreal.log_warning("[NaviSense P4-02] " + str(m))
def err(m):  unreal.log_error("[NaviSense P4-02] " + str(m))

def hex_to_lc(h):
    """e.g. 'ffbe34' -> LinearColor(1.0, 0.745, 0.2)."""
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    return unreal.LinearColor(r, g, b, 1.0)

def ensure_dir(path):
    if not unreal.EditorAssetLibrary.does_directory_exist(path):
        unreal.EditorAssetLibrary.make_directory(path)

def asset_path(folder, name):
    return "{}/{}".format(folder.rstrip("/"), name)

def asset_exists(path):
    return unreal.EditorAssetLibrary.does_asset_exist(path)

def create_master_material(name, folder):
    full = asset_path(folder, name)
    if asset_exists(full):
        return unreal.EditorAssetLibrary.load_asset(full)
    factory = unreal.MaterialFactoryNew()
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    asset = tools.create_asset(name, folder, unreal.Material, factory)
    if asset is None:
        err("Failed to create master {}".format(full))
        return None
    # Mark Substrate path - on UE 5.7 with Substrate enabled this is the default,
    # but we set ShadingModel = DefaultLit for safety.
    try:
        asset.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    except Exception:
        pass
    unreal.EditorAssetLibrary.save_loaded_asset(asset)
    log("Created master: {}".format(full))
    return asset

def create_mi(name, folder, parent_master, base_color, uv_tile, wetness=0.0):
    full = asset_path(folder, name)
    if asset_exists(full):
        mi = unreal.EditorAssetLibrary.load_asset(full)
    else:
        factory = unreal.MaterialInstanceConstantFactoryNew()
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        mi = tools.create_asset(name, folder, unreal.MaterialInstanceConstant, factory)
        if mi is None:
            err("Failed to create MI {}".format(full))
            return None
    # Set parent
    mi.set_editor_property("parent", parent_master)
    # Set parameters (will write into Override even if parent doesn't expose them yet,
    # so they're ready the moment the master graph is wired with the named params)
    unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(mi, "BaseColorTint", base_color)
    unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(mi, "UVTileMeters",  float(uv_tile))
    unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(mi, "Wetness",        float(wetness))
    unreal.EditorAssetLibrary.save_loaded_asset(mi)
    return mi

# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------
def main():
    log("=" * 60)

    # 1. Ensure folder structure
    ensure_dir(MASTERS_DIR)
    ensure_dir(INSTANCES_DIR)

    # 2. Create 7 master material stubs
    masters_by_name = {}
    for name, _ in MASTERS:
        m = create_master_material(name, MASTERS_DIR)
        if m is not None:
            masters_by_name[name] = m
    log("Masters ready: {} / {}".format(len(masters_by_name), len(MASTERS)))

    # 3. Build named-slot MIs
    mis_by_slot = {}
    for slot, (master_name, color, uv) in SLOT_MAP.items():
        master = masters_by_name.get(master_name)
        if master is None:
            warn("No master for slot {} -> {}".format(slot, master_name))
            continue
        mi_name = "MI_{}".format(slot)
        mi = create_mi(mi_name, INSTANCES_DIR, master, color, uv)
        if mi is not None:
            mis_by_slot[slot] = mi

    # 4. Build hex-roof MIs (one per hex code, all parented to M_RoofColored_Substrate)
    roof_master = masters_by_name.get("M_RoofColored_Substrate")
    for h in HEX_ROOF_SLOTS:
        if roof_master is None: break
        mi_name = "MI_roof_{}".format(h)
        mi = create_mi(mi_name, INSTANCES_DIR, roof_master, hex_to_lc(h), 1.0)
        if mi is not None:
            mis_by_slot[h] = mi
    log("Material instances ready: {}".format(len(mis_by_slot)))

    # 5. Assign MIs to Monacomap static mesh slots
    sm = unreal.EditorAssetLibrary.load_asset(TARGET_MESH)
    if sm is None:
        err("Could not load target mesh {}".format(TARGET_MESH))
        return
    slots = sm.static_materials
    assigned = 0
    skipped  = []
    for idx, m in enumerate(slots):
        slot_name = str(m.material_slot_name) or str(m.imported_material_slot_name)
        # Normalize: drop case, the SLOT_MAP keys are lowercase
        key = slot_name.lower()
        mi  = mis_by_slot.get(key)
        if mi is None:
            skipped.append((idx, slot_name))
            continue
        m.material_interface = mi
        assigned += 1
    # Write back
    sm.set_editor_property("static_materials", slots)
    unreal.EditorAssetLibrary.save_loaded_asset(sm)
    log("Slots assigned: {} / {}".format(assigned, len(slots)))
    if skipped:
        warn("Unmapped slots (these need a manual MI):")
        for idx, name in skipped:
            warn("  [{:2d}] '{}'".format(idx, name))

    log("=" * 60)
    log("DONE. Next steps:")
    log("  1. Open each of the 7 masters under {}".format(MASTERS_DIR))
    log("  2. Wire the graph per Documents/PHASE_4_MASTER_MATERIAL_RECIPES.md")
    log("  3. Reload Monacomap in the viewport - MIs will read the params automatically.")
    log("=" * 60)


if __name__ == "__main__":
    main()
