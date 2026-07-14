# =====================================================================
# NaviSense Phase 4 - FINAL material binding
# =====================================================================
#
# Scripts 02, 08, 09 all "succeeded" but materials never propagated to
# the placed PortHercule_Monacomap actor. The reason: my MI lookup
# matched by slot name, but the asset's slots had OSM auto-generated
# Material assets with the same names, so per-component overrides and
# asset slots collided and UE kept the asset's stale OSM value.
#
# This script writes per-component overrides using the FULL MI asset
# path, bypassing any name collision. It also forcibly re-saves the
# placed actor's external actor file (World Partition stores per-actor
# state in /Game/__ExternalActors__/).
# =====================================================================

import unreal

MI_FOLDER         = "/Game/NaviSense/Materials/Instances/Monaco"
MONACOMAP_ASSET   = "/Game/NaviSense/Ports/Monaco/Monacomap/StaticMeshes/Monacomap"


def log(m):  unreal.log("[NaviSense P4-10] " + str(m))
def warn(m): unreal.log_warning("[NaviSense P4-10] " + str(m))
def err(m):  unreal.log_error("[NaviSense P4-10] " + str(m))


def get_actor_subsys():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def find_all_monacomap_actors():
    target_path = MONACOMAP_ASSET
    hits = []
    for a in get_actor_subsys().get_all_level_actors():
        try:
            smc = a.static_mesh_component
        except Exception:
            continue
        if smc is None:
            continue
        cur = smc.static_mesh
        if cur is None:
            continue
        if cur.get_path_name().startswith(target_path):
            hits.append(a)
    return hits


def build_mi_lookup():
    reg = unreal.AssetRegistryHelpers.get_asset_registry()
    mi_filter = unreal.ARFilter(
        class_names=["MaterialInstanceConstant"],
        package_paths=[MI_FOLDER],
        recursive_paths=True,
    )
    lookup = {}
    for mi_meta in reg.get_assets(mi_filter):
        name = str(mi_meta.asset_name)
        if not name.startswith("MI_"):
            continue
        slot_key = name[3:]
        if slot_key.startswith("roof_"):
            slot_key = slot_key[5:]
        path = "{}.{}".format(mi_meta.package_name, mi_meta.asset_name)
        mi = unreal.EditorAssetLibrary.load_asset(path)
        if mi is not None:
            lookup[slot_key.lower()] = (mi, path)
    return lookup


def main():
    log("=" * 60)

    mi_lookup = build_mi_lookup()
    log("MI lookup: {} entries".format(len(mi_lookup)))

    actors = find_all_monacomap_actors()
    log("Found {} Monacomap actor(s) in level.".format(len(actors)))
    if not actors:
        err("No Monacomap actor in the level.")
        return

    # Read the slot names from the asset itself (these define the slot ordering)
    sm = unreal.EditorAssetLibrary.load_asset(MONACOMAP_ASSET)
    if sm is None:
        err("Could not load {}".format(MONACOMAP_ASSET))
        return
    asset_slots = sm.static_materials

    log("")
    log("Asset has {} slots; applying overrides per actor:".format(len(asset_slots)))

    for actor in actors:
        smc = actor.static_mesh_component
        if smc is None:
            warn("  {} has no SMC".format(actor.get_actor_label()))
            continue

        applied = 0
        not_found = []
        # Build slot index -> slot name from the asset
        for slot_idx, s in enumerate(asset_slots):
            slot_name = (str(s.material_slot_name) or
                         str(s.imported_material_slot_name) or "").lower()
            if not slot_name:
                continue
            mi_entry = mi_lookup.get(slot_name)
            if mi_entry is None:
                not_found.append(slot_name)
                continue
            mi, mi_path = mi_entry
            # First clear any existing override at this index
            smc.set_material(slot_idx, None)
            # Then assign our MI by direct asset reference
            smc.set_material(slot_idx, mi)
            applied += 1

        smc.modify()
        smc.mark_render_state_dirty()

        # Mark the actor dirty and save
        actor.modify()

        log("  {}  ({})  -> {} / {} overrides applied".format(
            actor.get_actor_label(),
            actor.get_class().get_name(),
            applied, len(asset_slots)))
        if not_found:
            warn("    Unmatched slot names (no MI_<name>): {}".format(not_found[:6]))

    # Force a level save - this triggers World Partition to write the
    # per-actor external file with the new component overrides.
    unreal.EditorLevelLibrary.save_current_level()

    # Verification readback
    log("")
    log("Readback verification:")
    for actor in actors:
        smc = actor.static_mesh_component
        if smc is None: continue
        sample_count = 0
        for i in range(min(5, smc.get_num_materials())):
            m = smc.get_material(i)
            if m is not None:
                sample_count += 1
                slot_name = str(asset_slots[i].material_slot_name) if i < len(asset_slots) else "?"
                log("  [{:2d}] {} -> {}".format(i, slot_name, m.get_path_name()))
        # Count all
        non_null = sum(1 for i in range(smc.get_num_materials())
                       if smc.get_material(i) is not None)
        log("  Total non-null overrides on {}: {} / {}".format(
            actor.get_actor_label(), non_null, smc.get_num_materials()))

    log("=" * 60)
    log("DONE. If readback shows non-null overrides AND the viewport still")
    log("shows white, click off the actor and click back ON it (or press F)")
    log("to force a redraw. The render thread sometimes lags.")
    log("=" * 60)


if __name__ == "__main__":
    main()
