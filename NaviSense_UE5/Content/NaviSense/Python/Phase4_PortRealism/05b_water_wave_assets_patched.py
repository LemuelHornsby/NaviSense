# =====================================================================
# NaviSense Phase 4 - Port Realism
# Script 05b: PATCHED - Author WaveAssets using path-based class lookup
# =====================================================================
#
# WHAT CHANGED FROM 05
#   The Water plugin's Python class registration is lazy in UE 5.7.
#   getattr(unreal, "WaterWavesAsset") fails until the class is touched.
#   This version uses unreal.load_class()/load_object() with the explicit
#   /Script/ paths the discovery (05a) confirmed work.
#
# Also bind the wave asset on the WaterBodyOceanComponent (the COMPONENT,
# not the actor itself - the wave reference lives on the component).
# =====================================================================

import unreal

# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------
SEA_DIR = "/Game/NaviSense/Settings/Sea"

PRESETS = {
    "WaveAsset_Calm": {
        "num_waves":  12, "amplitude": 0.07, "min_lambda": 3.0,
        "max_lambda": 30.0, "direction": 135.0, "hs": 0.2,
    },
    "WaveAsset_Moderate": {
        "num_waves":  16, "amplitude": 0.22, "min_lambda": 5.0,
        "max_lambda": 60.0, "direction": 135.0, "hs": 0.6,
    },
    "WaveAsset_Rough": {
        "num_waves":  20, "amplitude": 0.55, "min_lambda": 8.0,
        "max_lambda": 120.0, "direction": 135.0, "hs": 1.5,
    },
}
DEFAULT_PRESET = "WaveAsset_Calm"

# Class paths confirmed by 05a
PATH_WAVES_ASSET    = "/Script/Water.WaterWavesAsset"
PATH_GERSTNER_WAVES = "/Script/Water.GerstnerWaterWaves"
PATH_FACTORY        = "/Script/WaterEditor.WaterWavesAssetFactory"

# ---------------------------------------------------------------------
def log(m):  unreal.log("[NaviSense P4-05b] " + str(m))
def warn(m): unreal.log_warning("[NaviSense P4-05b] " + str(m))
def err(m):  unreal.log_error("[NaviSense P4-05b] " + str(m))

def ensure_dir(path):
    if not unreal.EditorAssetLibrary.does_directory_exist(path):
        unreal.EditorAssetLibrary.make_directory(path)

def asset_path(folder, name):
    return "{}/{}".format(folder.rstrip("/"), name)

def find_actor_by_label(label):
    subsys = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for a in subsys.get_all_level_actors():
        if a.get_actor_label() == label:
            return a
    return None

def find_actor_by_class_substr(substr):
    subsys = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    sub_lc = substr.lower()
    for a in subsys.get_all_level_actors():
        if sub_lc in a.get_class().get_name().lower():
            return a
    return None

def first_component_of_class_path(actor, class_path):
    """Return first component whose class path matches."""
    target_cls = unreal.load_class(None, class_path)
    if target_cls is None:
        return None
    for c in actor.get_components_by_class(target_cls):
        return c
    return None

# ---------------------------------------------------------------------
def create_wave_asset(name, folder, preset, waves_asset_cls, factory_cls,
                      gerstner_cls):
    full = asset_path(folder, name)

    if unreal.EditorAssetLibrary.does_asset_exist(full):
        asset = unreal.EditorAssetLibrary.load_asset(full)
        log("  Re-using existing {}".format(name))
    else:
        factory = unreal.new_object(factory_cls)
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        asset = tools.create_asset(name, folder, waves_asset_cls, factory)
        if asset is None:
            err("  create_asset returned None for {}".format(full))
            return None

    # The WaterWavesAsset holds an inner 'waves' UObject of type WaterWaves
    # (commonly GerstnerWaterWaves). Get-or-create it.
    inner = None
    try:
        inner = asset.get_editor_property("waves")
    except Exception:
        pass

    if inner is None or inner.get_class() != gerstner_cls:
        # Create a Gerstner-type inner UObject owned by the asset
        try:
            inner = unreal.new_object(gerstner_cls, asset)
            asset.set_editor_property("waves", inner)
            log("    attached new GerstnerWaterWaves inner object")
        except Exception as e:
            warn("    could not attach inner GerstnerWaterWaves: {}".format(e))

    # Set Gerstner parameters on inner. Property names are best-effort
    # because the Water plugin's UPROPERTY names vary between 5.x point
    # releases. Wrap each in try/except so unknown ones don't abort.
    if inner is not None:
        prop_attempts = [
            # (UPROPERTY name, value)
            ("num_waves",            int(preset["num_waves"])),
            ("seed",                 1234),
            ("wind_angle_deg",       float(preset["direction"])),
            ("min_wavelength",       float(preset["min_lambda"]) * 100.0),
            ("max_wavelength",       float(preset["max_lambda"]) * 100.0),
            ("wavelength_falloff",   1.0),
            ("min_amplitude",        float(preset["amplitude"]) * 50.0),
            ("max_amplitude",        float(preset["amplitude"]) * 200.0),
            ("amplitude_falloff",    1.0),
            ("directional_spread",   30.0),
            ("small_wave_steepness", 0.5),
            ("large_wave_steepness", 0.85),
        ]
        applied = []
        for k, v in prop_attempts:
            try:
                inner.set_editor_property(k, v)
                applied.append(k)
            except Exception:
                pass
        log("    applied {} Gerstner params: {}".format(len(applied), applied[:6]))

        # Some versions expose a 'RebuildWaves' method that must be called
        # for the inner array to regenerate from the parameters.
        for rebuild in ("rebuild_waves", "RebuildWaves"):
            try:
                inner.call_method(rebuild, ())
                log("    called {}()".format(rebuild))
                break
            except Exception:
                continue

    unreal.EditorAssetLibrary.save_loaded_asset(asset)
    log("  Saved {} (Hs hint {} m)".format(name, preset["hs"]))
    return asset

def bind_waves_to_water_body(water_body, wave_asset):
    """The water_waves reference lives on the WaterBodyOceanComponent,
    not on the actor. We try both for safety."""
    if water_body is None or wave_asset is None:
        return False

    comp = first_component_of_class_path(water_body,
        "/Script/Water.WaterBodyOceanComponent")
    if comp is None:
        comp = first_component_of_class_path(water_body,
            "/Script/Water.WaterBodyComponent")

    targets = []
    if comp is not None:
        targets.append(("WaterBodyOceanComponent", comp))
    targets.append(("WaterBodyOcean (actor)", water_body))

    for label, t in targets:
        for prop in ("water_waves", "water_waves_asset"):
            try:
                t.set_editor_property(prop, wave_asset)
                log("  Bound {} -> {}.{}".format(
                    wave_asset.get_name(), label, prop))
                return True
            except Exception:
                continue

    warn("  Could not bind WaveAsset via Python.")
    warn("  Manual: select WaterBodyOcean > Details > Wave Source > Water Waves Asset = {}"
         .format(wave_asset.get_name()))
    return False

def tag_actor(actor, tags_to_add):
    if actor is None:
        return
    try:
        cur = list(actor.tags) if actor.tags else []
        for t in tags_to_add:
            tn = unreal.Name(t)
            if tn not in cur:
                cur.append(tn)
        actor.tags = cur
    except Exception:
        pass

# ---------------------------------------------------------------------
def main():
    log("=" * 60)

    waves_asset_cls = unreal.load_class(None, PATH_WAVES_ASSET)
    factory_cls     = unreal.load_class(None, PATH_FACTORY)
    gerstner_cls    = unreal.load_class(None, PATH_GERSTNER_WAVES)

    if not all([waves_asset_cls, factory_cls, gerstner_cls]):
        err("Class resolution failed:")
        err("  WaterWavesAsset      : {}".format(waves_asset_cls))
        err("  WaterWavesAssetFactory: {}".format(factory_cls))
        err("  GerstnerWaterWaves   : {}".format(gerstner_cls))
        return
    log("All Water classes resolved.")

    ensure_dir(SEA_DIR)

    # 1. Create or update WaveAssets
    wave_assets = {}
    for name, preset in PRESETS.items():
        a = create_wave_asset(name, SEA_DIR, preset,
                              waves_asset_cls, factory_cls, gerstner_cls)
        if a is not None:
            wave_assets[name] = a
    log("Created/updated {} WaveAssets".format(len(wave_assets)))

    # 2. Bind default preset to WaterBodyOcean
    water_body = find_actor_by_label("WaterBodyOcean") \
              or find_actor_by_class_substr("WaterBodyOcean")
    if water_body is None:
        warn("No WaterBodyOcean in level - skipping bind step.")
    else:
        default_asset = wave_assets.get(DEFAULT_PRESET)
        if default_asset is not None:
            bind_waves_to_water_body(water_body, default_asset)

    # 3. Tag water actors
    tag_actor(water_body, ["NaviSense.Water.Ocean"])
    water_zone = find_actor_by_label("WaterZone") \
              or find_actor_by_class_substr("WaterZone")
    tag_actor(water_zone, ["NaviSense.Water.Zone"])

    log("=" * 60)
    log("DONE. Visual check:")
    log("  1. Select WaterBodyOcean in Outliner.")
    log("  2. Details > Wave Source > Water Waves Asset = WaveAsset_Calm")
    log("  3. Press Play - ocean should ripple gently.")
    log("  4. Open WaveAsset_Calm/Moderate/Rough in Content/NaviSense/Settings/Sea/")
    log("     to inspect/tune the Gerstner parameters.")
    log("=" * 60)


if __name__ == "__main__":
    main()
